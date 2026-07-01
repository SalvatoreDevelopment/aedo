"""Test degli endpoint di Regia del Banco (accodamento, note, override)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from aedo.admin.app import app
from aedo.admin.routes_state import read_session, write_session
from aedo.core.models import Base, EventLog, Outcome
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
    with TestSession() as s:
        withch = create_campaign_from_template(s, template_name="noir", campaign_name="Con canale")
        withch.discord_channel_id = "777"
        create_player_character(s, withch, name="Sam")
        s.add(EventLog(
            campaign=withch, actor="Sam", action_text="forzo la serratura",
            outcome=Outcome.FAILURE, narration="Niente da fare.",
        ))
        nochan = create_campaign_from_template(s, template_name="noir", campaign_name="Senza canale")
        create_player_character(s, nochan, name="Lou")
        s.commit()
        ids = {"withch": withch.id, "nochan": nochan.id}

    def override_read():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    def override_write():
        s = TestSession()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback(); raise
        finally:
            s.close()

    app.dependency_overrides[read_session] = override_read
    app.dependency_overrides[write_session] = override_write
    yield TestClient(app), ids
    app.dependency_overrides.clear()


def test_get_regia_reports_channel_and_last_event(client):
    c, ids = client
    r = c.get(f"/admin/api/campaigns/{ids['withch']}/regia").json()
    assert r["has_channel"] is True
    assert r["last_event"]["outcome"] == "failure"


def test_enqueue_narrated_event(client):
    c, ids = client
    r = c.post(f"/admin/api/campaigns/{ids['withch']}/regia/event",
               json={"mode": "narrated", "text": "Un tuono scuote la casa"})
    assert r.status_code == 200
    cmds = r.json()["commands"]
    assert cmds[0]["kind"] == "narrate_event" and cmds[0]["status"] == "pending"


def test_event_without_channel_is_400(client):
    c, ids = client
    r = c.post(f"/admin/api/campaigns/{ids['nochan']}/regia/event",
               json={"mode": "direct", "text": "boom"})
    assert r.status_code == 400


def test_override_requires_resolved_event(client):
    c, ids = client
    # 'withch' ha una prova risolta → ok
    ok = c.post(f"/admin/api/campaigns/{ids['withch']}/regia/override", json={"outcome": "success"})
    assert ok.status_code == 200
    # 'nochan' non ha nemmeno il canale → 400
    bad = c.post(f"/admin/api/campaigns/{ids['nochan']}/regia/override", json={"outcome": "success"})
    assert bad.status_code == 400


def test_notes_add_and_delete(client):
    c, ids = client
    cid = ids["withch"]
    r = c.post(f"/admin/api/campaigns/{cid}/notes", json={"text": "la porta sul retro è aperta"})
    notes = r.json()["notes"]
    assert len(notes) == 1
    note_id = notes[0]["id"]
    r2 = c.delete(f"/admin/api/campaigns/{cid}/notes/{note_id}")
    assert r2.status_code == 200 and r2.json()["notes"] == []
