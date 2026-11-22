from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import AwareDatetime, BaseModel, Field, StringConstraints, field_validator, model_validator

from app.contratos import UsuarioAutenticado
from app.modulos.voos.service import VooJaExiste, VooService
from app.seguranca import exigir_admin, usuario_opcional

NumeroAssento = Annotated[str, StringConstraints(pattern=r"^[0-9]{1,3}[A-Z]$")]
Preco = Annotated[float, Field(gt=0, le=100000)]


class VooIn(BaseModel):
    codigo: str = Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9]+$")
    origem: str = Field(min_length=3, max_length=50)
    destino: str = Field(min_length=3, max_length=50)
    preco: Preco
    partida: AwareDatetime
    chegada: AwareDatetime
    assentos: list[NumeroAssento] = Field(min_length=1, max_length=300)

    @field_validator("assentos")
    @classmethod
    def sem_repeticao(cls, assentos: list[str]) -> list[str]:
        if len(set(assentos)) != len(assentos):
            raise ValueError("assentos repetidos")
        return assentos

    @field_validator("partida")
    @classmethod
    def partida_futura(cls, partida: datetime) -> datetime:
        if partida <= datetime.now(UTC):
            raise ValueError("A partida precisa ser no futuro")
        return partida

    @model_validator(mode="after")
    def horarios_coerentes(self) -> "VooIn":
        if self.origem.strip().lower() == self.destino.strip().lower():
            raise ValueError("Origem e destino precisam ser diferentes")
        if not timedelta(minutes=20) <= self.chegada - self.partida <= timedelta(hours=24):
            raise ValueError("A chegada precisa ser entre 20 minutos e 24 horas depois da partida")
        return self


class PrecoIn(BaseModel):
    preco: Preco


def criar_router(servico: VooService) -> APIRouter:
    router = APIRouter(prefix="/voos", tags=["voos"])

    @router.post("", status_code=status.HTTP_201_CREATED)
    def criar_voo(dados: VooIn, _admin: UsuarioAutenticado = Depends(exigir_admin)) -> dict:
        try:
            return servico.criar(
                dados.codigo, dados.origem, dados.destino, dados.preco, dados.assentos, dados.partida, dados.chegada
            )
        except VooJaExiste:
            raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um voo com esse código")

    @router.get("")
    def listar_voos(
        incluir_encerrados: bool = False,
        usuario: UsuarioAutenticado | None = Depends(usuario_opcional),
    ) -> list[dict]:
        return servico.listar(incluir_encerrados and usuario is not None and usuario.admin)

    @router.get("/{voo_id}")
    def obter_voo(voo_id: int) -> dict:
        voo = servico.obter(voo_id)
        if voo is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Voo não encontrado")
        return voo

    @router.patch("/{voo_id}")
    def alterar_preco(voo_id: int, dados: PrecoIn, _admin: UsuarioAutenticado = Depends(exigir_admin)) -> dict:
        voo = servico.atualizar_preco(voo_id, dados.preco)
        if voo is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Voo não encontrado")
        return voo

    return router
