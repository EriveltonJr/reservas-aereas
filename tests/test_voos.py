from app.eventos import AssentoBloqueado, AssentoIndisponivel, LiberarAssento, ReservaCriada
from tests.apoio import assentos, dados_voo


def test_criar_listar_e_consultar_voo(sistema):
    s = sistema("voos")
    admin = s.admin()

    resposta = admin.post("/voos", json=dados_voo(codigo="el123"))
    assert resposta.status_code == 201
    criado = resposta.json()
    assert criado["codigo"] == "EL123"
    assert criado["partida"] and criado["chegada"]

    lista = s.client.get("/voos").json()
    assert lista[0]["assentos_livres"] == 2
    assert assentos(s.client, criado["id"]) == {"1A": "LIVRE", "1B": "LIVRE"}
    assert s.client.get("/voos/999").status_code == 404


def test_somente_admin_cadastra_e_altera_preco(sistema):
    s = sistema("voos")
    admin = s.admin()
    voo_id = admin.post("/voos", json=dados_voo()).json()["id"]

    assert s.client.post("/voos", json=dados_voo(codigo="EL200")).status_code == 401
    assert s.cliente().post("/voos", json=dados_voo(codigo="EL200")).status_code == 403

    resposta = admin.patch(f"/voos/{voo_id}", json={"preco": 899.9})
    assert resposta.status_code == 200
    assert resposta.json()["preco"] == 899.9
    assert admin.patch("/voos/999", json={"preco": 10}).status_code == 404


def test_codigo_repetido_da_409(sistema):
    s = sistema("voos")
    admin = s.admin()

    assert admin.post("/voos", json=dados_voo()).status_code == 201
    resposta = admin.post("/voos", json=dados_voo())

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Já existe um voo com esse código"


def test_entrada_invalida_da_422(sistema):
    s = sistema("voos")
    admin = s.admin()

    assert admin.post("/voos", json=dados_voo(preco=0)).status_code == 422
    assert admin.post("/voos", json=dados_voo(assentos=["1A", "1A"])).status_code == 422
    assert admin.post("/voos", json=dados_voo(assentos=["XX"])).status_code == 422
    assert admin.post("/voos", json=dados_voo(assentos=[])).status_code == 422
    assert admin.post("/voos", json=dados_voo(dias=-1)).status_code == 422
    assert admin.post("/voos", json=dados_voo(destino="Fortaleza")).status_code == 422


def test_voo_encerrado_nao_aparece_e_nao_vende(sistema):
    s = sistema("voos")
    admin = s.admin()
    voo_id = admin.post("/voos", json=dados_voo(dias=0.05)).json()["id"]

    assert s.client.get("/voos").json() == []
    assert len(admin.get("/voos", params={"incluir_encerrados": True}).json()) == 1

    s.bus.publicar(ReservaCriada(1, voo_id, "1A", 10))

    assert s.publicados(AssentoIndisponivel) == [AssentoIndisponivel(1, "Vendas encerradas para este voo")]


def test_reserva_criada_bloqueia_assento(sistema):
    s = sistema("voos")
    voo_id = s.admin().post("/voos", json=dados_voo(preco=1234.5)).json()["id"]

    s.bus.publicar(ReservaCriada(1, voo_id, "1A", 10))

    assert s.publicados(AssentoBloqueado) == [AssentoBloqueado(1, voo_id, "1A", 1234.5)]
    assert assentos(s.client, voo_id)["1A"] == "BLOQUEADO"


def test_assento_ocupado_ou_inexistente_fica_indisponivel(sistema):
    s = sistema("voos")
    voo_id = s.admin().post("/voos", json=dados_voo()).json()["id"]

    s.bus.publicar(ReservaCriada(1, voo_id, "1A", 10))
    s.bus.publicar(ReservaCriada(2, voo_id, "1A", 11))
    s.bus.publicar(ReservaCriada(3, voo_id, "9Z", 12))
    s.bus.publicar(ReservaCriada(4, 999, "1A", 13))

    assert len(s.publicados(AssentoBloqueado)) == 1
    indisponiveis = s.publicados(AssentoIndisponivel)
    assert [e.reserva_id for e in indisponiveis] == [2, 3, 4]


def test_liberar_assento_volta_a_livre(sistema):
    s = sistema("voos")
    voo_id = s.admin().post("/voos", json=dados_voo()).json()["id"]
    s.bus.publicar(ReservaCriada(1, voo_id, "1A", 10))

    s.bus.publicar(LiberarAssento(1))
    s.bus.publicar(LiberarAssento(99))

    assert assentos(s.client, voo_id)["1A"] == "LIVRE"
