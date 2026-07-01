"""Enumerazioni condivise dai modelli."""

from __future__ import annotations

from enum import Enum


class CampaignMode(str, Enum):
    """Modalità di una campagna."""

    SINGLE = "single"  # un solo giocatore (dialogo diretto con Aedo)
    MULTI = "multi"    # gruppo, stile tavolo da gioco


class CampaignStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class CrunchLevel(str, Enum):
    """Quanto le meccaniche sono visibili al giocatore.

    Definito dal Blueprint: alcune campagne sono pura narrazione,
    altre mostrano HP, statistiche e tiri.
    """

    NARRATIVE = "narrative"  # meccaniche dietro le quinte
    BALANCED = "balanced"    # un po' di numeri visibili
    TACTICAL = "tactical"    # HP, stat, tiri pienamente esposti


class ObjectiveStatus(str, Enum):
    """Stato di un obiettivo / quest."""

    OPEN = "open"
    COMPLETED = "completed"
    FAILED = "failed"


class Outcome(str, Enum):
    """Esito a 3 gradi della risoluzione di un'azione (stile PbtA).

    È il cuore del motore universale: vale per qualsiasi azione rischiosa,
    in qualsiasi genere.
    """

    SUCCESS = "success"               # successo pieno
    SUCCESS_WITH_COST = "success_cost"  # riesci, ma con una complicazione
    FAILURE = "failure"               # fallimento (e la storia avanza lo stesso)


class CommandKind(str, Enum):
    """Tipo di ordine di regia che il master invia dal Banco al canale.

    Il Banco li accoda; il bot Discord li esegue nel canale della campagna.
    """

    INJECT_EVENT = "inject_event"    # posta un testo del master così com'è
    NARRATE_EVENT = "narrate_event"  # dà uno spunto: Aedo lo trasforma in scena
    OVERRIDE_LAST = "override_last"   # corregge l'ultimo esito e fa ri-narrare


class CommandStatus(str, Enum):
    """Ciclo di vita di un ordine di regia."""

    PENDING = "pending"  # in coda, il bot non l'ha ancora eseguito
    DONE = "done"        # eseguito e postato nel canale
    ERROR = "error"      # esecuzione fallita (vedi il campo error)
