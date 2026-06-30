"""App FastAPI per la dashboard web di Aedo.

Avvio:  python -m aedo.api   (oppure: uvicorn aedo.api.app:app --reload)
Serve l'API di sola lettura su /api; la dashboard React la consuma.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aedo.storage import init_db
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Aedo API", version="0.1.0", lifespan=lifespan)

# In sviluppo la dashboard gira su un'altra porta (Vite): permettiamo il CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
