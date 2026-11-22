from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.banco import Base, agora

PENDENTE = "PENDENTE"
CONFIRMADA = "CONFIRMADA"
CANCELADA = "CANCELADA"


class Reserva(Base):
    __tablename__ = "reservas_reserva"

    id: Mapped[int] = mapped_column(primary_key=True)
    localizador: Mapped[str] = mapped_column(String(6), unique=True, index=True)
    conta_id: Mapped[int | None] = mapped_column(default=None, index=True)
    voo_id: Mapped[int]
    assento: Mapped[str] = mapped_column(String(10))
    passageiro_id: Mapped[int]
    status: Mapped[str] = mapped_column(String(10), default=PENDENTE)
    valor: Mapped[float | None] = mapped_column(default=None)
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(200), default=None)
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    confirmada_em: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    cancelada_em: Mapped[datetime | None] = mapped_column(DateTime, default=None)
