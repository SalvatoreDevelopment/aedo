"""Endpoint del Quadro di Comando — accendere e spegnere i servizi.

Le leve d'ottone della UI parlano con questi endpoint. Il supervisore vive
nello stato dell'app (``app.state.supervisor``) così è un singleton condiviso
fra le richieste e sopravvive per tutta la vita del Banco.
"""

from __future__ import annotations

import webbrowser

from fastapi import APIRouter, HTTPException, Request

from . import schemas
from .supervisor import Supervisor

router = APIRouter(prefix="/admin/api/command", tags=["command"])


def _supervisor(request: Request) -> Supervisor:
    return request.app.state.supervisor


def _page_url(raw: str) -> str:
    """La pagina da mostrare: per l'API togliamo il suffisso /health."""
    return raw.replace("/health", "/")


@router.get("/services", response_model=list[schemas.ServiceStatus])
def list_services(request: Request):
    """Stato di tutti i servizi (per accendere le spie e disegnare le leve)."""
    return _supervisor(request).snapshot_all()


@router.post("/services/{key}/start", response_model=schemas.CommandResult)
def start_service(key: str, request: Request):
    svc = _supervisor(request).get(key)
    if svc is None:
        raise HTTPException(status_code=404, detail=f"Servizio {key!r} sconosciuto.")
    return svc.start()


@router.post("/services/{key}/stop", response_model=schemas.CommandResult)
def stop_service(key: str, request: Request):
    svc = _supervisor(request).get(key)
    if svc is None:
        raise HTTPException(status_code=404, detail=f"Servizio {key!r} sconosciuto.")
    return svc.stop()


@router.get("/services/{key}/logs")
def service_logs(key: str, request: Request, limit: int = 500):
    """Ultime righe di console del servizio (per il mini-terminale della UI)."""
    svc = _supervisor(request).get(key)
    if svc is None:
        raise HTTPException(status_code=404, detail=f"Servizio {key!r} sconosciuto.")
    return {"key": key, "lines": svc.tail(limit)}


@router.post("/services/{key}/open")
def open_service(key: str, request: Request):
    """Apre la pagina del servizio nel browser di sistema.

    Dall'app desktop un link ``target=_blank`` non apre nulla; qui invece è il
    processo del Banco (che gira sul PC del master) a lanciare il browser
    predefinito — affidabile sia in finestra nativa sia nel browser.
    """
    svc = _supervisor(request).get(key)
    if svc is None:
        raise HTTPException(status_code=404, detail=f"Servizio {key!r} sconosciuto.")
    if not svc.spec.url:
        raise HTTPException(status_code=400, detail="Questo servizio non ha una pagina da aprire.")
    url = _page_url(svc.spec.url)
    webbrowser.open(url)
    return {"key": key, "opened": url}
