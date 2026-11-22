from starlette.concurrency import run_in_threadpool

from app.eventos import AssentoBloqueado, ReservaCancelada, ReservaCriada
from app.modulos.pagamentos import models
from app.modulos.pagamentos.routes import criar_router
from app.modulos.pagamentos.service import PagamentoService


def registrar(app, bus, container):
    servico = PagamentoService(bus)
    app.include_router(criar_router(servico))
    bus.inscrever(ReservaCriada, servico.ao_reserva_criada)
    bus.inscrever(AssentoBloqueado, servico.ao_assento_bloqueado)
    bus.inscrever(ReservaCancelada, servico.ao_reserva_cancelada)

    @app.middleware("http")
    async def expirar_pagamentos(request, chamar_proximo):
        if not request.url.path.startswith("/static"):
            await run_in_threadpool(servico.expirar_vencidas)
        return await chamar_proximo(request)
