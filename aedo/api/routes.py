"""Endpoint REST di sola lettura sullo stato delle campagne."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from aedo.core.models import Campaign, Character, EventLog, Item, Objective, Relationship
from aedo.storage import SessionLocal
from . import schemas

router = APIRouter(prefix="/api")


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _character_out(ch: Character) -> schemas.CharacterOut:
    return schemas.CharacterOut(
        id=ch.id, name=ch.name, is_player=ch.is_player,
        description=ch.description, attributes=ch.attributes,
        resources=ch.resources, conditions=ch.conditions,
    )


def _get_campaign(session: Session, campaign_id: int) -> Campaign:
    campaign = session.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campagna non trovata")
    return campaign


def _player(session: Session, campaign_id: int) -> Character | None:
    return session.scalar(
        select(Character).where(
            Character.campaign_id == campaign_id, Character.is_player.is_(True)
        )
    )


@router.get("/campaigns", response_model=list[schemas.CampaignSummary])
def list_campaigns(session: Session = Depends(get_session)):
    campaigns = session.scalars(select(Campaign).order_by(Campaign.id.desc())).all()
    return [
        schemas.CampaignSummary(
            id=c.id, name=c.name, genre=c.blueprint.genre,
            mode=c.mode.value, status=c.status.value,
        )
        for c in campaigns
    ]


@router.get("/campaigns/{campaign_id}", response_model=schemas.CampaignDetail)
def get_campaign(campaign_id: int, session: Session = Depends(get_session)):
    c = _get_campaign(session, campaign_id)
    pc = _player(session, campaign_id)
    bp = c.blueprint
    return schemas.CampaignDetail(
        id=c.id, name=c.name, genre=bp.genre, tone=bp.tone,
        mode=c.mode.value, status=c.status.value,
        crunch_level=bp.crunch_level.value, summary=c.current_summary,
        attributes=[schemas.AttributeDef(**a) for a in bp.attributes],
        player=_character_out(pc) if pc else None,
    )


@router.get("/campaigns/{campaign_id}/characters", response_model=list[schemas.CharacterOut])
def get_characters(campaign_id: int, session: Session = Depends(get_session)):
    c = _get_campaign(session, campaign_id)
    return [_character_out(ch) for ch in c.characters]


@router.get("/campaigns/{campaign_id}/inventory", response_model=list[schemas.ItemOut])
def get_inventory(campaign_id: int, session: Session = Depends(get_session)):
    pc = _player(session, campaign_id)
    if pc is None:
        return []
    return [
        schemas.ItemOut(
            id=it.id, name=it.name, description=it.description,
            quantity=it.quantity, properties=it.properties,
        )
        for it in pc.items
    ]


@router.get("/campaigns/{campaign_id}/relationships", response_model=list[schemas.RelationshipOut])
def get_relationships(campaign_id: int, session: Session = Depends(get_session)):
    c = _get_campaign(session, campaign_id)
    out = []
    for rel in c.relationships:
        out.append(
            schemas.RelationshipOut(
                id=rel.id, from_name=rel.from_character.name,
                to_name=rel.to_character.name, kind=rel.kind,
                affinity=rel.affinity, notes=rel.notes,
            )
        )
    return out


@router.get("/campaigns/{campaign_id}/objectives", response_model=list[schemas.ObjectiveOut])
def get_objectives(campaign_id: int, session: Session = Depends(get_session)):
    c = _get_campaign(session, campaign_id)
    return [
        schemas.ObjectiveOut(
            id=o.id, title=o.title, description=o.description, status=o.status.value
        )
        for o in c.objectives
    ]


@router.get("/campaigns/{campaign_id}/events", response_model=list[schemas.EventOut])
def get_events(campaign_id: int, limit: int = 50, session: Session = Depends(get_session)):
    _get_campaign(session, campaign_id)
    rows = session.scalars(
        select(EventLog)
        .where(EventLog.campaign_id == campaign_id)
        .order_by(EventLog.id.desc())
        .limit(limit)
    ).all()
    return [
        schemas.EventOut(
            id=e.id, actor=e.actor, action_text=e.action_text,
            outcome=e.outcome.value if e.outcome else None,
            narration=e.narration, created_at=e.created_at,
        )
        for e in reversed(rows)  # dal più vecchio al più recente
    ]
