"""Motore di risoluzione — il cuore universale di Aedo.

Un solo meccanismo per ogni azione rischiosa, in ogni genere: si tira un dado,
si somma l'attributo rilevante e si confronta con una difficoltà. L'esito non è
binario ma a tre gradi (stile Powered-by-the-Apocalypse):

    tiro >= difficoltà                  → SUCCESS (riesci)
    difficoltà - banda <= tiro < diff   → SUCCESS_WITH_COST (riesci, ma…)
    tiro < difficoltà - banda           → FAILURE (fallisci, e la storia avanza)

La "banda" è la fascia di mancato-di-poco che diventa successo con complicazione;
è configurabile dal Blueprint. Chi sceglie *quale* attributo e *quanta* difficoltà
è il narratore (Fase 2): qui la meccanica è pura e deterministica.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from aedo.core.models.enums import Outcome
from .dice import roll


class Difficulty(IntEnum):
    """Soglie di difficoltà che il narratore può assegnare a un'azione.

    Tarate su un tiro base `2d6 + attributo` (attributo tipico 0–4).
    """

    TRIVIAL = 6
    EASY = 8
    MEDIUM = 10
    HARD = 12
    EXTREME = 14


@dataclass
class ResolutionResult:
    """Esito completo di una risoluzione, trasparente e tracciabile.

    Pensato per essere salvato in `EventLog.roll` e mostrato al giocatore.
    """

    outcome: Outcome
    attribute_name: str
    attribute_value: int
    difficulty: int
    dice_formula: str
    dice_rolls: list[int]
    modifier: int = 0
    total: int = 0
    margin: int = 0  # total - difficulty (negativo = sotto soglia)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Forma serializzabile, adatta a `EventLog.roll`."""
        return {
            "outcome": self.outcome.value,
            "attribute": self.attribute_name,
            "attribute_value": self.attribute_value,
            "difficulty": self.difficulty,
            "dice": self.dice_formula,
            "rolls": self.dice_rolls,
            "modifier": self.modifier,
            "total": self.total,
            "margin": self.margin,
            **({"extra": self.extra} if self.extra else {}),
        }

    @property
    def summary(self) -> str:
        """Riga sintetica, es. `Intuito · 14 vs 12`."""
        return f"{self.attribute_name} · {self.total} vs {self.difficulty}"


def classify(total: int, difficulty: int, band: int) -> Outcome:
    """Traduce un tiro confrontato con la difficoltà in un esito a 3 gradi."""
    if total >= difficulty:
        return Outcome.SUCCESS
    if total >= difficulty - band:
        return Outcome.SUCCESS_WITH_COST
    return Outcome.FAILURE


def resolve(
    *,
    attribute_name: str,
    attribute_value: int,
    difficulty: int | Difficulty,
    dice_formula: str = "2d6",
    modifier: int = 0,
    band: int = 2,
    rng: random.Random | None = None,
) -> ResolutionResult:
    """Risolve un'azione rischiosa.

    Parameters
    ----------
    attribute_name / attribute_value:
        L'attributo rilevante del personaggio (definito dal Blueprint) e il suo valore.
    difficulty:
        Soglia da superare; il narratore la sceglie in base alla situazione.
    dice_formula:
        Formula del dado, dal Blueprint (default `2d6`).
    modifier:
        Bonus/malus situazionale (vantaggio, ferita, oggetto…).
    band:
        Ampiezza della fascia "riesci, ma…" sotto la soglia (dal Blueprint).
    rng:
        Generatore casuale iniettabile (per test deterministici).
    """
    dice_roll = roll(dice_formula, rng=rng)
    total = dice_roll.total + attribute_value + modifier
    difficulty_value = int(difficulty)
    outcome = classify(total, difficulty_value, band)
    return ResolutionResult(
        outcome=outcome,
        attribute_name=attribute_name,
        attribute_value=attribute_value,
        difficulty=difficulty_value,
        dice_formula=str(dice_roll.spec),
        dice_rolls=dice_roll.rolls,
        modifier=modifier,
        total=total,
        margin=total - difficulty_value,
    )
