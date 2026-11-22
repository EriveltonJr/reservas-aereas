import os

from numpy import isclose

from app.barramento import Barramento
from app.eventos import (
    AssentoBloqueado,
    PagamentoAprovado,
    PagamentoRecusado,
)

class PagamentoService:
    def __init__(self, bus: Barramento) -> None:
        self.bus = bus
        self._processados: set[int] = set()


    def obter_valor_pagamento(self, evento: AssentoBloqueado) -> float:
        return float(evento.valor)
    
    def processar(self, evento: AssentoBloqueado) -> None:
        if evento.reserva_id in self._processados:
            return

        valor_pago = self.obter_valor_pagamento(evento)
        valor_voo = float(evento.valor)

        if not isclose(valor_pago, valor_voo):
            self._processados.add(evento.reserva_id)
            self.bus.publicar(PagamentoRecusado(reserva_id=evento.reserva_id, motivo=(
                        "Valor do pagamento diferente do valor do voo: "
                        f"esperado R$ {valor_voo:.2f}, "
                        f"recebido R$ {valor_pago:.2f}"
                    ),))
            return

        self._processados.add(evento.reserva_id)
        self.bus.publicar(PagamentoAprovado(reserva_id=evento.reserva_id, pagamento_id=evento.reserva_id, valor=valor_pago))