"""Il Banco del Master come **app desktop nativa** (finestra Windows propria).

Non è un sito nel browser: la stessa interfaccia (grafica del tavolo del master)
viene mostrata dentro una finestra desktop tutta sua, tramite ``pywebview`` — che
su Windows usa il motore Edge (WebView2) già presente nel sistema. Zero barra
degli indirizzi, zero browser.

Come funziona:

* il server FastAPI parte in un **thread in sottofondo** (serve la UI e le API su
  una porta locale, non esposta all'esterno);
* la **finestra** pywebview gira nel thread principale (requisito delle GUI) e
  carica quella pagina;
* quando chiudi la finestra, il server viene fermato con grazia → il suo shutdown
  spegne anche i servizi eventualmente accesi dal Quadro di Comando (niente bot o
  server lasciati orfani).
"""

from __future__ import annotations

import socket
import threading
import time

import uvicorn
import webview

from .app import app

HOST = "127.0.0.1"
PORT = 8100
WINDOW_TITLE = "Il Banco del Master — Aedo"


def _port_is_open(host: str, port: int, timeout: float = 0.25) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def _wait_until_up(timeout: float = 20.0) -> bool:
    """Aspetta che il server risponda, così la finestra non apre una pagina vuota."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_is_open(HOST, PORT):
            return True
        time.sleep(0.1)
    return False


def main() -> None:
    # 1) Server FastAPI in sottofondo (thread, non processo: condivide lo stato).
    config = uvicorn.Config(app, host=HOST, port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    if not _wait_until_up():
        raise RuntimeError("Il server del Banco non si è avviato in tempo.")

    # 2) Finestra desktop nativa con la nostra interfaccia.
    webview.create_window(
        WINDOW_TITLE,
        f"http://{HOST}:{PORT}/",
        width=1200,
        height=920,
        min_size=(940, 640),
    )
    # Bloccante: ritorna quando la finestra viene chiusa.
    webview.start()

    # 3) Chiusura pulita: fai terminare il server → esegue lo shutdown del lifespan
    #    (che spegne i servizi accesi dal Quadro di Comando).
    server.should_exit = True
    server_thread.join(timeout=10)


if __name__ == "__main__":
    main()
