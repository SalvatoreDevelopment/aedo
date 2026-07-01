"""Supervisore di processi del Banco del Master.

Avvia, ferma e sorveglia gli altri componenti di Aedo come **sottoprocessi**:
il master accende SOLO il Banco, e da lì — con le "leve" del Quadro di Comando —
accende/spegne bot Discord, API giocatore e web giocatore. Niente più tre
terminali PowerShell aperti a mano.

Scelte tecniche (target: Windows):

* ogni servizio è un ``subprocess.Popen``; ne tracciamo il PID;
* stdout+stderr sono catturati riga per riga da un thread dedicato e tenuti in
  un ring-buffer (le ultime N righe) da mostrare come mini-console;
* lo stop termina l'**intero albero** di processi (``taskkill /T`` su Windows,
  ``killpg`` altrove): serve perché ``npm run dev`` genera figli (node/esbuild)
  che un kill del solo padre lascerebbe orfani;
* distinguiamo un'uscita **volontaria** (abbiamo chiesto lo stop) da un
  **crash** (il processo muore da solo) → stato ``stopped`` vs ``errored``.

Il supervisore è deliberatamente ignaro di *cosa* siano i servizi: riceve una
lista di :class:`ServiceSpec`. Così la logica è testabile con comandi finti,
senza avviare davvero bot o server.
"""

from __future__ import annotations

import re
import subprocess
import sys
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable

# Sequenze di escape ANSI (colori/stile) che strumenti come Vite emettono:
# vanno tolte o la console del Banco le mostra come caratteri illeggibili.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


class ServiceState(str, Enum):
    """Stato corrente di un servizio gestito."""

    STOPPED = "stopped"      # mai avviato, o fermato volontariamente
    RUNNING = "running"      # sottoprocesso vivo
    ERRORED = "errored"      # morto da solo (crash / exit != 0)
    UNAVAILABLE = "unavailable"  # non avviabile qui (es. manca npm/node_modules)


@dataclass(frozen=True)
class ServiceSpec:
    """Descrizione dichiarativa di un servizio avviabile.

    ``command`` è una *factory* (non una lista statica) così il comando può
    essere risolto al momento dell'avvio — utile per trovare ``npm`` sul PATH
    o per rilevare che il servizio non è avviabile (ritorna ``None``).
    """

    key: str                       # id macchina, es. "api"
    label: str                     # nome mostrato, es. "API giocatore"
    description: str               # una riga di spiegazione per la UI
    command: Callable[[], list[str] | None]
    cwd: str | None = None         # directory di lavoro del processo
    url: str | None = None         # link "apri" (se il servizio espone una pagina)
    unavailable_hint: str = ""     # perché non è avviabile (se command() è None)


@dataclass
class _Runtime:
    """Stato mutabile di un servizio (separato dalla spec, che è immutabile)."""

    proc: subprocess.Popen | None = None
    state: ServiceState = ServiceState.STOPPED
    started_at: datetime | None = None
    exit_code: int | None = None
    stopping: bool = False
    logs: deque[str] = field(default_factory=lambda: deque(maxlen=500))
    reader: threading.Thread | None = None


# Su Windows: nuovo gruppo di processi, così possiamo terminare l'albero.
_CREATE_NEW_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


class ManagedService:
    """Un singolo servizio sotto supervisione."""

    def __init__(self, spec: ServiceSpec) -> None:
        self.spec = spec
        self._rt = _Runtime()
        self._lock = threading.Lock()

    # -- interrogazione ----------------------------------------------------
    @property
    def state(self) -> ServiceState:
        with self._lock:
            self._refresh_locked()
            return self._rt.state

    def snapshot(self) -> dict:
        """Fotografia serializzabile per l'API."""
        with self._lock:
            self._refresh_locked()
            rt = self._rt
            return {
                "key": self.spec.key,
                "label": self.spec.label,
                "description": self.spec.description,
                "url": self.spec.url,
                "state": rt.state.value,
                "pid": rt.proc.pid if rt.proc and rt.state is ServiceState.RUNNING else None,
                "started_at": rt.started_at.isoformat() if rt.started_at else None,
                "exit_code": rt.exit_code,
                "unavailable_hint": self.spec.unavailable_hint
                if rt.state is ServiceState.UNAVAILABLE else "",
            }

    def tail(self, limit: int = 200) -> list[str]:
        """Ultime righe di log (le più recenti in fondo)."""
        with self._lock:
            return list(self._rt.logs)[-limit:]

    # -- controllo ---------------------------------------------------------
    def start(self) -> dict:
        with self._lock:
            self._refresh_locked()
            if self._rt.state is ServiceState.RUNNING:
                return self._result_locked("Già in esecuzione.")

            cmd = self.spec.command()
            if cmd is None:
                self._rt.state = ServiceState.UNAVAILABLE
                self._log_locked(f"[banco] non avviabile: {self.spec.unavailable_hint}")
                return self._result_locked(self.spec.unavailable_hint or "Non avviabile.")

            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=self.spec.cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=_CREATE_NEW_GROUP,
                )
            except (OSError, ValueError) as exc:
                self._rt.state = ServiceState.ERRORED
                self._log_locked(f"[banco] avvio fallito: {exc}")
                return self._result_locked(f"Avvio fallito: {exc}")

            self._rt.proc = proc
            self._rt.state = ServiceState.RUNNING
            self._rt.started_at = datetime.now()
            self._rt.exit_code = None
            self._rt.stopping = False
            self._log_locked(f"[banco] avviato (pid {proc.pid}): {' '.join(cmd)}")
            self._rt.reader = threading.Thread(
                target=self._pump_output, args=(proc,), daemon=True
            )
            self._rt.reader.start()
            return self._result_locked("Avviato.")

    def stop(self) -> dict:
        with self._lock:
            self._refresh_locked()
            proc = self._rt.proc
            if proc is None or self._rt.state is not ServiceState.RUNNING:
                self._rt.state = ServiceState.STOPPED
                return self._result_locked("Già fermo.")
            self._rt.stopping = True
            self._log_locked("[banco] arresto richiesto…")

        # Terminazione fuori dal lock: può richiedere qualche istante.
        _terminate_tree(proc)
        with self._lock:
            self._rt.state = ServiceState.STOPPED
            self._rt.exit_code = proc.poll()
            return self._result_locked("Fermato.")

    # -- interni -----------------------------------------------------------
    def _refresh_locked(self) -> None:
        """Aggiorna lo stato se il processo è morto da solo."""
        proc = self._rt.proc
        if proc is None:
            return
        code = proc.poll()
        if code is None:
            return  # ancora vivo
        # Il processo è terminato.
        if self._rt.state is ServiceState.RUNNING:
            self._rt.exit_code = code
            if self._rt.stopping or code == 0:
                self._rt.state = ServiceState.STOPPED
            else:
                self._rt.state = ServiceState.ERRORED
                self._log_locked(f"[banco] terminato inaspettatamente (codice {code})")

    def _pump_output(self, proc: subprocess.Popen) -> None:
        """Thread: travasa stdout del processo nel ring-buffer."""
        stream = proc.stdout
        if stream is None:
            return
        try:
            for line in stream:
                clean = _ANSI_RE.sub("", line.rstrip("\n"))
                with self._lock:
                    self._log_locked(clean)
        except (ValueError, OSError):
            pass  # stream chiuso durante lo stop

    def _log_locked(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self._rt.logs.append(f"{stamp}  {message}")

    def _result_locked(self, message: str) -> dict:
        return {"key": self.spec.key, "state": self._rt.state.value, "message": message}


class Supervisor:
    """Insieme dei servizi gestiti dal Banco del Master."""

    def __init__(self, specs: list[ServiceSpec]) -> None:
        self._services: dict[str, ManagedService] = {
            spec.key: ManagedService(spec) for spec in specs
        }

    def get(self, key: str) -> ManagedService | None:
        return self._services.get(key)

    def snapshot_all(self) -> list[dict]:
        return [svc.snapshot() for svc in self._services.values()]

    def stop_all(self) -> None:
        """Ferma tutti i servizi vivi (chiamato alla chiusura del Banco)."""
        for svc in self._services.values():
            if svc.state is ServiceState.RUNNING:
                svc.stop()


def _terminate_tree(proc: subprocess.Popen, timeout: float = 8.0) -> None:
    """Termina un processo e tutti i suoi figli.

    Su Windows ``taskkill /T /F`` uccide l'intero albero (indispensabile per
    ``npm``, che genera node/esbuild). Altrove si tenta un ``terminate`` gentile
    e, se non basta, ``kill``.
    """
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=timeout,
            )
        except (subprocess.SubprocessError, OSError):
            proc.kill()
    else:
        proc.terminate()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
