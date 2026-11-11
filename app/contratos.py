import importlib
import pkgutil
from typing import Protocol

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.banco import criar_engine, criar_sessoes, criar_tabelas
from app.barramento import Barramento

ORDEM_MODULOS = (
    "passageiros",
    "voos",
    "reservas",
    "pagamentos",
    "notificacoes",
    "saga",
)


class PassageirosContrato(Protocol):
    def obter_identificador(self, nome: str, documento: str) -> int:
        """Retorna o identificador do passageiro. Única chamada direta entre módulos."""


class PassageiroFalso:
    """Substituto até o módulo Passageiros de Liedson chamar registrar_passageiros."""

    def __init__(self) -> None:
        self._por_documento: dict[str, int] = {}

    def obter_identificador(self, nome: str, documento: str) -> int:
        del nome
        documento_limpo = documento.strip()
        if not documento_limpo:
            raise ValueError("documento do passageiro é obrigatório")
        if documento_limpo not in self._por_documento:
            self._por_documento[documento_limpo] = len(self._por_documento) + 1
        return self._por_documento[documento_limpo]


class Container:
    def __init__(
        self,
        engine: Engine,
        sessoes: sessionmaker[Session],
        barramento: Barramento,
        passageiros: PassageirosContrato,
    ) -> None:
        self.engine = engine
        self.sessoes = sessoes
        self.barramento = barramento
        self.passageiros = passageiros

    def registrar_passageiros(self, servico: PassageirosContrato) -> None:
        if not callable(getattr(servico, "obter_identificador", None)):
            raise TypeError("o serviço de passageiros deve implementar obter_identificador")
        self.passageiros = servico


def criar_container(url: str | None = None) -> Container:
    engine = criar_engine(url)
    return Container(
        engine=engine,
        sessoes=criar_sessoes(engine),
        barramento=Barramento(),
        passageiros=PassageiroFalso(),
    )


def aplicar_registro(modulo: object, container: Container) -> bool:
    registrar = getattr(modulo, "registrar", None)
    if not callable(registrar):
        return False
    registrar(container)
    return True


def carregar_modulos(container: Container) -> list[str]:
    """Importa app.modulos e executa registrar(container) quando o pacote definir essa função.

    Liedson: coloque registrar(container) no __init__ do módulo. Não altere app/main.py.
    Leia container.passageiros na hora da reserva, não durante o registro.
    """
    import app.modulos as pacote

    encontrados = {modulo.name for modulo in pkgutil.iter_modules(pacote.__path__)}
    ordem = [nome for nome in ORDEM_MODULOS if nome in encontrados]
    ordem.extend(sorted(encontrados - set(ordem)))

    carregados: list[str] = []
    for nome in ordem:
        modulo = importlib.import_module(f"app.modulos.{nome}")
        if aplicar_registro(modulo, container):
            carregados.append(nome)
    return carregados


def iniciar(url: str | None = None) -> Container:
    container = criar_container(url)
    carregar_modulos(container)
    criar_tabelas(container.engine)
    return container
