from datetime import timedelta

from sqlalchemy import update

from app.banco import agora, sessao
from app.eventos import (
    PagamentoAprovado,
    PagamentoEstornado,
    PagamentoRecusado,
    PrazoPagamentoExpirado,
    ReservaCancelada,
)
from app.modulos.pagamentos import gateway
from app.modulos.pagamentos.models import Cobranca
from tests.apoio import CARTAO_APROVADO, CARTAO_RECUSADO, dados_cartao, dados_reserva, dados_voo

MODULOS = ("voos", "reservas", "pagamentos")


def preparar(s, preco=500.0):
    voo_id = s.admin().post("/voos", json=dados_voo(preco=preco)).json()["id"]
    cliente = s.cliente()
    reserva = cliente.post("/reservas", json=dados_reserva(voo_id)).json()
    return cliente, reserva


def test_cartao_valido_aprova_e_confirma_reserva(sistema):
    s = sistema(*MODULOS)
    cliente, reserva = preparar(s, 1234.5)

    resposta = cliente.post(f"/pagamentos/{reserva['id']}", json=dados_cartao())

    assert resposta.status_code == 200
    pagamento = resposta.json()
    assert (pagamento["status"], pagamento["bandeira"], pagamento["final_cartao"]) == ("PAGO", "Visa", "4242")
    assert "numero" not in pagamento and "cvv" not in str(pagamento)
    assert s.publicados(PagamentoAprovado)[0].valor == 1234.5
    assert cliente.get(f"/reservas/{reserva['id']}").json()["status"] == "CONFIRMADA"


def test_cartao_recusado_mantem_reserva_pendente_para_nova_tentativa(sistema):
    s = sistema(*MODULOS)
    cliente, reserva = preparar(s)

    recusado = cliente.post(f"/pagamentos/{reserva['id']}", json=dados_cartao(CARTAO_RECUSADO))

    assert recusado.status_code == 402
    assert recusado.json()["detail"] == "Cartão recusado pelo banco emissor"
    assert s.publicados(PagamentoRecusado)[0].reserva_id == reserva["id"]
    assert cliente.get(f"/reservas/{reserva['id']}").json()["status"] == "PENDENTE"
    assert cliente.post(f"/pagamentos/{reserva['id']}", json=dados_cartao()).status_code == 200
    assert cliente.post(f"/pagamentos/{reserva['id']}", json=dados_cartao()).status_code == 409


def test_dados_de_cartao_invalidos_dao_422(sistema):
    s = sistema(*MODULOS)
    cliente, reserva = preparar(s)
    rota = f"/pagamentos/{reserva['id']}"

    assert cliente.post(rota, json=dados_cartao("4242 4242 4242 4241")).status_code == 422
    assert cliente.post(rota, json=dados_cartao(validade="01/20")).status_code == 422
    assert cliente.post(rota, json=dados_cartao(cvv="12")).status_code == 422
    assert cliente.post(rota, json=dados_cartao("9999 9999 9999 9995")).status_code == 422


def test_somente_o_dono_paga_e_consulta(sistema):
    s = sistema(*MODULOS)
    _, reserva = preparar(s)
    outro = s.cliente("outro@exemplo.com")

    assert outro.post(f"/pagamentos/{reserva['id']}", json=dados_cartao()).status_code == 404
    assert outro.get(f"/pagamentos/{reserva['id']}").status_code == 404
    assert s.client.get("/pagamentos").status_code == 401


def test_prazo_vencido_expira_a_cobranca(sistema):
    s = sistema(*MODULOS)
    cliente, reserva = preparar(s)
    with sessao() as banco:
        banco.execute(update(Cobranca).values(prazo=agora() - timedelta(minutes=1)))
        banco.commit()

    resposta = cliente.post(f"/pagamentos/{reserva['id']}", json=dados_cartao())

    assert resposta.status_code == 409
    assert s.publicados(PrazoPagamentoExpirado) == [PrazoPagamentoExpirado(reserva["id"])]


def test_cancelamento_de_reserva_paga_gera_estorno(sistema):
    s = sistema(*MODULOS)
    cliente, reserva = preparar(s)
    cliente.post(f"/pagamentos/{reserva['id']}", json=dados_cartao())

    s.bus.publicar(ReservaCancelada(reserva["id"], reserva["passageiro_id"], "Cancelada pelo cliente"))

    assert s.publicados(PagamentoEstornado)[0].valor == 500.0
    assert cliente.get(f"/pagamentos/{reserva['id']}").json()["status"] == "ESTORNADO"


def test_validacao_de_cartao():
    assert gateway.luhn_valido("4242424242424242")
    assert not gateway.luhn_valido("4242424242424241")
    assert gateway.bandeira("4242424242424242") == "Visa"
    assert gateway.bandeira("5555555555554444") == "Mastercard"
    assert gateway.bandeira("378282246310005") == "American Express"
    assert gateway.autorizar(gateway.somente_digitos(CARTAO_APROVADO)) is None
