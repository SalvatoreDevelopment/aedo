"""Interfaccia astratta del narratore (Aedo) e contratti dei dati.

Principio cardine: **il codice tiene lo stato, l'AI propone soltanto**. Il
narratore non scrive nel database: restituisce dati strutturati (esito atteso,
narrazione, cambiamenti proposti) che il game loop applica in modo controllato.

Esistono due implementazioni:
- `OpenRouterNarrator` — il vero modello via OpenRouter.
- `FakeNarrator` — deterministico, per test e gioco offline senza chiave.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from aedo.core.resolution import ResolutionResult


@dataclass
class NarratorContext:
    """Tutto ciò che serve al narratore per ragionare su un turno.

    Lo costruisce il game loop a partire dallo stato della campagna.
    """

    # --- Dal Blueprint (le regole del genere) ---
    genre: str
    tone: str
    narrator_persona: str
    special_rules: str
    crunch_level: str
    attribute_names: list[str]
    difficulty_options: list[str]

    # --- Dal personaggio che agisce ---
    character_name: str
    character_description: str
    character_attributes: dict[str, int]
    character_resources: dict[str, int]
    character_conditions: list[str]

    # --- Dalla situazione ---
    current_summary: str
    recent_events: list[str] = field(default_factory=list)
    relevant_memories: list[str] = field(default_factory=list)  # Fase 3

    # --- L'input del giocatore ---
    player_action: str = ""


@dataclass
class Assessment:
    """Valutazione di un'azione: serve un tiro? con quale attributo e difficoltà?"""

    is_risky: bool
    attribute: str | None = None      # nome di un attributo del Blueprint
    difficulty: str | None = None     # uno dei difficulty_options (es. "hard")
    reason: str = ""                  # breve motivazione (per trasparenza/log)


@dataclass
class StateChanges:
    """Cambiamenti di stato proposti dal narratore dopo un turno.

    Tutti opzionali: un turno tranquillo può non cambiare nulla.
    """

    resource_deltas: dict[str, int] = field(default_factory=dict)
    conditions_add: list[str] = field(default_factory=list)
    conditions_remove: list[str] = field(default_factory=list)
    # Personaggi (NPC) verso cui cambia una relazione: {name, kind?, affinity_delta}
    relationship_changes: list[dict] = field(default_factory=list)
    new_items: list[dict] = field(default_factory=list)        # {name, description?, quantity?}
    removed_items: list[str] = field(default_factory=list)     # per nome
    new_objectives: list[dict] = field(default_factory=list)   # {title, description?}
    completed_objectives: list[str] = field(default_factory=list)  # per titolo
    # Un ricordo saliente da memorizzare (memoria narrativa, Fase 3).
    memory: str | None = None
    memory_importance: float = 0.5


@dataclass
class Narration:
    """L'output narrativo di un turno."""

    text: str
    new_summary: str | None = None  # aggiorna la "scena" corrente, se cambiata
    changes: StateChanges = field(default_factory=StateChanges)
    # Titolo proposto per la campagna (solo nella scena d'apertura, se l'utente
    # non ne ha dato uno).
    title: str | None = None


class NarratorProvider(ABC):
    """Contratto comune a tutti i narratori."""

    name: str = "base"

    @abstractmethod
    def open_scene(self, ctx: NarratorContext, premise: str = "") -> Narration:
        """Genera la scena di apertura di una campagna.

        Colloca il personaggio in un luogo e una situazione concreti e offre un
        gancio iniziale. `premise` è uno spunto facoltativo del giocatore; se
        vuoto, il narratore inventa l'incipit dal genere.
        """

    @abstractmethod
    def assess(self, ctx: NarratorContext) -> Assessment:
        """Decide se l'azione del giocatore richiede un tiro, e con quali parametri."""

    @abstractmethod
    def narrate(
        self, ctx: NarratorContext, resolution: ResolutionResult | None
    ) -> Narration:
        """Narra l'esito e propone i cambiamenti di stato.

        `resolution` è None per le azioni libere (nessun tiro).
        """

    def turn(self, ctx: NarratorContext) -> tuple[Assessment, Narration | None]:
        """Valuta l'azione e, se non rischiosa, ne narra subito l'esito.

        Default in due chiamate (assess + narrate). I provider che sanno fondere
        le due cose in una sola chiamata sovrascrivono questo metodo per
        dimezzare la latenza delle azioni libere. Restituisce
        `(assessment, narration)`: narration è None se l'azione è rischiosa —
        in tal caso il game loop tira e poi chiama `narrate()`.
        """
        assessment = self.assess(ctx)
        if assessment.is_risky:
            return assessment, None
        return assessment, self.narrate(ctx, None)
