from app.eventos import LiberarAssento, ReservaCriada
from app.modulos.voos import models
from app.modulos.voos.routes import criar_router
from app.modulos.voos.service import VooService


def registrar(app, bus, container) -> None:
    servico = VooService(bus)
    app.include_router(criar_router(servico))
    bus.inscrever(ReservaCriada, servico.bloquear_assento)
    bus.inscrever(LiberarAssento, servico.liberar_assento)
