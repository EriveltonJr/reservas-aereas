CARTOES_RECUSADOS = {
    "4000000000000002": "Cartão recusado pelo banco emissor",
    "4000000000009995": "Saldo insuficiente",
    "4000000000000069": "Cartão bloqueado para compras online",
}


def somente_digitos(numero: str) -> str:
    return "".join(caractere for caractere in numero if caractere.isdigit())


def luhn_valido(numero: str) -> bool:
    total = 0
    for posicao, digito in enumerate(reversed(numero)):
        valor = int(digito)
        if posicao % 2 == 1:
            valor *= 2
            if valor > 9:
                valor -= 9
        total += valor
    return total % 10 == 0


PREFIXOS_ELO = ("4011", "4312", "4389", "5041", "5066", "5067", "6277", "6362", "6363", "6504", "6505", "6516")


def bandeira(numero: str) -> str | None:
    if len(numero) == 16 and numero.startswith(PREFIXOS_ELO):
        return "Elo"
    if len(numero) == 15 and numero.startswith(("34", "37")):
        return "American Express"
    if len(numero) in (13, 16, 19) and numero.startswith("4"):
        return "Visa"
    if len(numero) == 16 and (51 <= int(numero[:2]) <= 55 or 2221 <= int(numero[:4]) <= 2720):
        return "Mastercard"
    return None


def autorizar(numero: str) -> str | None:
    """Simula a resposta do adquirente: devolve o motivo da recusa ou None se aprovado."""
    return CARTOES_RECUSADOS.get(numero)
