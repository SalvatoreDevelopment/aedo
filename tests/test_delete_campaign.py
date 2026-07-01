"""Test dell'eliminazione di una singola campagna (dati + coda cancellazione canale)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from aedo.admin import state_ops
from aedo.admin.app import app
from aedo.admin.routes_state import read_session, write_session
from aedo.core.models import Base, Blueprint, Campaign, Character, CommandStatus, EventLog
from aedo.core.services import regia
from aedo.core.services.campaign_service import (
    create_campaign_from_template,
    create_player_character,
)


def _make_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool, future=True,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@pytest.fixture()
def db():
    return _make_session()


def test_delete_removes_campaign_blueprint_and_queues_channel(db):
    TestSession = db
    with TestSession() as s:
        noir = create_campaign_from_template(s, template_name="noir", campaign_name="Da cancellare")
        noir.discord_channel_id = "999"
        create_player_character(s, noir, name="Sam")
        s.add(EventLog(campaign=noir, actor="Sam", action_text="entro", narration="…"))
        fant = create_campaign_from_template(s, template_name="fantasy", campaign_name="Resta")
        s.commit()
        noir_id, fant_id, noir_bp = noir.id, fant.id, noir.blueprint_id

    with TestSession() as s:
        channel = state_ops.delete_campaign(s, noir_id)
        s.commit()
        assert channel == "999"

    with TestSession() as s:
        assert s.get(Campaign, noir_id) is None            # campagna sparita
        assert s.get(Campaign, fant_id) is not None         # l'altra resta
        assert s.get(Blueprint, noir_bp) is None            # blueprint orfano eliminato
        n_chars = s.scalar(
            select(func.count()).select_from(Character).where(Character.campaign_id == noir_id)
        )
        assert n_chars == 0                                 # cascata sui personaggi
        dels = regia.pending_channel_deletions(s)
        assert len(dels) == 1 and dels[0].channel_id == "999"


def test_delete_without_channel_queues_nothing(db):
    TestSession = db
    with TestSession() as s:
        camp = create_campaign_from_template(s, template_name="noir", campaign_name="Senza canale")
        s.commit()
        cid = camp.id
    with TestSession() as s:
        assert state_ops.delete_campaign(s, cid) is None
        s.commit()
        assert regia.pending_channel_deletions(s) == []


def test_channel_deletion_mark_done(db):
    TestSession = db
    with TestSession() as s:
        camp = create_campaign_from_template(s, template_name="noir", campaign_name="X")
        camp.discord_channel_id = "42"
        s.commit()
        cid = camp.id
    with TestSession() as s:
        state_ops.delete_campaign(s, cid)
        s.commit()
    with TestSession() as s:
        d = regia.pending_channel_deletions(s)[0]
        regia.mark_channel_deletion(s, d.id)
        s.commit()
    with TestSession() as s:
        assert regia.pending_channel_deletions(s) == []  # non più pending


@pytest.fixture()
def client():
    TestSession = _make_session()
    with TestSession() as s:
        camp = create_campaign_from_template(s, template_name="noir", campaign_name="Bersaglio")
        camp.discord_channel_id = "777"
        create_player_character(s, camp, name="Sam")
        s.commit()
        cid = camp.id

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
    yield TestClient(app), cid
    app.dependency_overrides.clear()


def test_delete_endpoint(client):
    c, cid = client
    r = c.delete(f"/admin/api/campaigns/{cid}")
    assert r.status_code == 200 and r.json()["channel_queued"] is True
    assert c.get(f"/admin/api/campaigns/{cid}/state").status_code == 404  # non esiste più
    assert c.delete("/admin/api/campaigns/99999").status_code == 404       # inesistente
