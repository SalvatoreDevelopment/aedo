"""Applicazione controllata dei cambiamenti di stato proposti dal narratore.

Il narratore *propone* (vedi `StateChanges`); qui il codice *dispone*, con
regole proprie: risorse non negative, affinità limitata a [-100, 100], NPC e
relazioni creati su richiesta. È la barriera che tiene coerente lo stato.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from aedo.core.models import (
    Campaign,
    Character,
    Item,
    Memory,
    Objective,
    ObjectiveStatus,
    Relationship,
)
from aedo.core.narrator.base import StateChanges


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _get_or_create_npc(session: Session, campaign: Campaign, name: str) -> Character:
    existing = session.scalar(
        select(Character).where(
            Character.campaign_id == campaign.id, Character.name == name
        )
    )
    if existing:
        return existing
    npc = Character(campaign=campaign, name=name, is_player=False)
    session.add(npc)
    session.flush()
    return npc


def apply_changes(
    session: Session,
    campaign: Campaign,
    character: Character,
    changes: StateChanges,
) -> None:
    """Applica i cambiamenti a personaggio e campagna."""

    # --- Risorse (solo quelle già esistenti; mai sotto zero) ---
    if changes.resource_deltas:
        resources = dict(character.resources)
        for name, delta in changes.resource_deltas.items():
            if name in resources:
                resources[name] = max(0, resources[name] + delta)
        character.resources = resources  # riassegna per il dirty-tracking JSON

    # --- Condizioni ---
    if changes.conditions_add or changes.conditions_remove:
        conditions = list(character.conditions)
        for c in changes.conditions_add:
            if c not in conditions:
                conditions.append(c)
        conditions = [c for c in conditions if c not in changes.conditions_remove]
        character.conditions = conditions

    # --- Relazioni (crea NPC e legame se mancanti) ---
    for change in changes.relationship_changes:
        target_name = change.get("name")
        if not target_name:
            continue
        npc = _get_or_create_npc(session, campaign, target_name)
        rel = session.scalar(
            select(Relationship).where(
                Relationship.campaign_id == campaign.id,
                Relationship.from_id == character.id,
                Relationship.to_id == npc.id,
            )
        )
        if rel is None:
            rel = Relationship(
                campaign=campaign, from_id=character.id, to_id=npc.id,
                kind=change.get("kind") or "conoscente",
                affinity=0,
            )
            session.add(rel)
        if change.get("kind"):
            rel.kind = change["kind"]
        try:
            delta = int(change.get("affinity_delta", 0))
        except (TypeError, ValueError):
            delta = 0
        rel.affinity = _clamp((rel.affinity or 0) + delta, -100, 100)

    # --- Inventario ---
    for item in changes.new_items:
        name = item.get("name")
        if not name:
            continue
        session.add(
            Item(
                campaign=campaign,
                owner=character,
                name=name,
                description=item.get("description", ""),
                quantity=int(item.get("quantity", 1) or 1),
            )
        )
    for name in changes.removed_items:
        owned = session.scalar(
            select(Item).where(Item.owner_id == character.id, Item.name == name)
        )
        if owned:
            session.delete(owned)

    # --- Obiettivi ---
    for obj in changes.new_objectives:
        title = obj.get("title")
        if not title:
            continue
        session.add(
            Objective(campaign=campaign, title=title, description=obj.get("description", ""))
        )
    for title in changes.completed_objectives:
        target = session.scalar(
            select(Objective).where(
                Objective.campaign_id == campaign.id, Objective.title == title
            )
        )
        if target:
            target.status = ObjectiveStatus.COMPLETED

    # --- Ricordo narrativo (memoria; embedding calcolato in Fase 3) ---
    if changes.memory:
        # Coinvolti: il protagonista + gli NPC nominati nel testo del ricordo
        # (serve a dare priorità ai ricordi sui personaggi presenti in scena).
        involved = [character.id]
        text_lower = changes.memory.lower()
        npcs = session.scalars(
            select(Character).where(
                Character.campaign_id == campaign.id,
                Character.is_player.is_(False),
            )
        ).all()
        for npc in npcs:
            if npc.name.lower() in text_lower and npc.id not in involved:
                involved.append(npc.id)
        session.add(
            Memory(
                campaign=campaign,
                text=changes.memory,
                importance=changes.memory_importance,
                involved_ids=involved,
                embedded=False,
            )
        )

    session.flush()
