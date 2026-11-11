import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

URL_PADRAO = "sqlite:///./reservas.db"


class Base(DeclarativeBase):
    pass


def criar_engine(url: str | None = None) -> Engine:
    url = url or os.getenv("RESERVAS_DATABASE_URL", URL_PADRAO)
    argumentos: dict = {}
    if url.startswith("sqlite"):
        argumentos["connect_args"] = {"check_same_thread": False}
        if url.endswith(":memory:"):
            argumentos["poolclass"] = StaticPool
    engine = create_engine(url, **argumentos)
    if engine.dialect.name == "sqlite":
        _ativar_chaves_estrangeiras(engine)
    return engine


def criar_sessoes(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def criar_tabelas(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)


@contextmanager
def sessao_de(fabrica: sessionmaker[Session]) -> Iterator[Session]:
    sessao = fabrica()
    try:
        yield sessao
    except Exception:
        sessao.rollback()
        raise
    finally:
        sessao.close()


def _ativar_chaves_estrangeiras(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _ao_conectar(conexao, _registro) -> None:
        cursor = conexao.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
