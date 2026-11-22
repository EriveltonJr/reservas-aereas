from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.banco import Base

LIVRE = "LIVRE"
BLOQUEADO = "BLOQUEADO"


class Voo(Base):
    __tablename__ = "voos_voo"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    origem: Mapped[str] = mapped_column(String(50))
    destino: Mapped[str] = mapped_column(String(50))
    preco: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False))
    partida: Mapped[datetime] = mapped_column(DateTime, index=True)
    chegada: Mapped[datetime] = mapped_column(DateTime)


class Assento(Base):
    __tablename__ = "voos_assento"
    __table_args__ = (UniqueConstraint("voo_id", "numero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    voo_id: Mapped[int] = mapped_column(ForeignKey("voos_voo.id"))
    numero: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(10), default=LIVRE)
    reserva_id: Mapped[int | None] = mapped_column(default=None)
