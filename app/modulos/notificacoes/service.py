from app.eventos import ReservaCancelada, ReservaConfirmada


class NotificacaoService:
    def __init__(self, app) -> None:
        self.notificacoes: list[dict] = []
        app.state.notificacoes = self.notificacoes

    def ao_confirmar(self, evento: ReservaConfirmada) -> None:
        self.notificacoes.append(
            {
                "tipo": "RESERVA_CONFIRMADA",
                "reserva_id": evento.reserva_id,
                "passageiro_id": evento.passageiro_id,
                "valor": evento.valor,
                "mensagem": "Reserva confirmada com sucesso",
            }
        )

    def ao_cancelar(self, evento: ReservaCancelada) -> None:
        self.notificacoes.append(
            {
                "tipo": "RESERVA_CANCELADA",
                "reserva_id": evento.reserva_id,
                "passageiro_id": evento.passageiro_id,
                "motivo": evento.motivo,
                "mensagem": "Reserva cancelada",
            }
        )
