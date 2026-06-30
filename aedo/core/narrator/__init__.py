"""Il narratore (Aedo): interfaccia astratta e implementazioni."""

from __future__ import annotations

from .base import (
    Assessment,
    Narration,
    NarratorContext,
    NarratorProvider,
    StateChanges,
)
from .fake import FakeNarrator

__all__ = [
    "NarratorProvider",
    "NarratorContext",
    "Assessment",
    "Narration",
    "StateChanges",
    "FakeNarrator",
    "get_narrator",
]


def get_narrator(name: str = "openrouter", **kwargs) -> NarratorProvider:
    """Factory: restituisce il narratore richiesto.

    `OpenRouterNarrator` è importato pigramente per non richiedere la chiave
    (né la rete) quando si usa solo il narratore finto.
    """
    key = name.strip().lower()
    if key == "fake":
        return FakeNarrator(**kwargs)
    if key in ("openrouter", "openai"):
        from .openrouter import OpenRouterNarrator

        return OpenRouterNarrator(**kwargs)
    raise ValueError(f"Narratore sconosciuto: {name!r}")
