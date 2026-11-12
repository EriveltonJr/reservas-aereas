import importlib

import pytest

from app.contratos import DadosPassageiro, PassageiroFalso
from app.eventos import PagamentoRecusado

MODULOS_LIEDSON = ("passageiros", "pagamentos", "notificacoes", "saga")
TODOS = ("passageiros", "voos", "reservas", "pagamentos", "notificacoes", "saga")
SEM_PAGAMENTOS = ("passageiros", "voos", "reservas", "notificacoes", "saga")


def _modulos_prontos() -> bool:
    return all(
        callable(getattr(importlib.import_module(f"app.modulos.{nome}"), "registrar", None))
        for nome in MODULOS_LIEDSON
    )


pytestmark = pytest.mark.skipif(
    not _modulos_prontos(),
    reason="aguardando os módulos Passageiros, Pagamentos, Notificações e Saga",
)


def criar_voo(client, codigo: str, preco: float = 500) -> int:
    resposta = client.post(
        "/voos",
        json={"codigo": codigo, "origem": "Fortaleza", "destino": "Recife", "preco": preco, "assentos": ["1A", "1B"]},
    )
    assert resposta.status_code == 201
    return resposta.json()["id"]


def reservar(client, voo_id: int, assento: str = "1A", documento: str = "12345") -> dict:
    resposta = client.post(
        "/reservas",
        json={
            "voo_id": voo_id,
            "assento": assento,
            "passageiro": {"nome": "Ana Souza", "documento": documento, "email": "ana@exemplo.com"},
        },
    )
    assert resposta.status_code == 201
    return resposta.json()


def status_assento(client, voo_id: int, numero: str) -> str:
    assentos = client.get(f"/voos/{voo_id}").json()["assentos"]
    return next(a["status"] for a in assentos if a["numero"] == numero)


def test_passageiros_substitui_o_servico_provisorio(sistema):
    s = sistema("passageiros")
    servico = s.container.passageiros

    primeiro = servico.criar_ou_validar(DadosPassageiro("Ana Souza", "12345", "ana@exemplo.com"))
    mesmo = servico.criar_ou_validar(DadosPassageiro("Ana Souza", "12345", "ana@exemplo.com"))
    outro = servico.criar_ou_validar(DadosPassageiro("Bruno Lima", "67890", "bruno@exemplo.com"))

    assert not isinstance(servico, PassageiroFalso)
    assert primeiro == mesmo
    assert outro != primeiro


def test_reserva_termina_confirmada_ou_cancelada(sistema):
    s = sistema(*TODOS)
    voo_id = criar_voo(s.client, "EL100", 500)

    reserva = reservar(s.client, voo_id)

    assert reserva["status"] in ("CONFIRMADA", "CANCELADA")
    if reserva["status"] == "CONFIRMADA":
        assert reserva["valor"] == 500
        assert status_assento(s.client, voo_id, "1A") == "BLOQUEADO"
    else:
        assert status_assento(s.client, voo_id, "1A") == "LIVRE"


def test_saga_compensa_pagamento_recusado(sistema):
    s = sistema(*SEM_PAGAMENTOS)
    voo_id = criar_voo(s.client, "EL200")
    reserva = reservar(s.client, voo_id)
    assert status_assento(s.client, voo_id, "1A") == "BLOQUEADO"

    s.bus.publicar(PagamentoRecusado(reserva["id"], "Cartão recusado"))

    cancelada = s.client.get(f"/reservas/{reserva['id']}").json()
    assert cancelada["status"] == "CANCELADA"
    assert cancelada["motivo_cancelamento"]
    assert status_assento(s.client, voo_id, "1A") == "LIVRE"


def test_saga_cancela_reserva_com_assento_ocupado(sistema):
    s = sistema(*SEM_PAGAMENTOS)
    voo_id = criar_voo(s.client, "EL300")

    primeira = reservar(s.client, voo_id, documento="11111")
    segunda = reservar(s.client, voo_id, documento="22222")

    assert segunda["status"] == "CANCELADA"
    assert primeira["status"] == "PENDENTE"
    assert status_assento(s.client, voo_id, "1A") == "BLOQUEADO"


def test_mesmo_documento_reaproveita_passageiro_nas_reservas(sistema):
    s = sistema(*TODOS)
    voo_id = criar_voo(s.client, "EL400")

    primeira = reservar(s.client, voo_id, "1A")
    segunda = reservar(s.client, voo_id, "1B")

    assert primeira["passageiro_id"] == segunda["passageiro_id"]
