from collections import defaultdict
from collections.abc import Callable

from app.eventos import Evento

Tratador = Callable[[Evento], None]


class Barramento:
    def __init__(self) -> None:
        self._inscritos: dict[type[Evento], list[Tratador]] = defaultdict(list)
        self._fila: list[Evento] = []
        self._em_entrega = False

    def inscrever(self, tipo: type[Evento], tratador: Tratador) -> None:
        if not isinstance(tipo, type) or not issubclass(tipo, Evento):
            raise TypeError("inscreva uma classe de evento")
        self._inscritos[tipo].append(tratador)

    def publicar(self, evento: Evento) -> None:
        if not isinstance(evento, Evento):
            raise TypeError("o barramento só publica eventos")
        self._fila.append(evento)
        if self._em_entrega:
            return
        self._em_entrega = True
        try:
            while self._fila:
                atual = self._fila.pop(0)
                for tratador in list(self._inscritos.get(type(atual), [])):
                    tratador(atual)
        except Exception:
            self._fila.clear()
            raise
        finally:
            self._em_entrega = False
