"""Narratore finto, deterministico — per test e gioco offline senza chiave.

Non chiama alcun modello: applica un'euristica trasparente per decidere se
un'azione è rischiosa e genera una narrazione di servizio. Permette di provare
l'intero game loop (e di sviluppare bot e web) senza spendere credito.
"""

from __future__ import annotations

from aedo.core.resolution import ResolutionResult
from .base import Assessment, Narration, NarratorContext, NarratorProvider, StateChanges

# Verbi che suggeriscono un'azione con posta in gioco.
_RISKY_HINTS = (
    "attacc", "colpisc", "seguo", "pedino", "scass", "minacc", "rubo", "salto",
    "fuggo", "corro", "combatto", "sparo", "hackero", "seduco", "bacio",
    "convinco", "intruf", "arrampic", "nascond", "spingo", "lancio",
)


class FakeNarrator(NarratorProvider):
    name = "fake"

    def __init__(
        self,
        *,
        force_risky: bool | None = None,
        attribute: str | None = None,
        difficulty: str = "medium",
        scripted_changes: StateChanges | None = None,
    ) -> None:
        self._force_risky = force_risky
        self._attribute = attribute
        self._difficulty = difficulty
        self._scripted_changes = scripted_changes

    def open_scene(self, ctx: NarratorContext, premise: str = "") -> Narration:
        spunto = f" Tema: {premise}." if premise.strip() else ""
        text = (
            f"[Apertura · {ctx.genre}]{spunto} {ctx.character_name}, la tua storia comincia. "
            "Intorno a te la scena prende forma e qualcosa reclama la tua attenzione. "
            "Cosa fai?"
        )
        return Narration(
            text=text,
            new_summary=f"{ctx.character_name} è all'inizio della propria avventura.",
            changes=StateChanges(
                new_objectives=[{"title": "Capire cosa sta succedendo", "description": ""}]
            ),
            title=f"La storia di {ctx.character_name}",
        )

    def assess(self, ctx: NarratorContext) -> Assessment:
        if self._force_risky is not None:
            risky = self._force_risky
        else:
            text = ctx.player_action.lower()
            risky = any(h in text for h in _RISKY_HINTS)
        if not risky:
            return Assessment(is_risky=False, reason="azione libera")
        attribute = self._attribute or (ctx.attribute_names[0] if ctx.attribute_names else None)
        return Assessment(
            is_risky=True,
            attribute=attribute,
            difficulty=self._difficulty,
            reason="azione con posta in gioco",
        )

    def narrate(
        self, ctx: NarratorContext, resolution: ResolutionResult | None
    ) -> Narration:
        if resolution is None:
            text = f"{ctx.character_name}: {ctx.player_action}. La scena prosegue."
        else:
            esito = {
                "success": "riesce con efficacia",
                "success_cost": "riesce, ma a un prezzo",
                "failure": "non riesce, e le cose si complicano",
            }.get(resolution.outcome.value, resolution.outcome.value)
            text = (
                f"{ctx.character_name} tenta: {ctx.player_action}. "
                f"({resolution.summary}) — {esito}."
            )
        return Narration(
            text=text,
            new_summary=None,
            changes=self._scripted_changes or StateChanges(),
        )
