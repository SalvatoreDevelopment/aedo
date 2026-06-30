"""Modelli di risposta dell'API (Pydantic). Sola lettura: la dashboard mostra,
non modifica — il gioco si svolge su Discord."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CampaignSummary(BaseModel):
    id: int
    name: str
    genre: str
    mode: str
    status: str


class AttributeDef(BaseModel):
    name: str
    description: str = ""


class CharacterOut(BaseModel):
    id: int
    name: str
    is_player: bool
    description: str
    attributes: dict[str, int]
    resources: dict[str, int]
    conditions: list[str]


class ItemOut(BaseModel):
    id: int
    name: str
    description: str
    quantity: int
    properties: dict


class RelationshipOut(BaseModel):
    id: int
    from_name: str
    to_name: str
    kind: str
    affinity: int
    notes: str


class ObjectiveOut(BaseModel):
    id: int
    title: str
    description: str
    status: str


class EventOut(BaseModel):
    id: int
    actor: str
    action_text: str
    outcome: str | None
    narration: str
    created_at: datetime


class CampaignDetail(BaseModel):
    id: int
    name: str
    genre: str
    tone: str
    mode: str
    status: str
    crunch_level: str
    summary: str
    attributes: list[AttributeDef]
    player: CharacterOut | None
