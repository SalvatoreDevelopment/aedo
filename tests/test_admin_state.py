"""Test degli endpoint di Controllo dello Stato del Banco del Master.

Come per test_api: database SQLite in memoria, TestClient, override delle
sessioni. Qui però si *scrive*, quindi si verifica anche che le regole del
dominio (clamp affinità, risorse non negative, NPC non-giocante) reggano.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from aedo.admin.app import app
from aedo.admin.routes_state import read_session, write_session
from aedo.core.models import Base, Character, Item, Objective, Relationship
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
        camp = create_campaign_from_template(
            s, template_name="fantasy", campaign_name="La rovina di Eldar"
        )
        hero = create_player_character(s, camp, name="Kira", attributes={"Forza": 2})
        villain = Character(campaign=camp, name="Morzan", is_player=False)
        s.add(villain); s.flush()
        s.add(Item(campaign=camp, owner=hero, name="Spada", quantity=1))
        s.add(Relationship(campaign=camp, from_id=hero.id, to_id=villain.id, kind="nemico", affinity=-20))
        s.add(Objective(campaign=camp, title="Sconfiggi Morzan"))
        s.commit()
        ids = {"camp": camp.id, "hero": hero.id, "villain": villain.id}

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
            s.rollback()
            raise
        finally:
            s.close()

    app.dependency_overrides[read_session] = override_read
    app.dependency_overrides[write_session] = override_write
    yield TestClient(app), ids
    app.dependency_overrides.clear()


def _state(c, cid):
    return c.get(f"/admin/api/campaigns/{cid}/state").json()


def test_state_shows_everything_including_npc(client):
    c, ids = client
    st = _state(c, ids["camp"])
    names = {ch["name"] for ch in st["characters"]}
    assert names == {"Kira", "Morzan"}
    assert any(not ch["is_player"] for ch in st["characters"])  # l'NPC è visibile
    assert len(st["items"]) == 1 and len(st["relationships"]) == 1


def test_set_and_adjust_resource_clamped(client):
    c, ids = client
    cid, hid = ids["camp"], ids["hero"]
    c.post(f"/admin/api/campaigns/{cid}/characters/{hid}/resources/set",
           json={"name": "vita", "value": 7})
    r = c.post(f"/admin/api/campaigns/{cid}/characters/{hid}/resources/adjust",
               json={"name": "vita", "delta": -100})
    hero = next(ch for ch in r.json()["characters"] if ch["id"] == hid)
    assert hero["resources"]["vita"] == 0  # mai sotto zero


def test_grant_item_stacks_then_removes(client):
    c, ids = client
    cid, hid = ids["camp"], ids["hero"]
    c.post(f"/admin/api/campaigns/{cid}/items",
           json={"owner_id": hid, "name": "Pozione", "quantity": 2})
    r = c.post(f"/admin/api/campaigns/{cid}/items",
               json={"owner_id": hid, "name": "Pozione", "quantity": 3})
    pot = next(it for it in r.json()["items"] if it["name"] == "Pozione")
    assert pot["quantity"] == 5  # sommate, non duplicate

    r = c.patch(f"/admin/api/campaigns/{cid}/items/{pot['id']}", json={"quantity": 0})
    assert not any(it["name"] == "Pozione" for it in r.json()["items"])  # qty 0 = rimosso


def test_relationship_affinity_clamped_and_duplicate_rejected(client):
    c, ids = client
    cid = ids["camp"]
    rel_id = _state(c, cid)["relationships"][0]["id"]
    r = c.patch(f"/admin/api/campaigns/{cid}/relationships/{rel_id}",
                json={"affinity_delta": -1000})
    assert r.json()["relationships"][0]["affinity"] == -100  # clamp a -100

    dup = c.post(f"/admin/api/campaigns/{cid}/relationships",
                 json={"from_id": ids["hero"], "to_id": ids["villain"], "kind": "x"})
    assert dup.status_code == 400  # legame già esistente


def test_objective_status_change(client):
    c, ids = client
    cid = ids["camp"]
    obj_id = _state(c, cid)["objectives"][0]["id"]
    r = c.post(f"/admin/api/campaigns/{cid}/objectives/{obj_id}/status",
               json={"status": "completed"})
    assert r.json()["objectives"][0]["status"] == "completed"


def test_create_npc_and_delete_rules(client):
    c, ids = client
    cid = ids["camp"]
    r = c.post(f"/admin/api/campaigns/{cid}/npcs",
               json={"name": "Saphira", "description": "un drago"})
    assert any(ch["name"] == "Saphira" for ch in r.json()["characters"])

    # il PG non è eliminabile dal Banco
    bad = c.delete(f"/admin/api/campaigns/{cid}/characters/{ids['hero']}")
    assert bad.status_code == 400

    # l'NPC sì
    ok = c.delete(f"/admin/api/campaigns/{cid}/characters/{ids['villain']}")
    assert ok.status_code == 200
    assert not any(ch["id"] == ids["villain"] for ch in ok.json()["characters"])


def test_conditions_add_remove(client):
    c, ids = client
    cid, hid = ids["camp"], ids["hero"]
    c.post(f"/admin/api/campaigns/{cid}/characters/{hid}/conditions/add",
           json={"condition": "avvelenato"})
    r = c.post(f"/admin/api/campaigns/{cid}/characters/{hid}/conditions/remove",
               json={"condition": "avvelenato"})
    hero = next(ch for ch in r.json()["characters"] if ch["id"] == hid)
    assert "avvelenato" not in hero["conditions"]


def test_unknown_campaign_is_404(client):
    c, _ = client
    assert c.get("/admin/api/campaigns/9999/state").status_code == 404
