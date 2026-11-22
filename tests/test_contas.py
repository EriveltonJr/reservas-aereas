from sqlalchemy import select

from app.banco import sessao
from app.modulos.contas.models import Usuario
from app.seguranca import gerar_hash_senha, verificar_senha
from tests.conftest import SENHA


def cadastro(email="ana@exemplo.com", senha=SENHA, aceite=True) -> dict:
    return {"nome": "Ana Souza", "email": email, "senha": senha, "aceite_termos": aceite}


def test_cadastro_entra_e_guarda_senha_com_hash(sistema):
    s = sistema()

    resposta = s.client.post("/auth/cadastro", json=cadastro(email="Ana@Exemplo.com"))

    assert resposta.status_code == 201
    assert resposta.json()["papel"] == "CLIENTE"
    assert "senha" not in resposta.text
    cookie = resposta.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert s.client.get("/auth/eu").json()["email"] == "ana@exemplo.com"
    with sessao() as banco:
        guardado = banco.scalar(select(Usuario.senha_hash))
    assert guardado.startswith("scrypt$") and SENHA not in guardado


def test_cadastro_rejeita_dados_fracos_e_email_repetido(sistema):
    s = sistema()

    assert s.client.post("/auth/cadastro", json=cadastro(senha="curta1")).status_code == 422
    assert s.client.post("/auth/cadastro", json=cadastro(senha="somenteletras")).status_code == 422
    assert s.client.post("/auth/cadastro", json=cadastro(aceite=False)).status_code == 422
    assert s.client.post("/auth/cadastro", json=cadastro()).status_code == 201
    resposta = s.client.post("/auth/cadastro", json=cadastro())
    assert resposta.status_code == 409


def test_login_e_logout(sistema):
    s = sistema()
    s.cliente()

    assert s.client.post("/auth/entrar", json={"email": "ana@exemplo.com", "senha": "errada123"}).status_code == 401
    assert s.client.post("/auth/entrar", json={"email": "ana@exemplo.com", "senha": SENHA}).status_code == 200
    assert s.client.get("/auth/eu").status_code == 200
    assert s.client.post("/auth/sair").status_code == 204
    assert s.client.get("/auth/eu").status_code == 401


def test_erro_de_login_nao_revela_se_o_email_existe(sistema):
    s = sistema()
    s.cliente()

    existente = s.client.post("/auth/entrar", json={"email": "ana@exemplo.com", "senha": "errada123"})
    inexistente = s.client.post("/auth/entrar", json={"email": "nao@existe.com", "senha": "errada123"})

    assert existente.json() == inexistente.json() == {"detail": "E-mail ou senha inválidos"}


def test_bloqueia_apos_tentativas_erradas(sistema):
    s = sistema()
    s.cliente()
    errado = {"email": "ana@exemplo.com", "senha": "errada123"}

    for _ in range(5):
        assert s.client.post("/auth/entrar", json=errado).status_code == 401
    bloqueado = s.client.post("/auth/entrar", json={"email": "ana@exemplo.com", "senha": SENHA})

    assert bloqueado.status_code == 429


def test_requisicao_sem_cabecalho_de_origem_e_recusada(sistema):
    s = sistema()
    s.cliente()
    from fastapi.testclient import TestClient

    sem_cabecalho = TestClient(s.client.app)

    assert sem_cabecalho.post("/auth/entrar", json={"email": "ana@exemplo.com", "senha": SENHA}).status_code == 403


def test_hash_de_senha():
    armazenado = gerar_hash_senha("Senha12345")

    assert verificar_senha("Senha12345", armazenado)
    assert not verificar_senha("Senha12346", armazenado)
    assert gerar_hash_senha("Senha12345") != armazenado
