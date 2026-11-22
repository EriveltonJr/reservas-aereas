import secrets
import threading
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.banco import agora, sessao
from app.contratos import UsuarioAutenticado
from app.modulos.contas.models import ADMIN, CLIENTE, Sessao, Usuario
from app.politicas import BLOQUEIO_LOGIN_MINUTOS, SESSAO_HORAS, TENTATIVAS_LOGIN
from app.seguranca import gerar_hash_senha, hash_token, verificar_senha

_HASH_FICTICIO = gerar_hash_senha(secrets.token_hex(16))


class ContaJaExiste(Exception):
    pass


class CredenciaisInvalidas(Exception):
    pass


class MuitasTentativas(Exception):
    def __init__(self, minutos: int) -> None:
        super().__init__(minutos)
        self.minutos = minutos


def _publico(usuario: Usuario) -> dict:
    return {"id": usuario.id, "nome": usuario.nome, "email": usuario.email, "papel": usuario.papel}


class ContaService:
    def __init__(self) -> None:
        self._falhas: dict[str, list] = {}
        self._trava = threading.Lock()

    def cadastrar(self, nome: str, email: str, senha: str, papel: str = CLIENTE) -> dict:
        usuario = Usuario(nome=nome.strip(), email=email.strip().lower(), senha_hash=gerar_hash_senha(senha), papel=papel)
        with sessao() as s:
            try:
                s.add(usuario)
                s.commit()
            except IntegrityError as erro:
                raise ContaJaExiste from erro
            return _publico(usuario)

    def criar_admin(self, nome: str, email: str, senha: str) -> dict:
        email = email.strip().lower()
        with sessao() as s:
            usuario = s.scalar(select(Usuario).where(Usuario.email == email))
            if usuario is None:
                usuario = Usuario(nome=nome.strip(), email=email)
                s.add(usuario)
            usuario.senha_hash = gerar_hash_senha(senha)
            usuario.papel = ADMIN
            s.commit()
            return _publico(usuario)

    def entrar(self, email: str, senha: str) -> tuple[str, dict]:
        email = email.strip().lower()
        self._verificar_bloqueio(email)
        with sessao() as s:
            usuario = s.scalar(select(Usuario).where(Usuario.email == email))
            valida = verificar_senha(senha, usuario.senha_hash if usuario else _HASH_FICTICIO)
            if usuario is None or not valida:
                self._registrar_falha(email)
                raise CredenciaisInvalidas
            self._limpar_falhas(email)
            token = secrets.token_urlsafe(32)
            s.execute(delete(Sessao).where(Sessao.usuario_id == usuario.id, Sessao.expira_em < agora()))
            s.add(Sessao(token_hash=hash_token(token), usuario_id=usuario.id,
                         expira_em=agora() + timedelta(hours=SESSAO_HORAS)))
            s.commit()
            return token, _publico(usuario)

    def sair(self, token: str) -> None:
        with sessao() as s:
            s.execute(delete(Sessao).where(Sessao.token_hash == hash_token(token)))
            s.commit()

    def usuario_por_token(self, token: str) -> UsuarioAutenticado | None:
        with sessao() as s:
            linha = s.execute(
                select(Usuario)
                .join(Sessao, Sessao.usuario_id == Usuario.id)
                .where(Sessao.token_hash == hash_token(token), Sessao.expira_em > agora())
            ).scalar_one_or_none()
            if linha is None:
                return None
            return UsuarioAutenticado(linha.id, linha.nome, linha.email, linha.papel)

    def _verificar_bloqueio(self, email: str) -> None:
        limite = agora() - timedelta(minutes=BLOQUEIO_LOGIN_MINUTOS)
        with self._trava:
            recentes = [momento for momento in self._falhas.get(email, []) if momento > limite]
            self._falhas[email] = recentes
            if len(recentes) >= TENTATIVAS_LOGIN:
                restante = recentes[0] + timedelta(minutes=BLOQUEIO_LOGIN_MINUTOS) - agora()
                raise MuitasTentativas(max(1, round(restante.total_seconds() / 60)))

    def _registrar_falha(self, email: str) -> None:
        with self._trava:
            self._falhas.setdefault(email, []).append(agora())

    def _limpar_falhas(self, email: str) -> None:
        with self._trava:
            self._falhas.pop(email, None)
