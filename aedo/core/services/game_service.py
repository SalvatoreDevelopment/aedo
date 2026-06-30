"""Il game loop: un turno di gioco, dall'azione del giocatore al salvataggio.

Mette insieme i pezzi delle fasi precedenti:
  azione → (narratore) valuta se è rischiosa → (motore) tira → (narratore) narra
  → (codice) applica i cambiamenti, salva l'evento e l'eventuale ricordo.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from aedo.core.models import Campaign, Character, EventLog
from aedo.core.memory import MemoryService
from aedo.core.narrator.base import Assessment, Narration, NarratorContext, NarratorProvider
from aedo.core.resolution import Difficulty, ResolutionResult, resolve
from .state_apply import apply_changes

# Mappa i nomi di difficoltà scelti dal narratore ai valori del motore.
_DIFFICULTY_BY_NAME = {d.name.lower(): d for d in Difficulty}


@dataclass
class TurnResult:
    """Esito completo di un turno, pronto per l'interfaccia (bot/web)."""

    narration: str
    assessment: Assessment
    resolution: ResolutionResult | None
    event_id: int


def _present_character_ids(session: Session, campaign: Campaign, action: str) -> list[int]:
    """NPC nominati nell'azione o nella scena corrente (per pesare i ricordi)."""
    text = f"{action} {campaign.current_summary}".lower()
    return [
        ch.id
        for ch in campaign.characters
        if not ch.is_player and ch.name and ch.name.lower() in text
    ]


def _recent_event_lines(session: Session, campaign: Campaign, limit: int = 5) -> list[str]:
    rows = session.scalars(
        select(EventLog)
        .where(EventLog.campaign_id == campaign.id)
        .order_by(EventLog.id.desc())
        .limit(limit)
    ).all()
    # Dal più vecchio al più recente, solo le narrazioni non vuote.
    return [r.narration for r in reversed(rows) if r.narration]


def build_context(
    session: Session,
    campaign: Campaign,
    character: Character,
    action: str,
    *,
    relevant_memories: list[str] | None = None,
) -> NarratorContext:
    """Assembla il contesto del narratore dallo stato corrente."""
    bp = campaign.blueprint
    return NarratorContext(
        genre=bp.genre,
        tone=bp.tone,
        narrator_persona=bp.narrator_persona,
        special_rules=bp.special_rules,
        crunch_level=bp.crunch_level.value,
        attribute_names=[a["name"] for a in bp.attributes],
        difficulty_options=list(_DIFFICULTY_BY_NAME),
        character_name=character.name,
        character_description=character.description,
        character_attributes=dict(character.attributes),
        character_resources=dict(character.resources),
        character_conditions=list(character.conditions),
        current_summary=campaign.current_summary,
        recent_events=_recent_event_lines(session, campaign),
        relevant_memories=relevant_memories or [],
        player_action=action,
    )


def start_campaign(
    session: Session,
    campaign: Campaign,
    character: Character,
    narrator: NarratorProvider,
    *,
    premise: str = "",
    memory: MemoryService | None = None,
) -> str:
    """Genera e salva la scena di apertura. Restituisce l'incipit narrato."""
    ctx = build_context(session, campaign, character, action="")
    narration = narrator.open_scene(ctx, premise)
    apply_changes(session, campaign, character, narration.changes)
    campaign.current_summary = narration.new_summary or narration.text
    event = EventLog(
        campaign=campaign,
        actor="Aedo",
        action_text="(apertura)",
        narration=narration.text,
    )
    session.add(event)
    session.flush()
    if memory is not None:
        memory.index_pending(session, campaign.id)
    return narration.text


def play_turn(
    session: Session,
    campaign: Campaign,
    character: Character,
    action: str,
    narrator: NarratorProvider,
    *,
    rng: random.Random | None = None,
    memory: MemoryService | None = None,
) -> TurnResult:
    """Esegue un turno completo e lo persiste."""
    if memory:
        present = _present_character_ids(session, campaign, action)
        relevant = memory.recall(session, campaign.id, action, present_ids=present)
    else:
        relevant = []
    ctx = build_context(
        session, campaign, character, action, relevant_memories=relevant
    )

    # 1. Il narratore valuta l'azione e, se libera, la narra già qui (1 chiamata).
    assessment, narration = narrator.turn(ctx)

    # 2. Se rischiosa, il motore risolve e il narratore racconta l'esito del tiro.
    resolution: ResolutionResult | None = None
    if assessment.is_risky and assessment.attribute:
        difficulty = _DIFFICULTY_BY_NAME.get(
            (assessment.difficulty or "medium").lower(), Difficulty.MEDIUM
        )
        resolution = resolve(
            attribute_name=assessment.attribute,
            attribute_value=character.attributes.get(assessment.attribute, 0),
            difficulty=difficulty,
            dice_formula=campaign.blueprint.dice_formula,
            band=campaign.blueprint.success_band,
            rng=rng,
        )
        narration = narrator.narrate(ctx, resolution)

    # 3. Salvaguardia: se l'azione era marcata rischiosa ma senza attributo valido,
    #    non c'è ancora narrazione → narra come azione libera.
    if narration is None:
        narration = narrator.narrate(ctx, resolution)

    # 4. Il codice applica i cambiamenti in modo controllato.
    apply_changes(session, campaign, character, narration.changes)
    if narration.new_summary:
        campaign.current_summary = narration.new_summary

    # 5. Registra il turno nel diario.
    event = EventLog(
        campaign=campaign,
        actor=character.name,
        action_text=action,
        outcome=resolution.outcome if resolution else None,
        roll=resolution.to_dict() if resolution else {},
        narration=narration.text,
    )
    session.add(event)
    session.flush()

    # Indicizza i ricordi appena creati (embedding) per i recuperi futuri.
    if memory is not None:
        memory.index_pending(session, campaign.id)

    return TurnResult(
        narration=narration.text,
        assessment=assessment,
        resolution=resolution,
        event_id=event.id,
    )
