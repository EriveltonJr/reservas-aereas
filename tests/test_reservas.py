from app.eventos import (
    CancelamentoSolicitado,
    CancelarReserva,
    PagamentoAprovado,
    ReservaCancelada,
    ReservaConfirmada,
    ReservaCriada,
)
from tests.apoio import dados_reserva


def test_criar_reserva_pendente_sem_dados_pessoais(sistema):
    s = sistema("reservas")
    cliente = s.cliente()

    resposta = cliente.post("/reservas", json=dados_reserva(1))

    assert resposta.status_code == 201
    criada = resposta.json()
    assert criada["status"] == "PENDENTE"
    assert len(criada["localizador"]) == 6
    assert criada["prazo_pagamento"]
    assert not {"nome", "documento", "email"} & set(criada)
    evento = s.publicados(ReservaCriada)[0]
    assert (evento.reserva_id, evento.passageiro_id, evento.localizador) == (
        criada["id"], criada["passageiro_id"], criada["localizador"],
    )
    assert evento.conta_id is not None


def test_reserva_exige_login(sistema):
    s = sistema("reservas")

    assert s.client.post("/reservas", json=dados_reserva(1)).status_code == 401
    assert s.client.get("/reservas").status_code == 401


def test_cada_cliente_ve_apenas_as_proprias_reservas(sistema):
    s = sistema("reservas")
    ana = s.cliente("ana@exemplo.com")
    bruno = s.cliente("bruno@exemplo.com", "Bruno Lima")
    reserva_ana = ana.post("/reservas", json=dados_reserva(1)).json()
    bruno.post("/reservas", json=dados_reserva(1, "1B", documento="67890"))

    assert [r["id"] for r in ana.get("/reservas").json()] == [reserva_ana["id"]]
    assert bruno.get(f"/reservas/{reserva_ana['id']}").status_code == 404
    assert len(s.admin().get("/reservas").json()) == 2


def test_entrada_invalida_da_422(sistema):
    cliente = sistema("reservas").cliente()

    assert cliente.post("/reservas", json=dados_reserva(1, assento="ZZ")).status_code == 422
    assert cliente.post("/reservas", json=dados_reserva(0)).status_code == 422
    assert cliente.post("/reservas", json=dados_reserva(1, email="ana.exemplo.com")).status_code == 422


def test_consultar_reserva_inexistente_da_404(sistema):
    cliente = sistema("reservas").cliente()

    assert cliente.get("/reservas/999").status_code == 404


def test_pagamento_aprovado_confirma_reserva(sistema):
    s = sistema("reservas")
    criada = s.cliente().post("/reservas", json=dados_reserva(1)).json()

    s.bus.publicar(PagamentoAprovado(criada["id"], 7, 500.0))

    evento = s.publicados(ReservaConfirmada)[0]
    assert (evento.reserva_id, evento.passageiro_id, evento.valor) == (criada["id"], criada["passageiro_id"], 500.0)
    assert evento.localizador == criada["localizador"]


def test_cancelar_reserva_publica_reserva_cancelada(sistema):
    s = sistema("reservas")
    cliente = s.cliente()
    criada = cliente.post("/reservas", json=dados_reserva(1)).json()

    s.bus.publicar(CancelarReserva(criada["id"], "Prazo para pagamento expirado"))

    cancelada = cliente.get(f"/reservas/{criada['id']}").json()
    assert cancelada["status"] == "CANCELADA"
    assert cancelada["motivo_cancelamento"] == "Prazo para pagamento expirado"
    assert s.publicados(ReservaCancelada)[0].reserva_id == criada["id"]


def test_cliente_solicita_cancelamento(sistema):
    s = sistema("reservas")
    cliente = s.cliente()
    criada = cliente.post("/reservas", json=dados_reserva(1)).json()

    assert cliente.post(f"/reservas/{criada['id']}/cancelar").status_code == 200

    assert s.publicados(CancelamentoSolicitado) == [CancelamentoSolicitado(criada["id"], "Cancelada pelo cliente")]
    assert s.cliente("outro@exemplo.com").post(f"/reservas/{criada['id']}/cancelar").status_code == 404
