import hashlib
import hmac
import os

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status

from app.contratos import UsuarioAutenticado
from app.politicas import SESSAO_HORAS

COOKIE_SESSAO = "elvoo_sessao"
CABECALHO_CSRF = "X-Requested-With"
METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}

_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}

CSP = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "script-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


def gerar_hash_senha(senha: str) -> str:
    sal = os.urandom(16)
    chave = hashlib.scrypt(senha.encode(), salt=sal, **_SCRYPT)
    return f"scrypt${sal.hex()}${chave.hex()}"


def verificar_senha(senha: str, armazenado: str) -> bool:
    try:
        algoritmo, sal, esperado = armazenado.split("$")
    except ValueError:
        return False
    if algoritmo != "scrypt":
        return False
    chave = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(sal), **_SCRYPT)
    return hmac.compare_digest(chave.hex(), esperado)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def gravar_cookie_sessao(resposta: Response, request: Request, token: str) -> None:
    https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    resposta.set_cookie(
        COOKIE_SESSAO,
        token,
        max_age=SESSAO_HORAS * 3600,
        httponly=True,
        secure=https,
        samesite="strict",
        path="/",
    )


def apagar_cookie_sessao(resposta: Response) -> None:
    resposta.delete_cookie(COOKIE_SESSAO, path="/")


def exigir_origem_propria(request: Request) -> None:
    if request.method not in METODOS_SEGUROS and request.headers.get(CABECALHO_CSRF) != "fetch":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requisição não permitida")


def usuario_opcional(request: Request) -> UsuarioAutenticado | None:
    token = request.cookies.get(COOKIE_SESSAO)
    autenticacao = request.app.state.container.autenticacao
    if not token or autenticacao is None:
        return None
    return autenticacao.usuario_por_token(token)


def exigir_usuario(
    request: Request,
    usuario: UsuarioAutenticado | None = Depends(usuario_opcional),
) -> UsuarioAutenticado:
    if usuario is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Faça login para continuar")
    exigir_origem_propria(request)
    return usuario


def exigir_admin(usuario: UsuarioAutenticado = Depends(exigir_usuario)) -> UsuarioAutenticado:
    if not usuario.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito ao administrador")
    return usuario


def aplicar_cabecalhos_de_seguranca(app: FastAPI) -> None:
    @app.middleware("http")
    async def cabecalhos(request: Request, chamar_proximo):
        resposta = await chamar_proximo(request)
        resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
        resposta.headers.setdefault("X-Frame-Options", "DENY")
        resposta.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resposta.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            resposta.headers.setdefault("Content-Security-Policy", CSP)
        if request.url.path.startswith(("/auth", "/reservas", "/pagamentos", "/notificacoes")):
            resposta.headers.setdefault("Cache-Control", "no-store")
        return resposta
