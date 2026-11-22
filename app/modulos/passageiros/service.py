from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.banco import sessao
from app.contratos import DadosPassageiro
from app.modulos.passageiros.models import Passageiro

class PassageiroService:
    def criar_ou_validar(self, dados: DadosPassageiro) -> int:
        documentos = dados.documento.strip()

        if not documentos:
            raise ValueError("documento inválido")

        with sessao() as s:
            passageiro = s.scalar(select(Passageiro).where(Passageiro.documento == documentos))

            if passageiro:
                return passageiro.id

            passageiro = Passageiro(
                nome=dados.nome.strip(),
                documento=documentos,
                email=dados.email.strip().lower(),
            )

            s.add(passageiro)

            try:
                s.commit()
            except IntegrityError:
                s.rollback()

                passageiro = s.scalar(select(Passageiro).where(Passageiro.documento == documentos))
            
                if passageiro is None:
                    raise ValueError("Erro ao criar passageiro")

                return passageiro.id

            return passageiro.id