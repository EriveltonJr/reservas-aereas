from app.barramento import Barramento
from app.eventos import (
    AssentoBloqueado,
    PagamentoAprovado,
    PagamentoRecusado,
)
from app.modulos.pagamentos.service import PagamentoService


def evento_pagamento(valor: float = 500.0) -> AssentoBloqueado:
    return AssentoBloqueado(
        reserva_id=1,
        voo_id=10,
        assento="1A",
        valor=valor,
    )


def test_valor_igual_ao_voo_aprova_pagamento():
    bus = Barramento()
    publicados = []
    bus.inscrever(PagamentoAprovado, publicados.append)

    servico = PagamentoService(bus)
    servico.processar(evento_pagamento(500.0))

    assert publicados == [PagamentoAprovado(1, 1, 500.0)]


def test_valor_diferente_do_voo_recusa_pagamento():
    bus = Barramento()
    publicados = []
    bus.inscrever(PagamentoRecusado, publicados.append)

    servico = PagamentoService(bus)
    servico.obter_valor_pagamento = lambda evento: 450.0
    servico.processar(evento_pagamento(500.0))

    assert len(publicados) == 1
    assert publicados[0].reserva_id == 1
    assert "diferente" in publicados[0].motivo
    assert "500.00" in publicados[0].motivo
    assert "450.00" in publicados[0].motivo


def test_pagamento_repetido_para_a_mesma_reserva_e_ignorado():
    bus = Barramento()
    publicados = []
    bus.inscrever(PagamentoAprovado, publicados.append)

    servico = PagamentoService(bus)
    evento = evento_pagamento(500.0)
    servico.processar(evento)
    servico.processar(evento)

    assert publicados == [PagamentoAprovado(1, 1, 500.0)]
