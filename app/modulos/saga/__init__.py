from app.eventos import AssentoIndisponivel, CancelamentoSolicitado, PrazoPagamentoExpirado
from app.modulos.saga.service import SagaService


def registrar(app, bus, container):
    del app, container

    servico = SagaService(bus)
    bus.inscrever(AssentoIndisponivel, servico.ao_assento_indisponivel)
    bus.inscrever(PrazoPagamentoExpirado, servico.ao_prazo_expirado)
    bus.inscrever(CancelamentoSolicitado, servico.ao_cancelamento_solicitado)
