"""Definizione dei servizi che il Banco del Master accende e spegne.

Tre componenti, avviati esattamente come li avvieresti a mano:

* **API giocatore** — ``python -m aedo.api``           (http://127.0.0.1:8000)
* **Bot Discord**   — ``python -m aedo.bots.discord``
* **Web giocatore** — ``npm run dev`` in ``aedo/web``  (http://127.0.0.1:5173)

Usiamo lo stesso interprete Python del Banco (``sys.executable`` → il venv
attivo) così i sottoprocessi ereditano le stesse dipendenze. Per la web
cerchiamo ``npm`` sul PATH; se manca (o mancano i ``node_modules``) il servizio
è segnalato come *non disponibile* con un suggerimento, invece di fallire a
sorpresa.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from .supervisor import ServiceSpec, Supervisor

# Radice del repo: .../aedo/admin/services.py → su di due livelli.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = PROJECT_ROOT / "aedo" / "web"


def _api_command() -> list[str]:
    return [sys.executable, "-m", "aedo.api"]


def _bot_command() -> list[str]:
    return [sys.executable, "-m", "aedo.bots.discord"]


def _web_command() -> list[str] | None:
    """Comando per la web giocatore, o ``None`` se non avviabile qui."""
    npm = shutil.which("npm")
    if npm is None:
        return None
    if not (WEB_DIR / "node_modules").is_dir():
        return None
    return [npm, "run", "dev"]


def _web_unavailable_hint() -> str:
    if shutil.which("npm") is None:
        return "npm non trovato sul PATH: installa Node.js per usare la web giocatore."
    if not (WEB_DIR / "node_modules").is_dir():
        return "Dipendenze mancanti: esegui 'npm install' in aedo/web una volta."
    return ""


def build_service_specs() -> list[ServiceSpec]:
    """Le tre leve del Quadro di Comando, nell'ordine mostrato in UI."""
    return [
        ServiceSpec(
            key="api",
            label="API giocatore",
            description="Il server che alimenta la dashboard di sola lettura.",
            command=_api_command,
            cwd=str(PROJECT_ROOT),
            url="http://127.0.0.1:8000/health",
        ),
        ServiceSpec(
            key="bot",
            label="Bot Discord",
            description="Aedo in ascolto sui canali: è qui che si gioca.",
            command=_bot_command,
            cwd=str(PROJECT_ROOT),
        ),
        ServiceSpec(
            key="web",
            label="Web giocatore",
            description="La dashboard React che i giocatori consultano.",
            command=_web_command,
            cwd=str(WEB_DIR),
            url="http://127.0.0.1:5173",
            unavailable_hint=_web_unavailable_hint(),
        ),
    ]


def build_supervisor() -> Supervisor:
    return Supervisor(build_service_specs())
