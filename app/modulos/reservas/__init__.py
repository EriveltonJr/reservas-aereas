from app.eventos import CancelarReserva, PagamentoAprovado
from app.modulos.reservas import models
from app.modulos.reservas.routes import criar_router
from app.modulos.reservas.service import ReservaService


def registrar(app, bus, container) -> None:
    servico = ReservaService(bus, container)
    app.include_router(criar_router(servico))
    bus.inscrever(PagamentoAprovado, servico.ao_pagamento_aprovado)
    bus.inscrever(CancelarReserva, servico.ao_cancelar_reserva)
