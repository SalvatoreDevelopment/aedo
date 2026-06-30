"""Test dell'API web (FastAPI TestClient) su un database in memoria."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from aedo.api.app import app
from aedo.api.routes import get_session
from aedo.core.models import Base, EventLog, Item, Objective, Outcome, Relationship
from aedo.core.services.campaign_service import (
    create_campaign_from_template,
    create_player_character,
)


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool, future=True,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    # Popola una campagna completa.
    with TestSession() as s:
        camp = create_campaign_from_template(
            s, template_name="noir", campaign_name="L'ombra sul molo"
        )
        sam = create_player_character(s, camp, name="Sam", attributes={"Intuito": 3})
        from aedo.core.models import Character

        lou = Character(campaign=camp, name="Lou", is_player=False)
        s.add(lou); s.flush()
        s.add(Item(campaign=camp, owner=sam, name="Revolver", quantity=1, properties={"colpi": 6}))
        s.add(Relationship(campaign=camp, from_id=sam.id, to_id=lou.id, kind="informatore", affinity=10))
        s.add(Objective(campaign=camp, title="Trova l'assassino"))
        s.add(EventLog(campaign=camp, actor="Sam", action_text="entro", outcome=Outcome.SUCCESS, narration="Entri nel locale."))
        s.commit()
        camp_id = camp.id

    def override():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = override
    yield TestClient(app), camp_id
    app.dependency_overrides.clear()


def test_list_campaigns(client):
    c, _ = client
    r = c.get("/api/campaigns")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["genre"].startswith("noir")


def test_campaign_detail(client):
    c, cid = client
    r = c.get(f"/api/campaigns/{cid}")
    assert r.status_code == 200
    d = r.json()
    assert d["name"] == "L'ombra sul molo"
    assert d["player"]["name"] == "Sam"
    assert d["player"]["attributes"]["Intuito"] == 3
    assert any(a["name"] == "Intuito" for a in d["attributes"])


def test_inventory(client):
    c, cid = client
    r = c.get(f"/api/campaigns/{cid}/inventory")
    assert r.status_code == 200
    assert r.json()[0]["name"] == "Revolver"


def test_relationships(client):
    c, cid = client
    r = c.get(f"/api/campaigns/{cid}/relationships")
    assert r.status_code == 200
    rel = r.json()[0]
    assert rel["from_name"] == "Sam" and rel["to_name"] == "Lou"
    assert rel["affinity"] == 10


def test_objectives_and_events(client):
    c, cid = client
    assert c.get(f"/api/campaigns/{cid}/objectives").json()[0]["title"] == "Trova l'assassino"
    events = c.get(f"/api/campaigns/{cid}/events").json()
    assert events[0]["narration"] == "Entri nel locale."
    assert events[0]["outcome"] == "success"


def test_unknown_campaign_404(client):
    c, _ = client
    assert c.get("/api/campaigns/9999").status_code == 404
