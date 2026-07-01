"""Entry point del Banco del Master:  python -m aedo.admin

Apre il Banco come **app desktop nativa** (una finestra Windows tutta sua, non
il browser). È l'unico programma che il master lancia a mano — doppio click su
``Banco-del-Master.bat`` — e da dentro il Quadro di Comando accende il resto.

Per il solo server (senza finestra, utile in sviluppo):
    uvicorn aedo.admin.app:app --port 8100
"""

from __future__ import annotations

from .desktop import main

if __name__ == "__main__":
    main()
