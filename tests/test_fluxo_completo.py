from datetime import timedelta

from sqlalchemy import update

from app.banco import agora, sessao
from app.contratos import DadosPassageiro, PassageiroFalso
from app.modulos.pagamentos.models import Cobranca
from tests.apoio import CARTAO_RECUSADO, assentos, dados_cartao, dados_reserva, dados_voo

TODOS = ("passageiros", "voos", "reservas", "pagamentos", "notificacoes", "saga")


def titulos(client) -> list[str]:
    return [n["titulo"] for n in client.get("/notificacoes").json()["itens"]]


def test_passageiros_substitui_o_servico_provisorio(sistema):
    s = sistema("passageiros")
    servico = s.container.passageiros

    primeiro = servico.criar_ou_validar(DadosPassageiro("Ana Souza", "12345", "ana@exemplo.com"))
    mesmo = servico.criar_ou_validar(DadosPassageiro("Ana Souza", "12345", "ana@exemplo.com"))
    outro = servico.criar_ou_validar(DadosPassageiro("Bruno Lima", "67890", "bruno@exemplo.com"))

    assert not isinstance(servico, PassageiroFalso)
    assert primeiro == mesmo
    assert outro != primeiro


def test_compra_completa_com_pagamento(sistema):
    s = sistema(*TODOS)
    admin = s.admin()
    voo_id = admin.post("/voos", json=dados_voo()).json()["id"]
    cliente = s.cliente()

    reserva = cliente.post("/reservas", json=dados_reserva(voo_id)).json()
    assert reserva["status"] == "PENDENTE"
    assert assentos(s.client, voo_id)["1A"] == "BLOQUEADO"

    assert cliente.post(f"/pagamentos/{reserva['id']}", json=dados_cartao(CARTAO_RECUSADO)).status_code == 402
    assert cliente.post(f"/pagamentos/{reserva['id']}", json=dados_cartao()).status_code == 200

    confirmada = cliente.get(f"/reservas/{reserva['id']}").json()
    assert (confirmada["status"], confirmada["valor"]) == ("CONFIRMADA", 500)
    localizador = reserva["localizador"]
    assert titulos(cliente) == [f"Reserva {localizador} confirmada", f"Reserva {localizador} criada"]
    assert titulos(admin) == ["Pagamento recebido", "Pagamento recusado", f"Nova reserva {localizador}"]


def test_cancelamento_pelo_cliente_libera_assento_e_estorna(sistema):
    s = sistema(*TODOS)
    admin = s.admin()
    voo_id = admin.post("/voos", json=dados_voo()).json()["id"]
    cliente = s.cliente()
    reserva = cliente.post("/reservas", json=dados_reserva(voo_id)).json()
    cliente.post(f"/pagamentos/{reserva['id']}", json=dados_cartao())

    cancelada = cliente.post(f"/reservas/{reserva['id']}/cancelar").json()

    assert cancelada["status"] == "CANCELADA"
    assert assentos(s.client, voo_id)["1A"] == "LIVRE"
    assert cliente.get(f"/pagamentos/{reserva['id']}").json()["status"] == "ESTORNADO"
    assert titulos(admin)[0] == "Estorno solicitado"
    assert cliente.post(f"/reservas/{reserva['id']}/cancelar").status_code == 409


def test_prazo_de_pagamento_vencido_cancela_e_libera_assento(sistema, monkeypatch):
    monkeypatch.setattr("app.modulos.pagamentos.service.INTERVALO_VARREDURA", 0)
    s = sistema(*TODOS)
    voo_id = s.admin().post("/voos", json=dados_voo()).json()["id"]
    cliente = s.cliente()
    reserva = cliente.post("/reservas", json=dados_reserva(voo_id)).json()
    with sessao() as banco:
        banco.execute(update(Cobranca).values(prazo=agora() - timedelta(minutes=1)))
        banco.commit()

    cliente.get("/voos")

    expirada = cliente.get(f"/reservas/{reserva['id']}").json()
    assert expirada["status"] == "CANCELADA"
    assert expirada["motivo_cancelamento"] == "Prazo para pagamento expirado"
    assert assentos(s.client, voo_id)["1A"] == "LIVRE"


def test_assento_ocupado_cancela_a_segunda_reserva(sistema):
    s = sistema(*TODOS)
    voo_id = s.admin().post("/voos", json=dados_voo()).json()["id"]

    primeira = s.cliente("ana@exemplo.com").post("/reservas", json=dados_reserva(voo_id, documento="11111")).json()
    segunda = s.cliente("bruno@exemplo.com").post("/reservas", json=dados_reserva(voo_id, documento="22222")).json()

    assert primeira["status"] == "PENDENTE"
    assert segunda["status"] == "CANCELADA"
    assert segunda["motivo_cancelamento"] == "Assento já ocupado"
    assert assentos(s.client, voo_id)["1A"] == "BLOQUEADO"


def test_mesmo_documento_reaproveita_passageiro_nas_reservas(sistema):
    s = sistema(*TODOS)
    voo_id = s.admin().post("/voos", json=dados_voo()).json()["id"]
    cliente = s.cliente()

    primeira = cliente.post("/reservas", json=dados_reserva(voo_id, "1A")).json()
    segunda = cliente.post("/reservas", json=dados_reserva(voo_id, "1B")).json()

    assert primeira["passageiro_id"] == segunda["passageiro_id"]
