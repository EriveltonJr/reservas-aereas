from app.barramento import Barramento
from app.eventos import (
    AssentoIndisponivel,
    CancelamentoSolicitado,
    CancelarReserva,
    LiberarAssento,
    PrazoPagamentoExpirado,
)

MOTIVO_PRAZO_EXPIRADO = "Prazo para pagamento expirado"


class SagaService:
    def __init__(self, bus: Barramento) -> None:
        self.bus = bus

    def ao_assento_indisponivel(self, evento: AssentoIndisponivel) -> None:
        self.bus.publicar(CancelarReserva(reserva_id=evento.reserva_id, motivo=evento.motivo))

    def ao_prazo_expirado(self, evento: PrazoPagamentoExpirado) -> None:
        self._desfazer(evento.reserva_id, MOTIVO_PRAZO_EXPIRADO)

    def ao_cancelamento_solicitado(self, evento: CancelamentoSolicitado) -> None:
        self._desfazer(evento.reserva_id, evento.motivo)

    def _desfazer(self, reserva_id: int, motivo: str) -> None:
        self.bus.publicar(LiberarAssento(reserva_id=reserva_id))
        self.bus.publicar(CancelarReserva(reserva_id=reserva_id, motivo=motivo))
