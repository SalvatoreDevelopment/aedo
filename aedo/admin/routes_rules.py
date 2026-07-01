"""Endpoint dell'Editor regole e generi (il Blueprint della campagna)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from aedo.config import settings
from aedo.core.models import Blueprint, CrunchLevel
from . import blueprint_ops, schemas
from .routes_state import read_session, write_session
from .state_ops import Invalid, NotFound

router = APIRouter(prefix="/admin/api", tags=["rules"])

_CRUNCH_OPTIONS = [c.value for c in CrunchLevel]


def _blueprint_out(bp: Blueprint) -> schemas.BlueprintOut:
    return schemas.BlueprintOut(
        name=bp.name, genre=bp.genre, tone=bp.tone,
        narrator_persona=bp.narrator_persona,
        crunch_level=bp.crunch_level.value, crunch_options=_CRUNCH_OPTIONS,
        attributes=[schemas.AttributeDef(**a) for a in bp.attributes],
        conflict_types=list(bp.conflict_types),
        default_resources={k: int(v) for k, v in bp.default_resources.items()},
        special_rules=bp.special_rules,
        dice_formula=bp.dice_formula, success_band=bp.success_band,
        ai_model=settings.aedo_model,
    )


@router.get("/campaigns/{campaign_id}/blueprint", response_model=schemas.BlueprintOut)
def get_blueprint(campaign_id: int, session: Session = Depends(read_session)):
    try:
        _camp, bp = blueprint_ops.get_blueprint(session, campaign_id)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _blueprint_out(bp)


@router.patch("/campaigns/{campaign_id}/blueprint", response_model=schemas.BlueprintOut)
def update_blueprint(campaign_id: int, body: schemas.BlueprintUpdate,
                     session: Session = Depends(write_session)):
    patch = body.model_dump(exclude_unset=True)
    try:
        _camp, bp = blueprint_ops.get_blueprint(session, campaign_id)
        blueprint_ops.update_blueprint(session, bp, patch)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Invalid as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _blueprint_out(bp)
