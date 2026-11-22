import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from app.contratos import UsuarioAutenticado
from app.modulos.contas.service import ContaJaExiste, ContaService, CredenciaisInvalidas, MuitasTentativas
from app.seguranca import (
    COOKIE_SESSAO,
    apagar_cookie_sessao,
    exigir_origem_propria,
    exigir_usuario,
    gravar_cookie_sessao,
)

PADRAO_EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def validar_senha(senha: str) -> str:
    if not re.search(r"[A-Za-z]", senha) or not re.search(r"\d", senha):
        raise ValueError("A senha precisa ter letras e números")
    return senha


class CadastroIn(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=120, pattern=PADRAO_EMAIL)
    senha: str = Field(min_length=8, max_length=128)
    aceite_termos: bool

    @field_validator("senha")
    @classmethod
    def senha_forte(cls, senha: str) -> str:
        return validar_senha(senha)

    @field_validator("aceite_termos")
    @classmethod
    def termos_aceitos(cls, aceite: bool) -> bool:
        if not aceite:
            raise ValueError("É preciso aceitar os termos de uso e a política de privacidade")
        return aceite


class EntrarIn(BaseModel):
    email: str = Field(max_length=120)
    senha: str = Field(max_length=128)


def criar_router(servico: ContaService) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["contas"], dependencies=[Depends(exigir_origem_propria)])

    @router.post("/cadastro", status_code=status.HTTP_201_CREATED)
    def cadastrar(dados: CadastroIn, request: Request, resposta: Response) -> dict:
        try:
            servico.cadastrar(dados.nome, dados.email, dados.senha)
        except ContaJaExiste:
            raise HTTPException(status.HTTP_409_CONFLICT, "Já existe uma conta com esse e-mail")
        token, usuario = servico.entrar(dados.email, dados.senha)
        gravar_cookie_sessao(resposta, request, token)
        return usuario

    @router.post("/entrar")
    def entrar(dados: EntrarIn, request: Request, resposta: Response) -> dict:
        try:
            token, usuario = servico.entrar(dados.email, dados.senha)
        except MuitasTentativas as erro:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Muitas tentativas. Tente novamente em {erro.minutos} minuto(s).",
            )
        except CredenciaisInvalidas:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha inválidos")
        gravar_cookie_sessao(resposta, request, token)
        return usuario

    @router.post("/sair", status_code=status.HTTP_204_NO_CONTENT)
    def sair(request: Request, resposta: Response) -> None:
        token = request.cookies.get(COOKIE_SESSAO)
        if token:
            servico.sair(token)
        apagar_cookie_sessao(resposta)

    @router.get("/eu")
    def eu(usuario: UsuarioAutenticado = Depends(exigir_usuario)) -> dict:
        return {"id": usuario.id, "nome": usuario.nome, "email": usuario.email, "papel": usuario.papel}

    return router
