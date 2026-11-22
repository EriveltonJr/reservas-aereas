from collections.abc import Iterable
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.banco import configurar, criar_tabelas
from app.barramento import Barramento
from app.contratos import Container, PassageiroFalso, carregar_modulos
from app.seguranca import aplicar_cabecalhos_de_seguranca

WEB = Path(__file__).parent / "web"


def criar_app(url: str | None = None, modulos: Iterable[str] | None = None) -> FastAPI:
    engine = configurar(url)
    bus = Barramento()
    container = Container(engine, bus, PassageiroFalso())
    app = FastAPI(title="ELVoo · Reservas Aéreas")
    app.state.container = container
    app.state.bus = bus
    aplicar_cabecalhos_de_seguranca(app)

    @app.get("/", include_in_schema=False)
    def pagina() -> FileResponse:
        return FileResponse(WEB / "index.html")

    app.mount("/static", StaticFiles(directory=WEB), name="static")
    carregar_modulos(app, bus, container, modulos)
    criar_tabelas(engine)
    return app
