from datetime import UTC, datetime, timedelta

CARTAO_APROVADO = "4242 4242 4242 4242"
CARTAO_RECUSADO = "4000 0000 0000 0002"


def dados_voo(codigo="EL100", preco=500.0, assentos=("1A", "1B"), dias=10, **extras) -> dict:
    partida = datetime.now(UTC) + timedelta(days=dias)
    return {
        "codigo": codigo,
        "origem": "Fortaleza",
        "destino": "Recife",
        "preco": preco,
        "partida": partida.isoformat(),
        "chegada": (partida + timedelta(hours=1, minutes=20)).isoformat(),
        "assentos": list(assentos),
        **extras,
    }


def dados_reserva(voo_id: int, assento="1A", documento="12345", email="ana@exemplo.com") -> dict:
    return {
        "voo_id": voo_id,
        "assento": assento,
        "passageiro": {"nome": "Ana Souza", "documento": documento, "email": email},
    }


def dados_cartao(numero=CARTAO_APROVADO, validade="12/35", cvv="123") -> dict:
    return {"titular": "ANA SOUZA", "numero": numero, "validade": validade, "cvv": cvv}


def assentos(client, voo_id: int) -> dict:
    return {a["numero"]: a["status"] for a in client.get(f"/voos/{voo_id}").json()["assentos"]}
