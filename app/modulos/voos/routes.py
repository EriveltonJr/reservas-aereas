from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.modulos.voos.service import VooJaExiste, VooService

NumeroAssento = Annotated[str, StringConstraints(pattern=r"^[0-9]{1,3}[A-Z]$")]


class VooIn(BaseModel):
    codigo: str = Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9]+$")
    origem: str = Field(min_length=3, max_length=50)
    destino: str = Field(min_length=3, max_length=50)
    preco: float = Field(gt=0, le=100000)
    assentos: list[NumeroAssento] = Field(min_length=1, max_length=300)

    @field_validator("assentos")
    @classmethod
    def sem_repeticao(cls, assentos: list[str]) -> list[str]:
        if len(set(assentos)) != len(assentos):
            raise ValueError("assentos repetidos")
        return assentos


def criar_router(servico: VooService) -> APIRouter:
    router = APIRouter(prefix="/voos", tags=["voos"])

    @router.post("", status_code=status.HTTP_201_CREATED)
    def criar_voo(dados: VooIn) -> dict:
        try:
            return servico.criar(dados.codigo, dados.origem, dados.destino, dados.preco, dados.assentos)
        except VooJaExiste:
            raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um voo com esse código")

    @router.get("")
    def listar_voos() -> list[dict]:
        return servico.listar()

    @router.get("/{voo_id}")
    def obter_voo(voo_id: int) -> dict:
        voo = servico.obter(voo_id)
        if voo is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Voo não encontrado")
        return voo

    return router
