from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.banco import Base

class Passageiro(Base):
    __tablename__ = "passageiros_passageiro"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    documento: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(120))