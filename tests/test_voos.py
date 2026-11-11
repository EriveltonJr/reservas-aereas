from app.eventos import AssentoBloqueado, AssentoIndisponivel, LiberarAssento, ReservaCriada


def voo(codigo="AB123", preco=500.0, assentos=("1A", "1B")) -> dict:
    return {
        "codigo": codigo,
        "origem": "Fortaleza",
        "destino": "Recife",
        "preco": preco,
        "assentos": list(assentos),
    }


def assentos(client, voo_id: int) -> dict:
    return {a["numero"]: a["status"] for a in client.get(f"/voos/{voo_id}").json()["assentos"]}


def test_criar_listar_e_consultar_voo(sistema):
    s = sistema("voos")

    resposta = s.client.post("/voos", json=voo(codigo="ab123"))
    assert resposta.status_code == 201
    criado = resposta.json()
    assert criado["codigo"] == "AB123"

    lista = s.client.get("/voos").json()
    assert lista[0]["assentos_livres"] == 2
    assert assentos(s.client, criado["id"]) == {"1A": "LIVRE", "1B": "LIVRE"}
    assert s.client.get("/voos/999").status_code == 404


def test_codigo_repetido_da_409(sistema):
    s = sistema("voos")

    assert s.client.post("/voos", json=voo()).status_code == 201
    resposta = s.client.post("/voos", json=voo())

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Já existe um voo com esse código"


def test_entrada_invalida_da_422(sistema):
    s = sistema("voos")

    assert s.client.post("/voos", json=voo(preco=0)).status_code == 422
    assert s.client.post("/voos", json=voo(assentos=["1A", "1A"])).status_code == 422
    assert s.client.post("/voos", json=voo(assentos=["XX"])).status_code == 422
    assert s.client.post("/voos", json=voo(assentos=[])).status_code == 422


def test_reserva_criada_bloqueia_assento(sistema):
    s = sistema("voos")
    voo_id = s.client.post("/voos", json=voo(preco=1234.5)).json()["id"]

    s.bus.publicar(ReservaCriada(1, voo_id, "1A", 10))

    assert s.publicados(AssentoBloqueado) == [AssentoBloqueado(1, voo_id, "1A", 1234.5)]
    assert assentos(s.client, voo_id)["1A"] == "BLOQUEADO"


def test_assento_ocupado_ou_inexistente_fica_indisponivel(sistema):
    s = sistema("voos")
    voo_id = s.client.post("/voos", json=voo()).json()["id"]

    s.bus.publicar(ReservaCriada(1, voo_id, "1A", 10))
    s.bus.publicar(ReservaCriada(2, voo_id, "1A", 11))
    s.bus.publicar(ReservaCriada(3, voo_id, "9Z", 12))
    s.bus.publicar(ReservaCriada(4, 999, "1A", 13))

    assert len(s.publicados(AssentoBloqueado)) == 1
    indisponiveis = s.publicados(AssentoIndisponivel)
    assert [e.reserva_id for e in indisponiveis] == [2, 3, 4]


def test_liberar_assento_volta_a_livre(sistema):
    s = sistema("voos")
    voo_id = s.client.post("/voos", json=voo()).json()["id"]
    s.bus.publicar(ReservaCriada(1, voo_id, "1A", 10))

    s.bus.publicar(LiberarAssento(1))
    s.bus.publicar(LiberarAssento(99))

    assert assentos(s.client, voo_id)["1A"] == "LIVRE"
