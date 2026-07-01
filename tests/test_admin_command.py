"""Test degli endpoint del Quadro di Comando (non avviano servizi veri)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aedo.admin.app import app
from aedo.admin.services import build_supervisor


@pytest.fixture()
def client(monkeypatch):
    # Il lifespan non gira nei test: popoliamo il supervisore a mano.
    app.state.supervisor = build_supervisor()
    opened = {}
    monkeypatch.setattr(
        "aedo.admin.routes_command.webbrowser.open",
        lambda url: opened.setdefault("url", url),
    )
    yield TestClient(app), opened


def test_list_services_returns_three_levers(client):
    c, _ = client
    r = c.get("/admin/api/command/services")
    assert r.status_code == 200
    keys = {s["key"] for s in r.json()}
    assert keys == {"api", "bot", "web"}
    assert all(s["state"] in {"stopped", "unavailable"} for s in r.json())


def test_open_service_launches_browser_for_page(client):
    c, opened = client
    r = c.post("/admin/api/command/services/api/open")
    assert r.status_code == 200
    # l'API espone /health: l'apertura punta alla home, senza quel suffisso
    assert opened["url"] == "http://127.0.0.1:8000/"


def test_open_service_without_page_is_400(client):
    c, _ = client
    r = c.post("/admin/api/command/services/bot/open")  # il bot non ha URL
    assert r.status_code == 400


def test_open_unknown_service_is_404(client):
    c, _ = client
    assert c.post("/admin/api/command/services/nope/open").status_code == 404
