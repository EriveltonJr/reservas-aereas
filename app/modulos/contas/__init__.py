from app.modulos.contas import models
from app.modulos.contas.routes import criar_router
from app.modulos.contas.service import ContaService


def registrar(app, bus, container) -> None:
    servico = ContaService()
    container.registrar_autenticacao(servico)
    app.include_router(criar_router(servico))
