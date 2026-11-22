from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.contratos import UsuarioAutenticado
from app.modulos.pagamentos import gateway
from app.modulos.pagamentos.service import (
    CobrancaNaoEncontrada,
    PagamentoIndisponivel,
    PagamentoNegado,
    PagamentoService,
)
from app.seguranca import exigir_admin, exigir_usuario

NAO_ENCONTRADO = "Pagamento não encontrado"


class CartaoIn(BaseModel):
    titular: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-zÀ-ÿ' ]+$")
    numero: str = Field(min_length=13, max_length=23)
    validade: str = Field(pattern=r"^(0[1-9]|1[0-2])/\d{2}$")
    cvv: str = Field(pattern=r"^\d{3,4}$")

    @field_validator("numero")
    @classmethod
    def numero_valido(cls, numero: str) -> str:
        digitos = gateway.somente_digitos(numero)
        if not 13 <= len(digitos) <= 19 or not gateway.luhn_valido(digitos):
            raise ValueError("Número de cartão inválido")
        if gateway.bandeira(digitos) is None:
            raise ValueError("Bandeira não aceita")
        return digitos

    @field_validator("validade")
    @classmethod
    def validade_futura(cls, validade: str) -> str:
        mes, ano = validade.split("/")
        hoje = date.today()
        if (2000 + int(ano), int(mes)) < (hoje.year, hoje.month):
            raise ValueError("Cartão vencido")
        return validade

    @model_validator(mode="after")
    def cvv_compativel(self) -> "CartaoIn":
        esperado = 4 if gateway.bandeira(self.numero) == "American Express" else 3
        if len(self.cvv) != esperado:
            raise ValueError("Código de segurança inválido")
        return self


def criar_router(servico: PagamentoService) -> APIRouter:
    router = APIRouter(prefix="/pagamentos", tags=["pagamentos"])

    @router.get("")
    def listar(_admin: UsuarioAutenticado = Depends(exigir_admin)) -> list[dict]:
        return servico.listar()

    @router.get("/{reserva_id}")
    def obter(reserva_id: int, usuario: UsuarioAutenticado = Depends(exigir_usuario)) -> dict:
        try:
            return servico.obter(reserva_id, usuario)
        except CobrancaNaoEncontrada:
            raise HTTPException(status.HTTP_404_NOT_FOUND, NAO_ENCONTRADO)

    @router.post("/{reserva_id}")
    def pagar(reserva_id: int, cartao: CartaoIn, usuario: UsuarioAutenticado = Depends(exigir_usuario)) -> dict:
        try:
            return servico.pagar(reserva_id, usuario, cartao.numero)
        except CobrancaNaoEncontrada:
            raise HTTPException(status.HTTP_404_NOT_FOUND, NAO_ENCONTRADO)
        except PagamentoIndisponivel as erro:
            raise HTTPException(status.HTTP_409_CONFLICT, str(erro))
        except PagamentoNegado as erro:
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, str(erro))

    return router
