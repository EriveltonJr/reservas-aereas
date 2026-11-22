from app.eventos import ReservaCancelada, ReservaConfirmada
from app.modulos.notificacoes.service import NotificacaoService


def registrar(app, bus, container) -> None:
    del container
    servico = NotificacaoService(app)
    bus.inscrever(ReservaConfirmada, servico.ao_confirmar)
    bus.inscrever(ReservaCancelada, servico.ao_cancelar)