"""Test dell'Editor regole/genere (Blueprint) del Banco."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from aedo.admin.app import app
from aedo.admin.routes_state import read_session, write_session
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


def test_get_blueprint_shape(client):
    c, cid = client
    bp = c.get(f"/admin/api/campaigns/{cid}/blueprint").json()
    assert "fantasy" in bp["genre"]
    assert len(bp["attributes"]) == 4
    assert len(bp["crunch_options"]) == 3
    assert bp["ai_model"]  # non vuoto


def test_patch_scalar_fields(client):
    c, cid = client
    r = c.patch(f"/admin/api/campaigns/{cid}/blueprint",
                json={"genre": "horror gotico", "tone": "cupo"})
    assert r.status_code == 200
    assert r.json()["genre"] == "horror gotico" and r.json()["tone"] == "cupo"


def test_invalid_dice_and_crunch_rejected(client):
    c, cid = client
    assert c.patch(f"/admin/api/campaigns/{cid}/blueprint",
                   json={"dice_formula": "non-un-dado"}).status_code == 400
    assert c.patch(f"/admin/api/campaigns/{cid}/blueprint",
                   json={"crunch_level": "inesistente"}).status_code == 400
    # una formula valida passa e viene normalizzata
    r = c.patch(f"/admin/api/campaigns/{cid}/blueprint", json={"dice_formula": "1D20"})
    assert r.status_code == 200 and r.json()["dice_formula"] == "1d20"


def test_attributes_replace_and_reject_duplicates(client):
    c, cid = client
    r = c.patch(f"/admin/api/campaigns/{cid}/blueprint",
                json={"attributes": [{"name": "Mira", "description": "prendere la mira"}]})
    assert r.status_code == 200 and len(r.json()["attributes"]) == 1
    dup = c.patch(f"/admin/api/campaigns/{cid}/blueprint",
                  json={"attributes": [{"name": "A"}, {"name": "a"}]})
    assert dup.status_code == 400


def test_resources_clamped_and_band_validated(client):
    c, cid = client
    r = c.patch(f"/admin/api/campaigns/{cid}/blueprint",
                json={"default_resources": {"vita": -5}})
    assert r.status_code == 200 and r.json()["default_resources"]["vita"] == 0
    assert c.patch(f"/admin/api/campaigns/{cid}/blueprint",
                   json={"success_band": -1}).status_code == 400
