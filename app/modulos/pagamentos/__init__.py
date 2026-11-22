from app.eventos import AssentoBloqueado
from app.modulos.pagamentos.service import PagamentoService

def registrar(app, bus, container):
    del app, container

    servico = PagamentoService(bus)
    bus.inscrever(AssentoBloqueado, servico.processar)