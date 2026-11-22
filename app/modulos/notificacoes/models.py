from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.banco import Base, agora


class Notificacao(Base):
    __tablename__ = "notificacoes_notificacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    conta_id: Mapped[int | None] = mapped_column(default=None, index=True)
    para_admin: Mapped[bool] = mapped_column(default=False, index=True)
    tipo: Mapped[str] = mapped_column(String(30))
    titulo: Mapped[str] = mapped_column(String(120))
    mensagem: Mapped[str] = mapped_column(String(300))
    reserva_id: Mapped[int | None] = mapped_column(default=None)
    lida: Mapped[bool] = mapped_column(default=False)
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
