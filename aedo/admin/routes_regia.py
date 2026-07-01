"""Endpoint di Regia narrativa — il master mette in scena.

Questi endpoint **accodano** ordini (li esegue poi il bot Discord) e gestiscono
le note segrete. Il Banco non parla con Discord: scrive nella coda e mostra lo
stato di ciò che il bot ha eseguito.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from aedo.core.models import CommandKind, Outcome
from aedo.core.services import regia
from . import schemas, state_ops
from .routes_state import read_session, write_session
from .state_ops import NotFound

router = APIRouter(prefix="/admin/api", tags=["regia"])

_VALID_OUTCOMES = {o.value for o in Outcome}


def _command_out(cmd) -> schemas.CommandOut:
    return schemas.CommandOut(
        id=cmd.id, kind=cmd.kind.value, status=cmd.status.value,
        payload=cmd.payload, result_narration=cmd.result_narration,
        error=cmd.error, created_at=cmd.created_at, processed_at=cmd.processed_at,
    )


def _regia_state(session: Session, campaign_id: int) -> schemas.RegiaState:
    camp = state_ops.get_campaign(session, campaign_id)
    last = regia.last_resolved_event(session, campaign_id)
    return schemas.RegiaState(
        campaign_id=campaign_id,
        has_channel=bool(camp.discord_channel_id),
        last_event=(
            schemas.LastEventOut(
                id=last.id, action_text=last.action_text,
                outcome=last.outcome.value if last.outcome else None,
            ) if last else None
        ),
        commands=[_command_out(c) for c in regia.recent_commands(session, campaign_id)],
        notes=[
            schemas.NoteOut(id=n.id, text=n.text, created_at=n.created_at)
            for n in regia.list_notes(session, campaign_id)
        ],
    )


@router.get("/campaigns/{campaign_id}/regia", response_model=schemas.RegiaState)
def get_regia(campaign_id: int, session: Session = Depends(read_session)):
    try:
        return _regia_state(session, campaign_id)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/campaigns/{campaign_id}/regia/event", response_model=schemas.RegiaState)
def inject_event(campaign_id: int, body: schemas.RegiaEventReq,
                 session: Session = Depends(write_session)):
    camp = _require_campaign_with_channel(session, campaign_id)
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Il testo dell'evento è vuoto.")
    kind = CommandKind.INJECT_EVENT if body.mode == "direct" else CommandKind.NARRATE_EVENT
    regia.enqueue(session, camp.id, kind, text)
    return _regia_state(session, campaign_id)


@router.post("/campaigns/{campaign_id}/regia/override", response_model=schemas.RegiaState)
def override_last(campaign_id: int, body: schemas.RegiaOverrideReq,
                  session: Session = Depends(write_session)):
    camp = _require_campaign_with_channel(session, campaign_id)
    if body.outcome not in _VALID_OUTCOMES:
        raise HTTPException(status_code=400, detail=f"Esito non valido: {body.outcome!r}.")
    if regia.last_resolved_event(session, camp.id) is None:
        raise HTTPException(status_code=400, detail="Non c'è nessuna prova recente da correggere.")
    regia.enqueue(session, camp.id, CommandKind.OVERRIDE_LAST, body.outcome)
    return _regia_state(session, campaign_id)


@router.post("/campaigns/{campaign_id}/notes", response_model=schemas.RegiaState)
def add_note(campaign_id: int, body: schemas.NoteReq,
             session: Session = Depends(write_session)):
    _require_campaign(session, campaign_id)
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="La nota è vuota.")
    regia.add_note(session, campaign_id, text)
    return _regia_state(session, campaign_id)


@router.delete("/campaigns/{campaign_id}/notes/{note_id}", response_model=schemas.RegiaState)
def delete_note(campaign_id: int, note_id: int,
                session: Session = Depends(write_session)):
    _require_campaign(session, campaign_id)
    if not regia.delete_note(session, campaign_id, note_id):
        raise HTTPException(status_code=404, detail="Nota inesistente.")
    return _regia_state(session, campaign_id)


# --- helper ---------------------------------------------------------------
def _require_campaign(session: Session, campaign_id: int):
    try:
        return state_ops.get_campaign(session, campaign_id)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _require_campaign_with_channel(session: Session, campaign_id: int):
    camp = _require_campaign(session, campaign_id)
    if not camp.discord_channel_id:
        raise HTTPException(
            status_code=400,
            detail="Questa campagna non ha un canale Discord: la regia non ha dove postare.",
        )
    return camp
