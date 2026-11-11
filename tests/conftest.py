from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import criar_app


@pytest.fixture
def sistema(tmp_path):
    def montar(*modulos: str) -> SimpleNamespace:
        app = criar_app(f"sqlite:///{tmp_path / 'teste.db'}", modulos)
        bus = app.state.bus
        eventos = []
        publicar = bus.publicar

        def registrar_e_publicar(evento) -> None:
            eventos.append(evento)
            publicar(evento)

        bus.publicar = registrar_e_publicar

        def publicados(tipo) -> list:
            return [evento for evento in eventos if isinstance(evento, tipo)]

        return SimpleNamespace(
            client=TestClient(app),
            bus=bus,
            container=app.state.container,
            publicados=publicados,
        )

    return montar
