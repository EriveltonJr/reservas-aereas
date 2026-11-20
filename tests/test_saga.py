from app.eventos import (
    AssentoIndisponivel,
    CancelarReserva,
    LiberarAssento,
    PagamentoRecusado,
)


def test_assento_indisponivel_cancela_a_reserva(sistema):
    s = sistema("saga")

    s.bus.publicar(
        AssentoIndisponivel(
            reserva_id=3,
            motivo="Assento já ocupado",
        )
    )

    assert s.publicados(CancelarReserva) == [
        CancelarReserva(3, "Assento já ocupado")
    ]


def test_pagamento_recusado_libera_assento_e_cancela_reserva(sistema):
    s = sistema("saga")

    s.bus.publicar(
        PagamentoRecusado(
            reserva_id=4,
            motivo="Valor do pagamento diferente do valor do voo",
        )
    )

    assert s.publicados(LiberarAssento) == [LiberarAssento(4)]
    assert s.publicados(CancelarReserva) == [
        CancelarReserva(4, "Valor do pagamento diferente do valor do voo")
    ]
