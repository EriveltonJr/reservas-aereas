import importlib
import pkgutil
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from fastapi import FastAPI
from sqlalchemy.engine import Engine

from app.barramento import Barramento

ORDEM_MODULOS = (
    "passageiros",
    "voos",
    "reservas",
    "pagamentos",
    "notificacoes",
    "saga",
)


@dataclass(frozen=True)
class DadosPassageiro:
    nome: str
    documento: str
    email: str


class PassageirosContrato(Protocol):
    def criar_ou_validar(self, dados: DadosPassageiro) -> int:
        """Cria ou valida o passageiro e devolve o identificador."""


class PassageiroFalso:
    """Implementação provisória substituível pelo serviço de Passageiros."""

    def __init__(self) -> None:
        self._por_documento: dict[str, int] = {}

    def criar_ou_validar(self, dados: DadosPassageiro) -> int:
        documento = dados.documento.strip()
        if not documento:
            raise ValueError("documento do passageiro é obrigatório")
        if documento not in self._por_documento:
            self._por_documento[documento] = len(self._por_documento) + 1
        return self._por_documento[documento]


class Container:
    def __init__(self, engine: Engine, bus: Barramento, passageiros: PassageirosContrato) -> None:
        self.engine = engine
        self.bus = bus
        self.passageiros = passageiros

    def registrar_passageiros(self, servico: PassageirosContrato) -> None:
        if not callable(getattr(servico, "criar_ou_validar", None)):
            raise TypeError("o serviço de passageiros deve implementar criar_ou_validar")
        self.passageiros = servico


def aplicar_registro(modulo: object, app: FastAPI, bus: Barramento, container: Container) -> bool:
    registrar = getattr(modulo, "registrar", None)
    if not callable(registrar):
        return False
    registrar(app, bus, container)
    return True


def carregar_modulos(
    app: FastAPI,
    bus: Barramento,
    container: Container,
    nomes: Iterable[str] | None = None,
) -> list[str]:
    """Descobre os módulos e executa registrar(app, bus, container), quando disponível."""
    import app.modulos as pacote

    encontrados = {modulo.name for modulo in pkgutil.iter_modules(pacote.__path__)}
    if nomes is not None:
        encontrados &= set(nomes)
    ordem = [nome for nome in ORDEM_MODULOS if nome in encontrados]
    ordem.extend(sorted(encontrados - set(ordem)))

    carregados: list[str] = []
    for nome in ordem:
        modulo = importlib.import_module(f"app.modulos.{nome}")
        if aplicar_registro(modulo, app, bus, container):
            carregados.append(nome)
    return carregados
