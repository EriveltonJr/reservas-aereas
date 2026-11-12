from collections.abc import Iterable
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.banco import configurar, criar_tabelas
from app.barramento import Barramento
from app.contratos import Container, PassageiroFalso, carregar_modulos

PAGINA = Path(__file__).parent / "web" / "index.html"


def criar_app(url: str | None = None, modulos: Iterable[str] | None = None) -> FastAPI:
    engine = configurar(url)
    bus = Barramento()
    container = Container(engine, bus, PassageiroFalso())
    app = FastAPI(title="Reservas Aéreas")
    app.state.container = container
    app.state.bus = bus

    @app.get("/", include_in_schema=False)
    def pagina() -> FileResponse:
        return FileResponse(PAGINA)

    carregar_modulos(app, bus, container, modulos)
    criar_tabelas(engine)
    return app
