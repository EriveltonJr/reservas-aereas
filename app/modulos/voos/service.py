from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, select, update
from sqlalchemy.exc import IntegrityError

from app.banco import agora, iso_utc, sessao
from app.barramento import Barramento
from app.eventos import AssentoBloqueado, AssentoIndisponivel, LiberarAssento, ReservaCriada
from app.modulos.voos.models import BLOQUEADO, LIVRE, Assento, Voo
from app.politicas import ANTECEDENCIA_MINIMA_COMPRA_HORAS


class VooJaExiste(Exception):
    pass


def _utc(momento: datetime) -> datetime:
    return momento.astimezone(UTC).replace(tzinfo=None)


def _voo_dict(voo: Voo) -> dict:
    return {
        "id": voo.id,
        "codigo": voo.codigo,
        "origem": voo.origem,
        "destino": voo.destino,
        "preco": voo.preco,
        "partida": iso_utc(voo.partida),
        "chegada": iso_utc(voo.chegada),
    }


def _limite_compra() -> datetime:
    return agora() + timedelta(hours=ANTECEDENCIA_MINIMA_COMPRA_HORAS)


class VooService:
    def __init__(self, bus: Barramento) -> None:
        self.bus = bus

    def criar(
        self,
        codigo: str,
        origem: str,
        destino: str,
        preco: float,
        assentos: list[str],
        partida: datetime,
        chegada: datetime,
    ) -> dict:
        voo = Voo(
            codigo=codigo.upper(),
            origem=origem.strip(),
            destino=destino.strip(),
            preco=preco,
            partida=_utc(partida),
            chegada=_utc(chegada),
        )
        with sessao() as s:
            try:
                s.add(voo)
                s.flush()
                s.add_all(Assento(voo_id=voo.id, numero=numero, status=LIVRE) for numero in assentos)
                s.commit()
            except IntegrityError as erro:
                raise VooJaExiste(voo.codigo) from erro
            return _voo_dict(voo)

    def listar(self, incluir_encerrados: bool = False) -> list[dict]:
        livres = func.coalesce(func.sum(case((Assento.status == LIVRE, 1), else_=0)), 0)
        total = func.count(Assento.id)
        consulta = (
            select(Voo, livres, total)
            .outerjoin(Assento, Assento.voo_id == Voo.id)
            .group_by(Voo.id)
            .order_by(Voo.partida, Voo.id)
            .limit(200)
        )
        if not incluir_encerrados:
            consulta = consulta.where(Voo.partida > _limite_compra())
        with sessao() as s:
            return [
                {**_voo_dict(voo), "assentos_livres": disponiveis, "assentos_total": quantidade}
                for voo, disponiveis, quantidade in s.execute(consulta)
            ]

    def obter(self, voo_id: int) -> dict | None:
        with sessao() as s:
            voo = s.get(Voo, voo_id)
            if voo is None:
                return None
            assentos = s.scalars(select(Assento).where(Assento.voo_id == voo_id).order_by(Assento.numero))
            return {
                **_voo_dict(voo),
                "vendas_abertas": voo.partida > _limite_compra(),
                "assentos": [{"numero": a.numero, "status": a.status} for a in assentos],
            }

    def atualizar_preco(self, voo_id: int, preco: float) -> dict | None:
        with sessao() as s:
            voo = s.get(Voo, voo_id)
            if voo is None:
                return None
            voo.preco = preco
            s.commit()
            return _voo_dict(voo)

    def bloquear_assento(self, evento: ReservaCriada) -> None:
        motivo = None
        with sessao() as s:
            voo = s.get(Voo, evento.voo_id)
            assento_id = None
            if voo is not None:
                assento_id = s.scalar(
                    select(Assento.id).where(Assento.voo_id == voo.id, Assento.numero == evento.assento)
                )
            if assento_id is None:
                motivo = "Voo ou assento inexistente"
            elif voo.partida <= _limite_compra():
                motivo = "Vendas encerradas para este voo"
            else:
                resultado = s.execute(
                    update(Assento)
                    .where(Assento.id == assento_id, Assento.status == LIVRE)
                    .values(status=BLOQUEADO, reserva_id=evento.reserva_id)
                )
                s.commit()
                if resultado.rowcount != 1:
                    motivo = "Assento já ocupado"

        if motivo:
            self.bus.publicar(AssentoIndisponivel(evento.reserva_id, motivo))
        else:
            self.bus.publicar(
                AssentoBloqueado(evento.reserva_id, evento.voo_id, evento.assento, float(voo.preco))
            )

    def liberar_assento(self, evento: LiberarAssento) -> None:
        with sessao() as s:
            s.execute(
                update(Assento)
                .where(Assento.reserva_id == evento.reserva_id, Assento.status == BLOQUEADO)
                .values(status=LIVRE, reserva_id=None)
            )
            s.commit()
