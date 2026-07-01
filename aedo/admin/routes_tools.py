"""Endpoint degli Strumenti e delle Statistiche del master."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from aedo.core.services import tools
from . import schemas, state_ops
from .routes_state import read_session
from .state_ops import NotFound

router = APIRouter(prefix="/admin/api", tags=["tools"])


@router.post("/tools/oracle", response_model=schemas.OracleOut)
def oracle(body: schemas.OracleReq):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Fai una domanda all'oracolo.")
    ans = tools.ask_oracle(body.question, body.likelihood)
    return schemas.OracleOut(
        question=ans.question, likelihood=ans.likelihood,
        answer=ans.answer, grade=ans.grade,
    )


@router.post("/campaigns/{campaign_id}/tools/generate", response_model=schemas.GenerateOut)
def generate(campaign_id: int, body: schemas.GenerateReq,
             session: Session = Depends(read_session)):
    try:
        camp = state_ops.get_campaign(session, campaign_id)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    genre = camp.blueprint.genre

    if body.kind == "names":
        return schemas.GenerateOut(kind="names", genre=genre, items=tools.generate_names(genre, 6))
    if body.kind == "hook":
        items = [tools.generate_hook(genre) for _ in range(3)]
        return schemas.GenerateOut(kind="hook", genre=genre, items=items)
    if body.kind == "npc":
        npc = tools.generate_npc(genre)
        label = f"{npc['name']} — {npc['role']} ({npc['trait']})"
        return schemas.GenerateOut(
            kind="npc", genre=genre, items=[label],
            npc=schemas.NpcSuggestion(**npc),
        )
    raise HTTPException(status_code=400, detail=f"Tipo di generatore sconosciuto: {body.kind!r}.")


@router.get("/campaigns/{campaign_id}/stats", response_model=schemas.StatsOut)
def stats(campaign_id: int, session: Session = Depends(read_session)):
    try:
        state_ops.get_campaign(session, campaign_id)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    s = tools.campaign_stats(session, campaign_id)
    return schemas.StatsOut(
        turns=s.turns, events_total=s.events_total, outcomes=s.outcomes,
        npc_count=s.npc_count, memory_count=s.memory_count,
        objectives=s.objectives,
        relationships=[schemas.RelStat(**r) for r in s.relationships],
    )
