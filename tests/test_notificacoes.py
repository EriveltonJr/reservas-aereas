from app.eventos import PagamentoEstornado, ReservaCancelada, ReservaConfirmada, ReservaCriada
from app.modulos.notificacoes.service import brl


def titulos(client) -> list[str]:
    return [n["titulo"] for n in client.get("/notificacoes").json()["itens"]]


def test_cliente_recebe_avisos_da_propria_reserva(sistema):
    s = sistema("notificacoes")
    ana = s.cliente()
    conta_id = ana.get("/auth/eu").json()["id"]

    s.bus.publicar(ReservaCriada(1, 10, "1A", 2, conta_id, "ABC123"))
    s.bus.publicar(ReservaConfirmada(1, 2, 500.0, conta_id, "ABC123"))

    assert titulos(ana) == ["Reserva ABC123 confirmada", "Reserva ABC123 criada"]
    assert ana.get("/notificacoes").json()["nao_lidas"] == 2
    assert titulos(s.cliente("outro@exemplo.com")) == []


def test_admin_recebe_reserva_pagamento_cancelamento_e_estorno(sistema):
    s = sistema("notificacoes")
    admin = s.admin()

    s.bus.publicar(ReservaCriada(1, 10, "1A", 2, None, "ABC123"))
    s.bus.publicar(ReservaConfirmada(1, 2, 500.0, None, "ABC123"))
    s.bus.publicar(ReservaCancelada(1, 2, "Cancelada pelo cliente", None, "ABC123"))
    s.bus.publicar(PagamentoEstornado(1, 1, 500.0))

    assert titulos(admin) == [
        "Estorno solicitado",
        "Reserva ABC123 cancelada",
        "Pagamento recebido",
        "Nova reserva ABC123",
    ]


def test_marcar_notificacoes_como_lidas(sistema):
    s = sistema("notificacoes")
    ana = s.cliente()
    conta_id = ana.get("/auth/eu").json()["id"]
    s.bus.publicar(ReservaCriada(1, 10, "1A", 2, conta_id, "ABC123"))
    s.bus.publicar(ReservaCriada(2, 10, "1B", 2, conta_id, "DEF456"))
    primeira = ana.get("/notificacoes").json()["itens"][-1]["id"]

    assert ana.post(f"/notificacoes/{primeira}/lida").status_code == 204
    assert ana.get("/notificacoes").json()["nao_lidas"] == 1
    assert ana.post("/notificacoes/lidas").status_code == 204
    assert ana.get("/notificacoes").json()["nao_lidas"] == 0


def test_formata_valor_em_reais():
    assert brl(1234.5) == "R$ 1.234,50"
