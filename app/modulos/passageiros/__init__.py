from app.modulos.passageiros import models
from app.modulos.passageiros.service import PassageiroService

def registrar(app, bus, container):
    del app, bus

    servico = PassageiroService()
    container.registrar_passageiros(servico)