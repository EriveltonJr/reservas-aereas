from fastapi import APIRouter, Depends, status

from app.contratos import UsuarioAutenticado
from app.eventos import PagamentoEstornado, PagamentoRecusado, ReservaCancelada, ReservaConfirmada, ReservaCriada
from app.modulos.notificacoes import models
from app.modulos.notificacoes.service import NotificacaoService
from app.seguranca import exigir_usuario


def registrar(app, bus, container) -> None:
    del container
    servico = NotificacaoService()
    bus.inscrever(ReservaCriada, servico.ao_reserva_criada)
    bus.inscrever(ReservaConfirmada, servico.ao_reserva_confirmada)
    bus.inscrever(PagamentoRecusado, servico.ao_pagamento_recusado)
    bus.inscrever(ReservaCancelada, servico.ao_reserva_cancelada)
    bus.inscrever(PagamentoEstornado, servico.ao_pagamento_estornado)

    router = APIRouter(prefix="/notificacoes", tags=["notificacoes"])

    @router.get("")
    def listar(usuario: UsuarioAutenticado = Depends(exigir_usuario)) -> dict:
        return servico.listar(usuario)

    @router.post("/lidas", status_code=status.HTTP_204_NO_CONTENT)
    def marcar_todas(usuario: UsuarioAutenticado = Depends(exigir_usuario)) -> None:
        servico.marcar_lidas(usuario)

    @router.post("/{notificacao_id}/lida", status_code=status.HTTP_204_NO_CONTENT)
    def marcar_uma(notificacao_id: int, usuario: UsuarioAutenticado = Depends(exigir_usuario)) -> None:
        servico.marcar_lidas(usuario, notificacao_id)

    app.include_router(router)
