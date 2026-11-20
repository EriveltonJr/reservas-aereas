from types import SimpleNamespace

from app.eventos import ReservaCancelada, ReservaConfirmada
from app.modulos.notificacoes.service import NotificacaoService


def test_reserva_confirmada_gera_notificacao():
    app = SimpleNamespace(state=SimpleNamespace())
    servico = NotificacaoService(app)

    servico.ao_confirmar(
        ReservaConfirmada(
            reserva_id=1,
            passageiro_id=2,
            valor=500.0,
        )
    )

    assert app.state.notificacoes == [
        {
            "tipo": "RESERVA_CONFIRMADA",
            "reserva_id": 1,
            "passageiro_id": 2,
            "valor": 500.0,
            "mensagem": "Reserva confirmada com sucesso",
        }
    ]


def test_reserva_cancelada_gera_notificacao():
    app = SimpleNamespace(state=SimpleNamespace())
    servico = NotificacaoService(app)

    servico.ao_cancelar(
        ReservaCancelada(
            reserva_id=1,
            passageiro_id=2,
            motivo="Pagamento recusado",
        )
    )

    assert app.state.notificacoes == [
        {
            "tipo": "RESERVA_CANCELADA",
            "reserva_id": 1,
            "passageiro_id": 2,
            "motivo": "Pagamento recusado",
            "mensagem": "Reserva cancelada",
        }
    ]
