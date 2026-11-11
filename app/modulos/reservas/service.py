from app.banco import sessao
from app.barramento import Barramento
from app.contratos import Container, DadosPassageiro
from app.eventos import (
    CancelarReserva,
    PagamentoAprovado,
    ReservaCancelada,
    ReservaConfirmada,
    ReservaCriada,
)
from app.modulos.reservas.models import CANCELADA, CONFIRMADA, PENDENTE, Reserva


def _reserva_dict(reserva: Reserva) -> dict:
    return {
        "id": reserva.id,
        "voo_id": reserva.voo_id,
        "assento": reserva.assento,
        "passageiro_id": reserva.passageiro_id,
        "status": reserva.status,
        "valor": reserva.valor,
        "motivo_cancelamento": reserva.motivo_cancelamento,
    }


class ReservaService:
    def __init__(self, bus: Barramento, container: Container) -> None:
        self.bus = bus
        self.container = container

    def criar(self, voo_id: int, assento: str, nome: str, documento: str, email: str) -> dict:
        passageiro_id = self.container.passageiros.criar_ou_validar(DadosPassageiro(nome, documento, email))
        reserva = Reserva(voo_id=voo_id, assento=assento, passageiro_id=passageiro_id, status=PENDENTE)
        with sessao() as s:
            s.add(reserva)
            s.commit()
        self.bus.publicar(ReservaCriada(reserva.id, voo_id, assento, passageiro_id))
        return self.obter(reserva.id)

    def obter(self, reserva_id: int) -> dict | None:
        with sessao() as s:
            reserva = s.get(Reserva, reserva_id)
            return _reserva_dict(reserva) if reserva else None

    def ao_pagamento_aprovado(self, evento: PagamentoAprovado) -> None:
        with sessao() as s:
            reserva = s.get(Reserva, evento.reserva_id)
            if reserva is None or reserva.status != PENDENTE:
                return
            reserva.status = CONFIRMADA
            reserva.valor = evento.valor
            s.commit()
        self.bus.publicar(ReservaConfirmada(reserva.id, reserva.passageiro_id, evento.valor))

    def ao_cancelar_reserva(self, evento: CancelarReserva) -> None:
        with sessao() as s:
            reserva = s.get(Reserva, evento.reserva_id)
            if reserva is None or reserva.status == CANCELADA:
                return
            reserva.status = CANCELADA
            reserva.motivo_cancelamento = evento.motivo
            s.commit()
        self.bus.publicar(ReservaCancelada(reserva.id, reserva.passageiro_id, evento.motivo))
