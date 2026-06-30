"""Motore di risoluzione universale: dadi + esito a 3 gradi."""

from __future__ import annotations

from .dice import DiceRoll, DiceSpec, parse_dice, roll
from .engine import Difficulty, ResolutionResult, classify, resolve

__all__ = [
    "DiceSpec",
    "DiceRoll",
    "parse_dice",
    "roll",
    "Difficulty",
    "ResolutionResult",
    "classify",
    "resolve",
]
