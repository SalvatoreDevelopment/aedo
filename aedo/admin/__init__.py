"""Il Banco del Master — dashboard di amministrazione / regia di Aedo.

Processo separato dall'API giocatore e dal bot: gira in locale sul PC del
master, serve la propria interfaccia (estetica "tavolo da gioco") e ha due
poteri che la dashboard giocatore non ha:

* **Quadro di Comando** — accende e spegne gli altri servizi come sottoprocessi
  (bot Discord, API giocatore, web giocatore) e ne mostra stato e log.
* **Controllo dello Stato** — scrive direttamente sul database della campagna
  (risorse, inventario, relazioni, obiettivi, NPC), anche a servizi spenti.

Avvio:  ``python -m aedo.admin``  (oppure doppio click su ``Banco-del-Master.bat``)
"""

from __future__ import annotations
