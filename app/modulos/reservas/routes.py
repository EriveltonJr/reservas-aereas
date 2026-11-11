from fastapi import APIRouter, HTTPException, status

from app.modulos.reservas.schemas import ReservaIn
from app.modulos.reservas.service import ReservaService


def criar_router(servico: ReservaService) -> APIRouter:
    router = APIRouter(prefix="/reservas", tags=["reservas"])

    @router.post("", status_code=status.HTTP_201_CREATED)
    def criar_reserva(dados: ReservaIn) -> dict:
        passageiro = dados.passageiro
        return servico.criar(dados.voo_id, dados.assento, passageiro.nome, passageiro.documento, passageiro.email)

    @router.get("/{reserva_id}")
    def obter_reserva(reserva_id: int) -> dict:
        reserva = servico.obter(reserva_id)
        if reserva is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Reserva não encontrada")
        return reserva

    return router
