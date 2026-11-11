from decimal import Decimal

import pytest
from sqlalchemy import text

from app.banco import criar_engine, criar_sessoes, sessao_de
from app.barramento import Barramento
from app.contratos import (
    Container,
    PassageiroFalso,
    aplicar_registro,
    carregar_modulos,
    criar_container,
    iniciar,
)
from app.eventos import AssentoBloqueado, ReservaCriada


def test_sessao_sqlite_desfaz_alteracao_sem_commit():
    engine = criar_engine("sqlite:///:memory:")
    with engine.begin() as conexao:
        conexao.execute(text("CREATE TABLE exemplo (id INTEGER PRIMARY KEY, nome TEXT)"))
    sessoes = criar_sessoes(engine)

    with sessao_de(sessoes) as sessao:
        sessao.execute(text("INSERT INTO exemplo (nome) VALUES ('a')"))
        sessao.rollback()
        total = sessao.execute(text("SELECT COUNT(*) FROM exemplo")).scalar_one()

    assert total == 0


def test_barramento_entrega_evento_aos_inscritos():
    barramento = Barramento()
    recebidos = []
    barramento.inscrever(ReservaCriada, recebidos.append)
    barramento.inscrever(ReservaCriada, recebidos.append)
    evento = ReservaCriada(1, 2, "12A", 3, Decimal("100.00"))

    barramento.publicar(evento)

    assert recebidos == [evento, evento]
    assert evento.nome == "ReservaCriada"


def test_barramento_entrega_evento_publicado_pelo_tratador():
    barramento = Barramento()
    recebidos = []

    def ao_criar(evento: ReservaCriada) -> None:
        recebidos.append(evento)
        barramento.publicar(AssentoBloqueado(evento.reserva_id, evento.voo_id, evento.codigo_assento))

    barramento.inscrever(ReservaCriada, ao_criar)
    barramento.inscrever(AssentoBloqueado, recebidos.append)

    barramento.publicar(ReservaCriada(1, 2, "12A", 3, Decimal("100.00")))

    assert [type(evento) for evento in recebidos] == [ReservaCriada, AssentoBloqueado]


def test_barramento_propaga_erro_do_tratador():
    barramento = Barramento()

    def falhar(_evento: ReservaCriada) -> None:
        raise RuntimeError("falha de teste")

    barramento.inscrever(ReservaCriada, falhar)

    with pytest.raises(RuntimeError, match="falha de teste"):
        barramento.publicar(ReservaCriada(1, 2, "12A", 3, Decimal("100.00")))


def test_passageiro_falso_e_substituido_no_container():
    container = iniciar("sqlite:///:memory:")
    assert isinstance(container.passageiros, PassageiroFalso)
    assert container.passageiros.obter_identificador("Ana", "123") == 1
    assert container.passageiros.obter_identificador("Ana Costa", " 123 ") == 1
    assert container.passageiros.obter_identificador("Bruno", "456") == 2
    with pytest.raises(ValueError, match="documento"):
        container.passageiros.obter_identificador("Ana", " ")

    class PassageirosFixos:
        def obter_identificador(self, nome: str, documento: str) -> int:
            del nome, documento
            return 99

    container.registrar_passageiros(PassageirosFixos())
    assert container.passageiros.obter_identificador("Ana", "123") == 99


def test_carregar_modulos_executa_somente_quem_define_registrar():
    container = criar_container("sqlite:///:memory:")

    class ModuloSemRegistro:
        pass

    class ModuloComRegistro:
        def registrar(self, destino: Container) -> None:
            destino.registrar_passageiros(PassageiroFalso())

    assert aplicar_registro(ModuloSemRegistro(), container) is False
    assert aplicar_registro(ModuloComRegistro(), container) is True
    assert carregar_modulos(container) == []
