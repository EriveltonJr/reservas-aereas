import secrets
from datetime import timedelta

from sqlalchemy import select

from app.banco import agora, iso_utc, sessao
from app.barramento import Barramento
from app.contratos import Container, DadosPassageiro, UsuarioAutenticado
from app.eventos import (
    CancelamentoSolicitado,
    CancelarReserva,
    PagamentoAprovado,
    ReservaCancelada,
    ReservaConfirmada,
    ReservaCriada,
)
from app.modulos.reservas.models import CANCELADA, CONFIRMADA, PENDENTE, Reserva
from app.politicas import CANCELAMENTO_GRATUITO_HORAS, PRAZO_PAGAMENTO_MINUTOS

ALFABETO_LOCALIZADOR = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class ReservaNaoEncontrada(Exception):
    pass


class CancelamentoNaoPermitido(Exception):
    pass


def _cancelavel(reserva: Reserva) -> bool:
    if reserva.status == PENDENTE:
        return True
    if reserva.status == CONFIRMADA and reserva.confirmada_em:
        return agora() <= reserva.confirmada_em + timedelta(hours=CANCELAMENTO_GRATUITO_HORAS)
    return False


def _reserva_dict(reserva: Reserva) -> dict:
    prazo = reserva.criada_em + timedelta(minutes=PRAZO_PAGAMENTO_MINUTOS) if reserva.status == PENDENTE else None
    return {
        "id": reserva.id,
        "localizador": reserva.localizador,
        "voo_id": reserva.voo_id,
        "assento": reserva.assento,
        "passageiro_id": reserva.passageiro_id,
        "status": reserva.status,
        "valor": reserva.valor,
        "motivo_cancelamento": reserva.motivo_cancelamento,
        "criada_em": iso_utc(reserva.criada_em),
        "prazo_pagamento": iso_utc(prazo),
        "confirmada_em": iso_utc(reserva.confirmada_em),
        "cancelavel": _cancelavel(reserva),
    }


class ReservaService:
    def __init__(self, bus: Barramento, container: Container) -> None:
        self.bus = bus
        self.container = container

    def criar(
        self, voo_id: int, assento: str, nome: str, documento: str, email: str, conta_id: int | None = None
    ) -> dict:
        passageiro_id = self.container.passageiros.criar_ou_validar(DadosPassageiro(nome, documento, email))
        with sessao() as s:
            reserva = Reserva(
                localizador=self._novo_localizador(s),
                conta_id=conta_id,
                voo_id=voo_id,
                assento=assento,
                passageiro_id=passageiro_id,
                status=PENDENTE,
            )
            s.add(reserva)
            s.commit()
        self.bus.publicar(
            ReservaCriada(reserva.id, voo_id, assento, passageiro_id, conta_id, reserva.localizador)
        )
        return self.obter(reserva.id)

    def obter(self, reserva_id: int, usuario: UsuarioAutenticado | None = None) -> dict | None:
        with sessao() as s:
            reserva = s.get(Reserva, reserva_id)
            if reserva is None or not self._pode_ver(reserva, usuario):
                return None
            return _reserva_dict(reserva)

    def listar(self, usuario: UsuarioAutenticado) -> list[dict]:
        consulta = select(Reserva).order_by(Reserva.id.desc()).limit(300)
        if not usuario.admin:
            consulta = consulta.where(Reserva.conta_id == usuario.id)
        with sessao() as s:
            return [_reserva_dict(reserva) for reserva in s.scalars(consulta)]

    def solicitar_cancelamento(self, reserva_id: int, usuario: UsuarioAutenticado) -> dict:
        with sessao() as s:
            reserva = s.get(Reserva, reserva_id)
            if reserva is None or not self._pode_ver(reserva, usuario):
                raise ReservaNaoEncontrada
            if reserva.status == CANCELADA:
                raise CancelamentoNaoPermitido("Esta reserva já está cancelada")
            if not usuario.admin and not _cancelavel(reserva):
                raise CancelamentoNaoPermitido(
                    f"O cancelamento gratuito vale por {CANCELAMENTO_GRATUITO_HORAS} horas após a confirmação"
                )
        motivo = "Cancelada pela companhia" if usuario.admin and reserva.conta_id != usuario.id else "Cancelada pelo cliente"
        self.bus.publicar(CancelamentoSolicitado(reserva_id, motivo))
        return self.obter(reserva_id)

    def ao_pagamento_aprovado(self, evento: PagamentoAprovado) -> None:
        with sessao() as s:
            reserva = s.get(Reserva, evento.reserva_id)
            if reserva is None or reserva.status != PENDENTE:
                return
            reserva.status = CONFIRMADA
            reserva.valor = evento.valor
            reserva.confirmada_em = agora()
            s.commit()
        self.bus.publicar(
            ReservaConfirmada(reserva.id, reserva.passageiro_id, evento.valor, reserva.conta_id, reserva.localizador)
        )

    def ao_cancelar_reserva(self, evento: CancelarReserva) -> None:
        with sessao() as s:
            reserva = s.get(Reserva, evento.reserva_id)
            if reserva is None or reserva.status == CANCELADA:
                return
            reserva.status = CANCELADA
            reserva.motivo_cancelamento = evento.motivo
            reserva.cancelada_em = agora()
            s.commit()
        self.bus.publicar(
            ReservaCancelada(reserva.id, reserva.passageiro_id, evento.motivo, reserva.conta_id, reserva.localizador)
        )

    @staticmethod
    def _pode_ver(reserva: Reserva, usuario: UsuarioAutenticado | None) -> bool:
        return usuario is None or usuario.admin or reserva.conta_id == usuario.id

    @staticmethod
    def _novo_localizador(s) -> str:
        while True:
            codigo = "".join(secrets.choice(ALFABETO_LOCALIZADOR) for _ in range(6))
            if s.scalar(select(Reserva.id).where(Reserva.localizador == codigo)) is None:
                return codigo
