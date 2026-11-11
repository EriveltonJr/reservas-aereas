from app.eventos import (
    CancelarReserva,
    PagamentoAprovado,
    ReservaCancelada,
    ReservaConfirmada,
    ReservaCriada,
)


def reserva(assento="1A", voo_id=1, documento="12345", email="ana@exemplo.com") -> dict:
    return {
        "voo_id": voo_id,
        "assento": assento,
        "passageiro": {"nome": "Ana Souza", "documento": documento, "email": email},
    }


def test_criar_reserva_pendente_sem_dados_pessoais(sistema):
    s = sistema("reservas")

    resposta = s.client.post("/reservas", json=reserva())

    assert resposta.status_code == 201
    criada = resposta.json()
    assert criada["status"] == "PENDENTE"
    assert not {"nome", "documento", "email"} & set(criada)
    assert s.publicados(ReservaCriada) == [ReservaCriada(criada["id"], 1, "1A", criada["passageiro_id"])]


def test_mesmo_passageiro_em_duas_reservas(sistema):
    s = sistema("reservas")

    primeira = s.client.post("/reservas", json=reserva("1A")).json()
    segunda = s.client.post("/reservas", json=reserva("1B")).json()

    assert primeira["passageiro_id"] == segunda["passageiro_id"]
    assert primeira["id"] != segunda["id"]


def test_entrada_invalida_da_422(sistema):
    s = sistema("reservas")

    assert s.client.post("/reservas", json=reserva(assento="ZZ")).status_code == 422
    assert s.client.post("/reservas", json=reserva(voo_id=0)).status_code == 422
    assert s.client.post("/reservas", json=reserva(email="ana.exemplo.com")).status_code == 422


def test_consultar_reserva(sistema):
    s = sistema("reservas")
    criada = s.client.post("/reservas", json=reserva()).json()

    assert s.client.get(f"/reservas/{criada['id']}").json() == criada
    resposta = s.client.get("/reservas/999")
    assert resposta.status_code == 404
    assert resposta.json()["detail"] == "Reserva não encontrada"


def test_pagamento_aprovado_confirma_reserva(sistema):
    s = sistema("reservas")
    criada = s.client.post("/reservas", json=reserva()).json()

    s.bus.publicar(PagamentoAprovado(criada["id"], 7, 500.0))

    confirmada = s.client.get(f"/reservas/{criada['id']}").json()
    assert confirmada["status"] == "CONFIRMADA"
    assert confirmada["valor"] == 500
    assert s.publicados(ReservaConfirmada) == [
        ReservaConfirmada(criada["id"], criada["passageiro_id"], 500.0)
    ]


def test_cancelar_reserva(sistema):
    s = sistema("reservas")
    criada = s.client.post("/reservas", json=reserva()).json()

    s.bus.publicar(CancelarReserva(criada["id"], "Pagamento recusado"))

    cancelada = s.client.get(f"/reservas/{criada['id']}").json()
    assert cancelada["status"] == "CANCELADA"
    assert cancelada["motivo_cancelamento"] == "Pagamento recusado"
    assert s.publicados(ReservaCancelada) == [
        ReservaCancelada(criada["id"], criada["passageiro_id"], "Pagamento recusado")
    ]
