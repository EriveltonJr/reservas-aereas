import argparse
import getpass
import sys

from app.banco import configurar, criar_tabelas
from app.modulos.contas import models
from app.modulos.contas.routes import validar_senha
from app.modulos.contas.service import ContaService


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.modulos.contas", description="Gerencia contas do ELVoo")
    comandos = parser.add_subparsers(dest="comando", required=True)
    admin = comandos.add_parser("criar-admin", help="cria ou promove uma conta de administrador")
    admin.add_argument("email")
    admin.add_argument("--nome", default="Administrador")
    args = parser.parse_args()

    senha = getpass.getpass("Senha do administrador: ")
    if senha != getpass.getpass("Repita a senha: "):
        print("As senhas não conferem.", file=sys.stderr)
        return 1
    try:
        if len(senha) < 8:
            raise ValueError("A senha precisa ter pelo menos 8 caracteres")
        validar_senha(senha)
    except ValueError as erro:
        print(erro, file=sys.stderr)
        return 1

    criar_tabelas(configurar())
    conta = ContaService().criar_admin(args.nome, args.email, senha)
    print(f"Administrador pronto: {conta['email']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
