"""App FastAPI del Banco del Master.

Serve la propria interfaccia statica (nessun build step) e monta i due gruppi di
endpoint: Quadro di Comando e Controllo dello Stato. Il supervisore dei processi
vive nello stato dell'app per l'intera durata del Banco e viene spento con
grazia alla chiusura (così non restano bot o server orfani).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from aedo.storage import init_db
from .routes_command import router as command_router
from .routes_state import router as state_router
from .services import build_supervisor

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.supervisor = build_supervisor()
    try:
        yield
    finally:
        # Alla chiusura del Banco, spegni tutto ciò che aveva acceso.
        app.state.supervisor.stop_all()


app = FastAPI(title="Aedo — Banco del Master", version="0.1.0", lifespan=lifespan)

app.include_router(command_router)
app.include_router(state_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# Asset statici (CSS/JS) sotto /static.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
