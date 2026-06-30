"""Tiri di dado, configurabili tramite formula testuale.

Una formula è del tipo `NdM`, opzionalmente con un modificatore:
`2d6`, `1d20`, `3d6+1`, `d8-1`. Il tipo di dado è una scelta del Blueprint
(un noir narrativo può usare `2d6`, un gioco più "swingy" un `1d20`).

Il generatore casuale è iniettabile: passando un `random.Random` con seed
i tiri diventano deterministici, il che rende il motore testabile.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

_DICE_RE = re.compile(r"^\s*(\d*)d(\d+)\s*([+-]\s*\d+)?\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class DiceSpec:
    """Una formula di dado già interpretata."""

    count: int
    sides: int
    modifier: int

    def __str__(self) -> str:
        base = f"{self.count}d{self.sides}"
        if self.modifier:
            base += f"{self.modifier:+d}"
        return base


@dataclass(frozen=True)
class DiceRoll:
    """Il risultato di un tiro."""

    spec: DiceSpec
    rolls: list[int]
    total: int  # somma dei dadi + modificatore della formula


def parse_dice(formula: str) -> DiceSpec:
    """Interpreta una formula come `2d6+1`. Solleva ValueError se invalida."""
    match = _DICE_RE.match(formula)
    if not match:
        raise ValueError(f"Formula di dado non valida: {formula!r}")
    count_str, sides_str, mod_str = match.groups()
    count = int(count_str) if count_str else 1
    sides = int(sides_str)
    modifier = int(mod_str.replace(" ", "")) if mod_str else 0
    if count < 1 or sides < 2:
        raise ValueError(f"Formula di dado fuori range: {formula!r}")
    return DiceSpec(count=count, sides=sides, modifier=modifier)


def roll(formula: str, rng: random.Random | None = None) -> DiceRoll:
    """Tira la formula indicata e restituisce il dettaglio del tiro."""
    spec = parse_dice(formula)
    generator = rng or random
    rolls = [generator.randint(1, spec.sides) for _ in range(spec.count)]
    return DiceRoll(spec=spec, rolls=rolls, total=sum(rolls) + spec.modifier)
