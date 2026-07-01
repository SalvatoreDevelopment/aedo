"""Endpoint di Controllo dello Stato — i poteri di scrittura del master.

Le operazioni vere stanno in :mod:`aedo.admin.state_ops` (testabili senza rete);
qui c'è il guscio HTTP: sessione transazionale, traduzione degli errori di
dominio in codici HTTP, serializzazione. Ogni scrittura restituisce lo **stato
completo** aggiornato della campagna, così la UI ridisegna con una risposta sola.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from aedo.core.models import Campaign, Character, Item, Objective, Relationship
from aedo.storage import SessionLocal
from . import schemas, state_ops
from .state_ops import Invalid, NotFound

router = APIRouter(prefix="/admin/api", tags=["state"])


# --- sessioni -------------------------------------------------------------
def read_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def write_session() -> Iterator[Session]:
    """Sessione transazionale: commit se l'endpoint riesce, rollback altrimenti."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def _translate():
    """Converte gli errori di dominio in risposte HTTP pulite."""
    try:
        yield
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Invalid as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --- serializzatori -------------------------------------------------------
def _character_admin(ch: Character) -> schemas.CharacterAdmin:
    return schemas.CharacterAdmin(
        id=ch.id, name=ch.name, is_player=ch.is_player, description=ch.description,
        attributes=ch.attributes, resources=ch.resources, conditions=ch.conditions,
    )


def _item_admin(it: Item) -> schemas.ItemAdmin:
    return schemas.ItemAdmin(
        id=it.id, owner_id=it.owner_id, name=it.name,
        description=it.description, quantity=it.quantity,
    )


def _rel_admin(rel: Relationship) -> schemas.RelationshipAdmin:
    return schemas.RelationshipAdmin(
        id=rel.id, from_id=rel.from_id, to_id=rel.to_id,
        from_name=rel.from_character.name, to_name=rel.to_character.name,
        kind=rel.kind, affinity=rel.affinity, notes=rel.notes,
    )


def _obj_admin(o: Objective) -> schemas.ObjectiveAdmin:
    return schemas.ObjectiveAdmin(
        id=o.id, title=o.title, description=o.description, status=o.status.value,
    )


def _campaign_state(session: Session, camp: Campaign) -> schemas.CampaignStateAdmin:
    bp = camp.blueprint
    characters = session.scalars(
        select(Character).where(Character.campaign_id == camp.id).order_by(
            Character.is_player.desc(), Character.id
        )
    ).all()
    items = session.scalars(
        select(Item).where(Item.campaign_id == camp.id).order_by(Item.id)
    ).all()
    rels = session.scalars(
        select(Relationship).where(Relationship.campaign_id == camp.id).order_by(Relationship.id)
    ).all()
    objs = session.scalars(
        select(Objective).where(Objective.campaign_id == camp.id).order_by(Objective.id)
    ).all()
    return schemas.CampaignStateAdmin(
        id=camp.id, name=camp.name, genre=bp.genre, tone=bp.tone,
        status=camp.status.value, crunch_level=bp.crunch_level.value,
        summary=camp.current_summary,
        attributes=[schemas.AttributeDef(**a) for a in bp.attributes],
        characters=[_character_admin(c) for c in characters],
        items=[_item_admin(i) for i in items],
        relationships=[_rel_admin(r) for r in rels],
        objectives=[_obj_admin(o) for o in objs],
    )


# =========================================================================
# Lettura
# =========================================================================
@router.get("/campaigns", response_model=list[schemas.CampaignRef])
def list_campaigns(session: Session = Depends(read_session)):
    camps = session.scalars(select(Campaign).order_by(Campaign.id.desc())).all()
    return [
        schemas.CampaignRef(
            id=c.id, name=c.name, genre=c.blueprint.genre, status=c.status.value
        )
        for c in camps
    ]


@router.get("/campaigns/{campaign_id}/state", response_model=schemas.CampaignStateAdmin)
def campaign_state(campaign_id: int, session: Session = Depends(read_session)):
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        return _campaign_state(session, camp)


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: int, session: Session = Depends(write_session)):
    """Elimina una campagna e tutto il suo contenuto. Se aveva un canale
    Discord, ne accoda la cancellazione (la esegue il bot, se acceso)."""
    with _translate():
        channel_id = state_ops.delete_campaign(session, campaign_id)
        return {"deleted": True, "campaign_id": campaign_id, "channel_queued": bool(channel_id)}


# =========================================================================
# Risorse e condizioni
# =========================================================================
@router.post("/campaigns/{campaign_id}/characters/{character_id}/resources/set")
def set_resource(campaign_id: int, character_id: int, body: schemas.ResourceSet,
                 session: Session = Depends(write_session)):
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        ch = state_ops.get_character(session, campaign_id, character_id)
        state_ops.set_resource(session, ch, body.name, body.value)
        return _campaign_state(session, camp)


@router.post("/campaigns/{campaign_id}/characters/{character_id}/resources/adjust")
def adjust_resource(campaign_id: int, character_id: int, body: schemas.ResourceAdjust,
                    session: Session = Depends(write_session)):
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        ch = state_ops.get_character(session, campaign_id, character_id)
        state_ops.adjust_resource(session, ch, body.name, body.delta)
        return _campaign_state(session, camp)


@router.post("/campaigns/{campaign_id}/characters/{character_id}/resources/remove")
def remove_resource(campaign_id: int, character_id: int, body: schemas.ConditionReq,
                    session: Session = Depends(write_session)):
    # riusa ConditionReq: un singolo campo "condition" col nome della risorsa
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        ch = state_ops.get_character(session, campaign_id, character_id)
        state_ops.remove_resource(session, ch, body.condition)
        return _campaign_state(session, camp)


@router.post("/campaigns/{campaign_id}/characters/{character_id}/conditions/add")
def add_condition(campaign_id: int, character_id: int, body: schemas.ConditionReq,
                  session: Session = Depends(write_session)):
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        ch = state_ops.get_character(session, campaign_id, character_id)
        state_ops.add_condition(session, ch, body.condition)
        return _campaign_state(session, camp)


@router.post("/campaigns/{campaign_id}/characters/{character_id}/conditions/remove")
def remove_condition(campaign_id: int, character_id: int, body: schemas.ConditionReq,
                     session: Session = Depends(write_session)):
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        ch = state_ops.get_character(session, campaign_id, character_id)
        state_ops.remove_condition(session, ch, body.condition)
        return _campaign_state(session, camp)


# =========================================================================
# Inventario
# =========================================================================
@router.post("/campaigns/{campaign_id}/items")
def grant_item(campaign_id: int, body: schemas.ItemGrant,
               session: Session = Depends(write_session)):
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        owner = state_ops.get_character(session, campaign_id, body.owner_id)
        state_ops.grant_item(
            session, camp, owner, name=body.name,
            quantity=body.quantity, description=body.description,
        )
        return _campaign_state(session, camp)


@router.patch("/campaigns/{campaign_id}/items/{item_id}")
def set_item_quantity(campaign_id: int, item_id: int, body: schemas.ItemQuantity,
                      session: Session = Depends(write_session)):
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        state_ops.set_item_quantity(session, campaign_id, item_id, body.quantity)
        return _campaign_state(session, camp)


@router.delete("/campaigns/{campaign_id}/items/{item_id}")
def remove_item(campaign_id: int, item_id: int,
                session: Session = Depends(write_session)):
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        state_ops.remove_item(session, campaign_id, item_id)
        return _campaign_state(session, camp)


# =========================================================================
# Relazioni
# =========================================================================
@router.post("/campaigns/{campaign_id}/relationships")
def create_relationship(campaign_id: int, body: schemas.RelationshipCreate,
                        session: Session = Depends(write_session)):
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        state_ops.create_relationship(
            session, camp, from_id=body.from_id, to_id=body.to_id,
            kind=body.kind, affinity=body.affinity,
        )
        return _campaign_state(session, camp)


@router.patch("/campaigns/{campaign_id}/relationships/{rel_id}")
def update_relationship(campaign_id: int, rel_id: int, body: schemas.RelationshipUpdate,
                        session: Session = Depends(write_session)):
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        state_ops.update_relationship(
            session, campaign_id, rel_id, kind=body.kind, affinity=body.affinity,
            affinity_delta=body.affinity_delta, notes=body.notes,
        )
        return _campaign_state(session, camp)


@router.delete("/campaigns/{campaign_id}/relationships/{rel_id}")
def delete_relationship(campaign_id: int, rel_id: int,
                        session: Session = Depends(write_session)):
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        state_ops.delete_relationship(session, campaign_id, rel_id)
        return _campaign_state(session, camp)


# =========================================================================
# Obiettivi / quest
# =========================================================================
@router.post("/campaigns/{campaign_id}/objectives")
def create_objective(campaign_id: int, body: schemas.ObjectiveCreate,
                     session: Session = Depends(write_session)):
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        state_ops.create_objective(session, camp, title=body.title, description=body.description)
        return _campaign_state(session, camp)


@router.post("/campaigns/{campaign_id}/objectives/{obj_id}/status")
def set_objective_status(campaign_id: int, obj_id: int, body: schemas.ObjectiveStatusReq,
                         session: Session = Depends(write_session)):
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        state_ops.set_objective_status(session, campaign_id, obj_id, body.status)
        return _campaign_state(session, camp)


@router.patch("/campaigns/{campaign_id}/objectives/{obj_id}")
def update_objective(campaign_id: int, obj_id: int, body: schemas.ObjectiveUpdate,
                     session: Session = Depends(write_session)):
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        state_ops.update_objective(
            session, campaign_id, obj_id, title=body.title, description=body.description
        )
        return _campaign_state(session, camp)


@router.delete("/campaigns/{campaign_id}/objectives/{obj_id}")
def delete_objective(campaign_id: int, obj_id: int,
                     session: Session = Depends(write_session)):
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        state_ops.delete_objective(session, campaign_id, obj_id)
        return _campaign_state(session, camp)


# =========================================================================
# NPC / personaggi
# =========================================================================
@router.post("/campaigns/{campaign_id}/npcs")
def create_npc(campaign_id: int, body: schemas.NpcCreate,
               session: Session = Depends(write_session)):
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        state_ops.create_npc(
            session, camp, name=body.name, description=body.description,
            attributes=body.attributes, resources=body.resources,
        )
        return _campaign_state(session, camp)


@router.patch("/campaigns/{campaign_id}/characters/{character_id}")
def update_character(campaign_id: int, character_id: int, body: schemas.CharacterUpdate,
                     session: Session = Depends(write_session)):
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        state_ops.update_character(
            session, campaign_id, character_id,
            name=body.name, description=body.description, attributes=body.attributes,
        )
        return _campaign_state(session, camp)


@router.delete("/campaigns/{campaign_id}/characters/{character_id}")
def delete_character(campaign_id: int, character_id: int,
                     session: Session = Depends(write_session)):
    with _translate():
        camp = state_ops.get_campaign(session, campaign_id)
        state_ops.delete_character(session, campaign_id, character_id)
        return _campaign_state(session, camp)
