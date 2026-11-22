from app.barramento import Barramento
from app.eventos import (
    AssentoIndisponivel,
    CancelarReserva,
    LiberarAssento,
    PagamentoRecusado,
)

class SagaService:
    def __init__(self, bus: Barramento) -> None:
        self.bus = bus

    def ao_assento_indisponivel(self, evento: AssentoIndisponivel) -> None:
        self.bus.publicar(CancelarReserva(reserva_id=evento.reserva_id, motivo=evento.motivo))

    def ao_pagamento_recusado(self, evento: PagamentoRecusado) -> None:
        self.bus.publicar(LiberarAssento(reserva_id=evento.reserva_id))

        self.bus.publicar(CancelarReserva(reserva_id=evento.reserva_id, motivo=evento.motivo))
