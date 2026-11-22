import threading
import time
from datetime import timedelta

from sqlalchemy import select

from app.banco import agora, iso_utc, sessao
from app.barramento import Barramento
from app.contratos import UsuarioAutenticado
from app.eventos import (
    AssentoBloqueado,
    PagamentoAprovado,
    PagamentoEstornado,
    PagamentoRecusado,
    PrazoPagamentoExpirado,
    ReservaCancelada,
    ReservaCriada,
)
from app.modulos.pagamentos import gateway
from app.modulos.pagamentos.models import (
    AGUARDANDO,
    AGUARDANDO_ASSENTO,
    CANCELADO,
    ESTORNADO,
    EXPIRADO,
    PAGO,
    Cobranca,
    Tentativa,
)
from app.politicas import PRAZO_PAGAMENTO_MINUTOS

INTERVALO_VARREDURA = 15


class CobrancaNaoEncontrada(Exception):
    pass


class PagamentoIndisponivel(Exception):
    pass


class PagamentoNegado(Exception):
    pass


def _cobranca_dict(cobranca: Cobranca, tentativas: list[Tentativa]) -> dict:
    return {
        "id": cobranca.id,
        "reserva_id": cobranca.reserva_id,
        "valor": cobranca.valor,
        "status": cobranca.status,
        "prazo": iso_utc(cobranca.prazo),
        "bandeira": cobranca.bandeira,
        "final_cartao": cobranca.final_cartao,
        "pago_em": iso_utc(cobranca.pago_em),
        "tentativas": [
            {
                "aprovada": t.aprovada,
                "bandeira": t.bandeira,
                "final_cartao": t.final_cartao,
                "motivo": t.motivo,
                "criada_em": iso_utc(t.criada_em),
            }
            for t in tentativas
        ],
    }


class PagamentoService:
    def __init__(self, bus: Barramento) -> None:
        self.bus = bus
        self._ultima_varredura = 0.0
        self._trava = threading.Lock()

    def ao_reserva_criada(self, evento: ReservaCriada) -> None:
        with sessao() as s:
            if s.scalar(select(Cobranca.id).where(Cobranca.reserva_id == evento.reserva_id)) is None:
                s.add(Cobranca(reserva_id=evento.reserva_id, conta_id=evento.conta_id, status=AGUARDANDO_ASSENTO))
                s.commit()

    def ao_assento_bloqueado(self, evento: AssentoBloqueado) -> None:
        with sessao() as s:
            cobranca = s.scalar(select(Cobranca).where(Cobranca.reserva_id == evento.reserva_id))
            if cobranca is None:
                cobranca = Cobranca(reserva_id=evento.reserva_id)
                s.add(cobranca)
            elif cobranca.status != AGUARDANDO_ASSENTO:
                return
            cobranca.valor = evento.valor
            cobranca.status = AGUARDANDO
            cobranca.prazo = agora() + timedelta(minutes=PRAZO_PAGAMENTO_MINUTOS)
            s.commit()

    def ao_reserva_cancelada(self, evento: ReservaCancelada) -> None:
        estorno = None
        with sessao() as s:
            cobranca = s.scalar(select(Cobranca).where(Cobranca.reserva_id == evento.reserva_id))
            if cobranca is None:
                return
            if cobranca.status in (AGUARDANDO, AGUARDANDO_ASSENTO):
                cobranca.status = CANCELADO
            elif cobranca.status == PAGO:
                cobranca.status = ESTORNADO
                estorno = PagamentoEstornado(cobranca.reserva_id, cobranca.id, cobranca.valor)
            s.commit()
        if estorno:
            self.bus.publicar(estorno)

    def pagar(self, reserva_id: int, usuario: UsuarioAutenticado, numero: str) -> dict:
        expirou = False
        recusa = None
        with sessao() as s:
            cobranca = self._cobranca_visivel(s, reserva_id, usuario)
            if cobranca.status == PAGO:
                raise PagamentoIndisponivel("Esta reserva já foi paga")
            if cobranca.status == AGUARDANDO_ASSENTO:
                raise PagamentoIndisponivel("O assento ainda não foi confirmado")
            if cobranca.status != AGUARDANDO:
                raise PagamentoIndisponivel("Esta reserva não está mais disponível para pagamento")
            if agora() > cobranca.prazo:
                cobranca.status = EXPIRADO
                expirou = True
            else:
                marca = gateway.bandeira(numero) or "Cartão"
                recusa = gateway.autorizar(numero)
                s.add(Tentativa(cobranca_id=cobranca.id, aprovada=recusa is None, bandeira=marca,
                                final_cartao=numero[-4:], motivo=recusa))
                if recusa is None:
                    cobranca.status = PAGO
                    cobranca.pago_em = agora()
                    cobranca.bandeira = marca
                    cobranca.final_cartao = numero[-4:]
            s.commit()
            cobranca_id, valor = cobranca.id, cobranca.valor

        if expirou:
            self.bus.publicar(PrazoPagamentoExpirado(reserva_id))
            raise PagamentoIndisponivel("O prazo para pagamento expirou e a reserva foi cancelada")
        if recusa:
            self.bus.publicar(PagamentoRecusado(reserva_id, recusa))
            raise PagamentoNegado(recusa)
        self.bus.publicar(PagamentoAprovado(reserva_id, cobranca_id, valor))
        return self.obter(reserva_id, usuario)

    def obter(self, reserva_id: int, usuario: UsuarioAutenticado) -> dict:
        with sessao() as s:
            cobranca = self._cobranca_visivel(s, reserva_id, usuario)
            tentativas = list(s.scalars(select(Tentativa).where(Tentativa.cobranca_id == cobranca.id).order_by(Tentativa.id)))
            return _cobranca_dict(cobranca, tentativas)

    def listar(self) -> list[dict]:
        with sessao() as s:
            cobrancas = list(s.scalars(select(Cobranca).order_by(Cobranca.id.desc()).limit(300)))
            tentativas: dict[int, list[Tentativa]] = {}
            if cobrancas:
                consulta = select(Tentativa).where(Tentativa.cobranca_id.in_([c.id for c in cobrancas])).order_by(Tentativa.id)
                for tentativa in s.scalars(consulta):
                    tentativas.setdefault(tentativa.cobranca_id, []).append(tentativa)
            return [_cobranca_dict(c, tentativas.get(c.id, [])) for c in cobrancas]

    def expirar_vencidas(self, forcar: bool = False) -> None:
        with self._trava:
            if not forcar and time.monotonic() - self._ultima_varredura < INTERVALO_VARREDURA:
                return
            self._ultima_varredura = time.monotonic()
        with sessao() as s:
            vencidas = list(s.scalars(select(Cobranca).where(Cobranca.status == AGUARDANDO, Cobranca.prazo < agora())))
            for cobranca in vencidas:
                cobranca.status = EXPIRADO
            s.commit()
            reservas = [cobranca.reserva_id for cobranca in vencidas]
        for reserva_id in reservas:
            self.bus.publicar(PrazoPagamentoExpirado(reserva_id))

    @staticmethod
    def _cobranca_visivel(s, reserva_id: int, usuario: UsuarioAutenticado) -> Cobranca:
        cobranca = s.scalar(select(Cobranca).where(Cobranca.reserva_id == reserva_id))
        if cobranca is None or not (usuario.admin or cobranca.conta_id == usuario.id):
            raise CobrancaNaoEncontrada
        return cobranca
