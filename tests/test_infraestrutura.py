from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from sqlalchemy import text

from app.banco import criar_engine, criar_sessoes, sessao_de
from app.barramento import Barramento
from app.contratos import (
    Container,
    DadosPassageiro,
    PassageiroFalso,
    aplicar_registro,
    carregar_modulos,
)
from app.eventos import AssentoBloqueado, ReservaCriada
from app.main import criar_app


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
    evento = ReservaCriada(1, 2, "12A", 3)

    barramento.publicar(evento)

    assert recebidos == [evento, evento]
    assert evento.nome == "ReservaCriada"


def test_barramento_entrega_evento_publicado_pelo_tratador():
    barramento = Barramento()
    recebidos = []

    def ao_criar(evento: ReservaCriada) -> None:
        recebidos.append(evento)
        barramento.publicar(AssentoBloqueado(evento.reserva_id, evento.voo_id, evento.assento, 100.0))

    barramento.inscrever(ReservaCriada, ao_criar)
    barramento.inscrever(AssentoBloqueado, recebidos.append)

    barramento.publicar(ReservaCriada(1, 2, "12A", 3))

    assert [type(evento) for evento in recebidos] == [ReservaCriada, AssentoBloqueado]


def test_barramento_propaga_erro_do_tratador():
    barramento = Barramento()

    def falhar(_evento: ReservaCriada) -> None:
        del _evento
        raise RuntimeError("falha de teste")

    barramento.inscrever(ReservaCriada, falhar)

    with pytest.raises(RuntimeError, match="falha de teste"):
        barramento.publicar(ReservaCriada(1, 2, "12A", 3))


def test_passageiro_falso_e_substituido_no_container():
    app = criar_app("sqlite:///:memory:", modulos=[])
    container = app.state.container
    assert isinstance(container.passageiros, PassageiroFalso)
    assert container.passageiros.criar_ou_validar(DadosPassageiro("Ana", "123", "ana@x.com")) == 1
    assert container.passageiros.criar_ou_validar(DadosPassageiro("Ana Costa", " 123 ", "ana@x.com")) == 1
    assert container.passageiros.criar_ou_validar(DadosPassageiro("Bruno", "456", "b@x.com")) == 2
    with pytest.raises(ValueError, match="documento"):
        container.passageiros.criar_ou_validar(DadosPassageiro("Ana", " ", "ana@x.com"))

    class PassageirosFixos:
        def criar_ou_validar(self, dados: DadosPassageiro) -> int:
            del dados
            return 99

    container.registrar_passageiros(PassageirosFixos())
    assert container.passageiros.criar_ou_validar(DadosPassageiro("Ana", "123", "ana@x.com")) == 99


def test_carregar_modulos_executa_somente_quem_define_registrar(monkeypatch):
    app = FastAPI()
    bus = Barramento()
    container = Container(criar_engine("sqlite:///:memory:"), bus, PassageiroFalso())
    registrados = []

    class ModuloSemRegistro:
        pass

    class ModuloComRegistro:
        def registrar(self, _app: FastAPI, _bus: Barramento, destino: Container) -> None:
            registrados.append("passageiros")
            destino.registrar_passageiros(PassageiroFalso())

    assert aplicar_registro(ModuloSemRegistro(), app, bus, container) is False
    assert aplicar_registro(ModuloComRegistro(), app, bus, container) is True
    registrados.clear()

    modulos = {
        "app.modulos.voos": ModuloSemRegistro(),
        "app.modulos.passageiros": ModuloComRegistro(),
    }
    monkeypatch.setattr(
        "app.contratos.pkgutil.iter_modules",
        lambda _: [
            SimpleNamespace(name="voos"),
            SimpleNamespace(name="passageiros"),
        ],
    )
    monkeypatch.setattr("app.contratos.importlib.import_module", lambda nome: modulos[nome])

    assert carregar_modulos(app, bus, container) == ["passageiros"]
    assert registrados == ["passageiros"]
