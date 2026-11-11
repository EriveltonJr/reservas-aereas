from dataclasses import dataclass
from decimal import Decimal


class Evento:
    @property
    def nome(self) -> str:
        return type(self).__name__


@dataclass(frozen=True)
class ReservaCriada(Evento):
    reserva_id: int
    voo_id: int
    codigo_assento: str
    passageiro_id: int
    valor: Decimal


@dataclass(frozen=True)
class AssentoBloqueado(Evento):
    reserva_id: int
    voo_id: int
    codigo_assento: str


@dataclass(frozen=True)
class AssentoIndisponivel(Evento):
    reserva_id: int
    voo_id: int
    codigo_assento: str
    motivo: str


@dataclass(frozen=True)
class PagamentoAprovado(Evento):
    reserva_id: int
    pagamento_id: int
    valor: Decimal


@dataclass(frozen=True)
class PagamentoRecusado(Evento):
    reserva_id: int
    motivo: str


@dataclass(frozen=True)
class ReservaConfirmada(Evento):
    reserva_id: int


@dataclass(frozen=True)
class LiberarAssento(Evento):
    reserva_id: int
    voo_id: int
    codigo_assento: str


@dataclass(frozen=True)
class CancelarReserva(Evento):
    reserva_id: int
    motivo: str


@dataclass(frozen=True)
class ReservaCancelada(Evento):
    reserva_id: int
    motivo: str
