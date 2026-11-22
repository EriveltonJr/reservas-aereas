from fastapi import APIRouter, Depends, HTTPException, status

from app.contratos import UsuarioAutenticado
from app.modulos.reservas.schemas import ReservaIn
from app.modulos.reservas.service import CancelamentoNaoPermitido, ReservaNaoEncontrada, ReservaService
from app.seguranca import exigir_usuario

NAO_ENCONTRADA = "Reserva não encontrada"


def criar_router(servico: ReservaService) -> APIRouter:
    router = APIRouter(prefix="/reservas", tags=["reservas"])

    @router.post("", status_code=status.HTTP_201_CREATED)
    def criar_reserva(dados: ReservaIn, usuario: UsuarioAutenticado = Depends(exigir_usuario)) -> dict:
        passageiro = dados.passageiro
        return servico.criar(
            dados.voo_id, dados.assento, passageiro.nome, passageiro.documento, passageiro.email, usuario.id
        )

    @router.get("")
    def listar_reservas(usuario: UsuarioAutenticado = Depends(exigir_usuario)) -> list[dict]:
        return servico.listar(usuario)

    @router.get("/{reserva_id}")
    def obter_reserva(reserva_id: int, usuario: UsuarioAutenticado = Depends(exigir_usuario)) -> dict:
        reserva = servico.obter(reserva_id, usuario)
        if reserva is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, NAO_ENCONTRADA)
        return reserva

    @router.post("/{reserva_id}/cancelar")
    def cancelar_reserva(reserva_id: int, usuario: UsuarioAutenticado = Depends(exigir_usuario)) -> dict:
        try:
            return servico.solicitar_cancelamento(reserva_id, usuario)
        except ReservaNaoEncontrada:
            raise HTTPException(status.HTTP_404_NOT_FOUND, NAO_ENCONTRADA)
        except CancelamentoNaoPermitido as erro:
            raise HTTPException(status.HTTP_409_CONFLICT, str(erro))

    return router
