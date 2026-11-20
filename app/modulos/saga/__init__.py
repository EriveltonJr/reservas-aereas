"""Saga: implemente registrar(app, bus, container) e coordene compensações via eventos."""
from app.eventos import AssentoIndisponivel, PagamentoRecusado
from app.modulos.saga.service import SagaService

def registrar(app, bus, container):
    del app, container

    servico = SagaService(bus)
    bus.inscrever(AssentoIndisponivel, servico.ao_assento_indisponivel)
    bus.inscrever(PagamentoRecusado, servico.ao_pagamento_recusado)
    