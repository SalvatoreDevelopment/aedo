"""Verifica della spina dorsale dati: schema, entità e relazioni.

Usa un database SQLite in memoria, indipendente dalla configurazione reale.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aedo.core.models import (
    Base,
    Blueprint,
    Campaign,
    CampaignMode,
    Character,
    CrunchLevel,
    EventLog,
    Item,
    Memory,
    Objective,
    ObjectiveStatus,
    Outcome,
    Relationship,
)


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as s:
        yield s


def _make_noir_blueprint() -> Blueprint:
    """Un Blueprint di genere completamente diverso da D&D, per provare
    che il modello è davvero genre-agnostic."""
    return Blueprint(
        name="Noir investigativo",
        genre="noir anni '40",
        tone="cupo, adulto, ironico",
        crunch_level=CrunchLevel.NARRATIVE,
        attributes=[
            {"name": "Intuito", "description": "leggere persone e indizi"},
            {"name": "Sangue freddo", "description": "restare lucidi sotto pressione"},
        ],
        conflict_types=["interrogatorio", "inseguimento", "deduzione"],
        default_resources={"salute": 5, "nervi": 3},
    )


def test_blueprint_is_genre_agnostic(session: Session) -> None:
    bp = _make_noir_blueprint()
    session.add(bp)
    session.commit()

    loaded = session.get(Blueprint, bp.id)
    assert loaded is not None
    # Gli attributi sono DATI, non colonne fisse: nessun "Forza/Destrezza".
    names = [a["name"] for a in loaded.attributes]
    assert names == ["Intuito", "Sangue freddo"]
    assert loaded.default_resources["nervi"] == 3


def test_full_campaign_graph(session: Session) -> None:
    bp = _make_noir_blueprint()
    campaign = Campaign(name="L'ombra sul molo", mode=CampaignMode.SINGLE, blueprint=bp)
    session.add(campaign)
    session.flush()

    detective = Character(
        campaign=campaign,
        name="Sam",
        is_player=True,
        discord_id="123",
        attributes={"Intuito": 3, "Sangue freddo": 2},
        resources={"salute": 5, "nervi": 3},
    )
    informatore = Character(
        campaign=campaign, name="Lou il Topo", is_player=False
    )
    session.add_all([detective, informatore])
    session.flush()

    revolver = Item(
        campaign=campaign, owner=detective, name="Revolver", properties={"colpi": 6}
    )
    legame = Relationship(
        campaign=campaign,
        from_id=detective.id,
        to_id=informatore.id,
        kind="informatore",
        affinity=10,
    )
    quest = Objective(
        campaign=campaign,
        title="Scopri chi ha ucciso la cantante",
        status=ObjectiveStatus.OPEN,
    )
    ricordo = Memory(
        campaign=campaign,
        text="Lou ha accennato a un nome prima di sparire nella nebbia.",
        involved_ids=[detective.id, informatore.id],
        importance=0.8,
    )
    turno = EventLog(
        campaign=campaign,
        actor="Sam",
        action_text="Interrogo Lou con tono minaccioso",
        outcome=Outcome.SUCCESS_WITH_COST,
        roll={"attributo": "Intuito", "dado": 14, "difficolta": 12},
        narration="Lou parla, ma ora sa che fai sul serio.",
    )
    session.add_all([revolver, legame, quest, ricordo, turno])
    session.commit()

    # Ricarico la campagna e verifico che il grafo sia integro.
    fresh = session.get(Campaign, campaign.id)
    assert fresh is not None
    assert fresh.blueprint.genre == "noir anni '40"
    assert len(fresh.characters) == 2
    assert fresh.items[0].owner.name == "Sam"
    assert fresh.items[0].properties["colpi"] == 6
    assert fresh.relationships[0].affinity == 10
    assert fresh.objectives[0].status is ObjectiveStatus.OPEN
    assert fresh.memories[0].importance == 0.8
    assert fresh.events[0].outcome is Outcome.SUCCESS_WITH_COST


def test_cascade_delete(session: Session) -> None:
    """Cancellando la campagna spariscono tutte le entità figlie."""
    bp = _make_noir_blueprint()
    campaign = Campaign(name="Temp", blueprint=bp)
    session.add(campaign)
    session.flush()
    session.add(Character(campaign=campaign, name="X"))
    session.commit()

    session.delete(campaign)
    session.commit()

    assert session.query(Character).count() == 0
    # Il Blueprint NON è figlio: sopravvive (può essere un template riusabile).
    assert session.query(Blueprint).count() == 1
