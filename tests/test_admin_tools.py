"""Test degli endpoint Strumenti/Statistiche del Banco."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from aedo.admin.app import app
from aedo.admin.routes_state import read_session
from aedo.core.models import Base
from aedo.core.services.campaign_service import create_campaign_from_template


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool, future=True,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestSession() as s:
        camp = create_campaign_from_template(s, template_name="fantasy", campaign_name="Eldar")
        s.commit()
        cid = camp.id

    def override_read():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[read_session] = override_read
    yield TestClient(app), cid
    app.dependency_overrides.clear()


def test_oracle_endpoint(client):
    c, _ = client
    r = c.post("/admin/api/tools/oracle", json={"question": "Piove?", "likelihood": "likely"})
    assert r.status_code == 200
    assert r.json()["answer"] in {"Sì", "Sì, ma…", "No, ma…", "No"}
    assert r.json()["grade"] in {"yes", "yes_but", "no_but", "no"}


def test_oracle_empty_question_is_400(client):
    c, _ = client
    assert c.post("/admin/api/tools/oracle", json={"question": "  "}).status_code == 400


def test_generators(client):
    c, cid = client
    for kind in ("names", "npc", "hook"):
        r = c.post(f"/admin/api/campaigns/{cid}/tools/generate", json={"kind": kind})
        assert r.status_code == 200
        assert r.json()["items"]
    npc = c.post(f"/admin/api/campaigns/{cid}/tools/generate", json={"kind": "npc"}).json()
    assert npc["npc"]["name"]
    bad = c.post(f"/admin/api/campaigns/{cid}/tools/generate", json={"kind": "boh"})
    assert bad.status_code == 400


def test_stats_endpoint(client):
    c, cid = client
    r = c.get(f"/admin/api/campaigns/{cid}/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["turns"] == 0 and "success" in body["outcomes"]
