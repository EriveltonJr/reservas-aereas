from pydantic import BaseModel, Field


class PassageiroIn(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    documento: str = Field(min_length=5, max_length=30, pattern=r"^[A-Za-z0-9.\-]+$")
    email: str = Field(max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ReservaIn(BaseModel):
    voo_id: int = Field(gt=0)
    assento: str = Field(pattern=r"^[0-9]{1,3}[A-Z]$")
    passageiro: PassageiroIn
