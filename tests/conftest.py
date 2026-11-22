from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import criar_app

CABECALHOS = {"X-Requested-With": "fetch"}
SENHA = "Senha12345"


@pytest.fixture
def sistema(tmp_path):
    def montar(*modulos: str) -> SimpleNamespace:
        app = criar_app(f"sqlite:///{tmp_path / 'teste.db'}", ("contas", *modulos))
        bus = app.state.bus
        container = app.state.container
        eventos = []
        publicar = bus.publicar

        def registrar_e_publicar(evento) -> None:
            eventos.append(evento)
            publicar(evento)

        bus.publicar = registrar_e_publicar

        def publicados(tipo) -> list:
            return [evento for evento in eventos if isinstance(evento, tipo)]

        def cliente(email: str = "ana@exemplo.com", nome: str = "Ana Souza") -> TestClient:
            conectado = TestClient(app, headers=CABECALHOS)
            resposta = conectado.post(
                "/auth/cadastro", json={"nome": nome, "email": email, "senha": SENHA, "aceite_termos": True}
            )
            assert resposta.status_code == 201, resposta.text
            return conectado

        def admin(email: str = "admin@elvoo.com") -> TestClient:
            container.autenticacao.criar_admin("Administrador", email, SENHA)
            conectado = TestClient(app, headers=CABECALHOS)
            assert conectado.post("/auth/entrar", json={"email": email, "senha": SENHA}).status_code == 200
            return conectado

        return SimpleNamespace(
            client=TestClient(app, headers=CABECALHOS),
            bus=bus,
            container=container,
            publicados=publicados,
            cliente=cliente,
            admin=admin,
        )

    return montar
