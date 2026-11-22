from app.eventos import (
    AssentoIndisponivel,
    CancelamentoSolicitado,
    CancelarReserva,
    LiberarAssento,
    PagamentoRecusado,
    PrazoPagamentoExpirado,
)


def test_assento_indisponivel_cancela_a_reserva(sistema):
    s = sistema("saga")

    s.bus.publicar(AssentoIndisponivel(reserva_id=3, motivo="Assento já ocupado"))

    assert s.publicados(CancelarReserva) == [CancelarReserva(3, "Assento já ocupado")]


def test_prazo_expirado_libera_assento_e_cancela_reserva(sistema):
    s = sistema("saga")

    s.bus.publicar(PrazoPagamentoExpirado(reserva_id=4))

    assert s.publicados(LiberarAssento) == [LiberarAssento(4)]
    assert s.publicados(CancelarReserva) == [CancelarReserva(4, "Prazo para pagamento expirado")]


def test_cancelamento_solicitado_libera_assento_e_cancela_reserva(sistema):
    s = sistema("saga")

    s.bus.publicar(CancelamentoSolicitado(reserva_id=5, motivo="Cancelada pelo cliente"))

    assert s.publicados(LiberarAssento) == [LiberarAssento(5)]
    assert s.publicados(CancelarReserva) == [CancelarReserva(5, "Cancelada pelo cliente")]


def test_tentativa_de_pagamento_recusada_nao_cancela(sistema):
    s = sistema("saga")

    s.bus.publicar(PagamentoRecusado(reserva_id=6, motivo="Saldo insuficiente"))

    assert s.publicados(CancelarReserva) == []
