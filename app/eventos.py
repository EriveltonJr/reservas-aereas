from dataclasses import dataclass
from decimal import Decimal


class Evento:
    @property
    def nome(self) -> str:
        return type(self).__name__


@dataclass(frozen=True)
class ReservaCriada(Evento):
    """Reservas publica. Voos bloqueia o assento. Pagamentos, Notificações e Saga também podem assinar."""

    reserva_id: int
    voo_id: int
    codigo_assento: str
    passageiro_id: int
    valor: Decimal


@dataclass(frozen=True)
class AssentoBloqueado(Evento):
    """Voos publica. Pagamentos segue com a cobrança."""

    reserva_id: int
    voo_id: int
    codigo_assento: str


@dataclass(frozen=True)
class AssentoIndisponivel(Evento):
    """Voos publica quando o assento não pode ser bloqueado."""

    reserva_id: int
    voo_id: int
    codigo_assento: str
    motivo: str


@dataclass(frozen=True)
class PagamentoAprovado(Evento):
    """Pagamentos publica. Reservas confirma a reserva."""

    reserva_id: int
    pagamento_id: int
    valor: Decimal


@dataclass(frozen=True)
class PagamentoRecusado(Evento):
    """Pagamentos publica. Saga pode compensar a reserva."""

    reserva_id: int
    motivo: str


@dataclass(frozen=True)
class ReservaConfirmada(Evento):
    """Reservas publica depois de confirmar."""

    reserva_id: int


@dataclass(frozen=True)
class LiberarAssento(Evento):
    """Saga publica. Voos libera o assento bloqueado."""

    reserva_id: int
    voo_id: int
    codigo_assento: str


@dataclass(frozen=True)
class CancelarReserva(Evento):
    """Saga publica. Reservas cancela a reserva."""

    reserva_id: int
    motivo: str


@dataclass(frozen=True)
class ReservaCancelada(Evento):
    """Reservas publica depois de cancelar."""

    reserva_id: int
    motivo: str
