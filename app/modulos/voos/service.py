from sqlalchemy import case, func, select, update
from sqlalchemy.exc import IntegrityError

from app.banco import sessao
from app.barramento import Barramento
from app.eventos import AssentoBloqueado, AssentoIndisponivel, LiberarAssento, ReservaCriada
from app.modulos.voos.models import BLOQUEADO, LIVRE, Assento, Voo


class VooJaExiste(Exception):
    pass


def _voo_dict(voo: Voo) -> dict:
    return {
        "id": voo.id,
        "codigo": voo.codigo,
        "origem": voo.origem,
        "destino": voo.destino,
        "preco": voo.preco,
    }


class VooService:
    def __init__(self, bus: Barramento) -> None:
        self.bus = bus

    def criar(self, codigo: str, origem: str, destino: str, preco: float, assentos: list[str]) -> dict:
        voo = Voo(codigo=codigo.upper(), origem=origem, destino=destino, preco=preco)
        with sessao() as s:
            try:
                s.add(voo)
                s.flush()
                s.add_all(Assento(voo_id=voo.id, numero=numero, status=LIVRE) for numero in assentos)
                s.commit()
            except IntegrityError as erro:
                raise VooJaExiste(voo.codigo) from erro
            return _voo_dict(voo)

    def listar(self) -> list[dict]:
        livres = func.coalesce(func.sum(case((Assento.status == LIVRE, 1), else_=0)), 0)
        consulta = (
            select(Voo, livres)
            .outerjoin(Assento, Assento.voo_id == Voo.id)
            .group_by(Voo.id)
            .order_by(Voo.id)
            .limit(100)
        )
        with sessao() as s:
            return [{**_voo_dict(voo), "assentos_livres": total} for voo, total in s.execute(consulta)]

    def obter(self, voo_id: int) -> dict | None:
        with sessao() as s:
            voo = s.get(Voo, voo_id)
            if voo is None:
                return None
            assentos = s.scalars(select(Assento).where(Assento.voo_id == voo_id).order_by(Assento.numero))
            return {
                **_voo_dict(voo),
                "assentos": [{"numero": a.numero, "status": a.status} for a in assentos],
            }

    def bloquear_assento(self, evento: ReservaCriada) -> None:
        with sessao() as s:
            voo = s.get(Voo, evento.voo_id)
            assento_id = None
            if voo is not None:
                assento_id = s.scalar(
                    select(Assento.id).where(Assento.voo_id == voo.id, Assento.numero == evento.assento)
                )
            bloqueou = False
            if assento_id is not None:
                resultado = s.execute(
                    update(Assento)
                    .where(Assento.id == assento_id, Assento.status == LIVRE)
                    .values(status=BLOQUEADO, reserva_id=evento.reserva_id)
                )
                s.commit()
                bloqueou = resultado.rowcount == 1

        if assento_id is None:
            self.bus.publicar(AssentoIndisponivel(evento.reserva_id, "Voo ou assento inexistente"))
        elif bloqueou:
            self.bus.publicar(
                AssentoBloqueado(evento.reserva_id, evento.voo_id, evento.assento, float(voo.preco))
            )
        else:
            self.bus.publicar(AssentoIndisponivel(evento.reserva_id, "Assento já ocupado"))

    def liberar_assento(self, evento: LiberarAssento) -> None:
        with sessao() as s:
            s.execute(
                update(Assento)
                .where(Assento.reserva_id == evento.reserva_id, Assento.status == BLOQUEADO)
                .values(status=LIVRE, reserva_id=None)
            )
            s.commit()
