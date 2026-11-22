from sqlalchemy import func, select, update

from app.banco import iso_utc, sessao
from app.contratos import UsuarioAutenticado
from app.eventos import (
    PagamentoEstornado,
    PagamentoRecusado,
    ReservaCancelada,
    ReservaConfirmada,
    ReservaCriada,
)
from app.modulos.notificacoes.models import Notificacao
from app.politicas import PRAZO_ESTORNO_DIAS_UTEIS, PRAZO_PAGAMENTO_MINUTOS


def brl(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _rotulo(localizador: str, reserva_id: int) -> str:
    return localizador or f"#{reserva_id}"


class NotificacaoService:
    def ao_reserva_criada(self, evento: ReservaCriada) -> None:
        rotulo = _rotulo(evento.localizador, evento.reserva_id)
        self._cliente(evento.conta_id, evento.reserva_id, "RESERVA_CRIADA", f"Reserva {rotulo} criada",
                      f"Assento {evento.assento} reservado. Conclua o pagamento em até "
                      f"{PRAZO_PAGAMENTO_MINUTOS} minutos para emitir o bilhete.")
        self._admin(evento.reserva_id, "NOVA_RESERVA", f"Nova reserva {rotulo}",
                    f"Voo #{evento.voo_id}, assento {evento.assento}. Aguardando pagamento.")

    def ao_reserva_confirmada(self, evento: ReservaConfirmada) -> None:
        rotulo = _rotulo(evento.localizador, evento.reserva_id)
        self._cliente(evento.conta_id, evento.reserva_id, "RESERVA_CONFIRMADA", f"Reserva {rotulo} confirmada",
                      f"Pagamento de {brl(evento.valor)} aprovado e bilhete emitido. Boa viagem!")
        self._admin(evento.reserva_id, "PAGAMENTO_RECEBIDO", "Pagamento recebido",
                    f"Reserva {rotulo}: {brl(evento.valor)} aprovado.")

    def ao_pagamento_recusado(self, evento: PagamentoRecusado) -> None:
        self._admin(evento.reserva_id, "PAGAMENTO_RECUSADO", "Pagamento recusado",
                    f"Reserva #{evento.reserva_id}: {evento.motivo}.")

    def ao_reserva_cancelada(self, evento: ReservaCancelada) -> None:
        rotulo = _rotulo(evento.localizador, evento.reserva_id)
        self._cliente(evento.conta_id, evento.reserva_id, "RESERVA_CANCELADA", f"Reserva {rotulo} cancelada",
                      f"Motivo: {evento.motivo}. Se houve pagamento, o estorno é feito em até "
                      f"{PRAZO_ESTORNO_DIAS_UTEIS} dias úteis.")
        self._admin(evento.reserva_id, "RESERVA_CANCELADA", f"Reserva {rotulo} cancelada", evento.motivo)

    def ao_pagamento_estornado(self, evento: PagamentoEstornado) -> None:
        self._admin(evento.reserva_id, "ESTORNO", "Estorno solicitado",
                    f"Reserva #{evento.reserva_id}: {brl(evento.valor)} a devolver ao cliente.")

    def listar(self, usuario: UsuarioAutenticado) -> dict:
        filtro = self._filtro(usuario)
        with sessao() as s:
            itens = s.scalars(select(Notificacao).where(filtro).order_by(Notificacao.id.desc()).limit(50))
            nao_lidas = s.scalar(select(func.count()).select_from(Notificacao).where(filtro, Notificacao.lida.is_(False)))
            return {
                "nao_lidas": nao_lidas,
                "itens": [
                    {
                        "id": n.id,
                        "tipo": n.tipo,
                        "titulo": n.titulo,
                        "mensagem": n.mensagem,
                        "reserva_id": n.reserva_id,
                        "lida": n.lida,
                        "criada_em": iso_utc(n.criada_em),
                    }
                    for n in itens
                ],
            }

    def marcar_lidas(self, usuario: UsuarioAutenticado, notificacao_id: int | None = None) -> None:
        condicao = [self._filtro(usuario)]
        if notificacao_id is not None:
            condicao.append(Notificacao.id == notificacao_id)
        with sessao() as s:
            s.execute(update(Notificacao).where(*condicao).values(lida=True))
            s.commit()

    @staticmethod
    def _filtro(usuario: UsuarioAutenticado):
        return Notificacao.para_admin.is_(True) if usuario.admin else Notificacao.conta_id == usuario.id

    def _cliente(self, conta_id: int | None, reserva_id: int, tipo: str, titulo: str, mensagem: str) -> None:
        if conta_id is not None:
            self._gravar(Notificacao(conta_id=conta_id, tipo=tipo, titulo=titulo, mensagem=mensagem, reserva_id=reserva_id))

    def _admin(self, reserva_id: int, tipo: str, titulo: str, mensagem: str) -> None:
        self._gravar(Notificacao(para_admin=True, tipo=tipo, titulo=titulo, mensagem=mensagem, reserva_id=reserva_id))

    @staticmethod
    def _gravar(notificacao: Notificacao) -> None:
        with sessao() as s:
            s.add(notificacao)
            s.commit()
