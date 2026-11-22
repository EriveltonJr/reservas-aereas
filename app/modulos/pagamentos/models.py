from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.banco import Base, agora

AGUARDANDO_ASSENTO = "AGUARDANDO_ASSENTO"
AGUARDANDO = "AGUARDANDO"
PAGO = "PAGO"
EXPIRADO = "EXPIRADO"
CANCELADO = "CANCELADO"
ESTORNADO = "ESTORNADO"


class Cobranca(Base):
    __tablename__ = "pagamentos_cobranca"

    id: Mapped[int] = mapped_column(primary_key=True)
    reserva_id: Mapped[int] = mapped_column(unique=True, index=True)
    conta_id: Mapped[int | None] = mapped_column(default=None)
    valor: Mapped[float | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(String(20), default=AGUARDANDO_ASSENTO)
    prazo: Mapped[datetime | None] = mapped_column(DateTime, default=None, index=True)
    bandeira: Mapped[str | None] = mapped_column(String(20), default=None)
    final_cartao: Mapped[str | None] = mapped_column(String(4), default=None)
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    pago_em: Mapped[datetime | None] = mapped_column(DateTime, default=None)


class Tentativa(Base):
    __tablename__ = "pagamentos_tentativa"

    id: Mapped[int] = mapped_column(primary_key=True)
    cobranca_id: Mapped[int] = mapped_column(ForeignKey("pagamentos_cobranca.id"), index=True)
    aprovada: Mapped[bool]
    bandeira: Mapped[str] = mapped_column(String(20))
    final_cartao: Mapped[str] = mapped_column(String(4))
    motivo: Mapped[str | None] = mapped_column(String(200), default=None)
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
