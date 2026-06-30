"""Test del service del bot Discord (senza connettersi a Discord).

Il service apre le proprie sessioni via `SessionLocal`: per i test lo
sostituiamo con un SQLite in memoria condiviso (StaticPool), così più sessioni
vedono lo stesso database.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from aedo.bots.discord import service
from aedo.core.memory import FakeEmbedder, MemoryService
from aedo.core.models import Base
from aedo.core.narrator import FakeNarrator


@pytest.fixture()
def bot_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    monkeypatch.setattr(service, "SessionLocal", TestSession)
    # Embedder finto: niente PyTorch nei test.
    monkeypatch.setattr(service, "_memory_service", MemoryService(FakeEmbedder()))
    yield


def _new_campaign(channel_id="c1"):
    return service.create_campaign_in_channel(
        FakeNarrator(),
        channel_id=channel_id, guild_id="g1", owner_discord_id="u1",
        template="noir", campaign_name="L'ombra sul molo", character_name="Sam",
    )


def test_create_campaign_in_channel(bot_db):
    dto = _new_campaign()
    assert dto.opening                      # scena d'apertura generata
    assert dto.character_name == "Sam"
    assert dto.attributes["Intuito"] == 3   # primo attributo potenziato
    assert dto.attributes["Strada"] == 2
    assert service.is_campaign_channel("c1") is True
    assert service.is_campaign_channel("ignoto") is False


def test_create_campaign_without_name_gets_auto_title(bot_db):
    dto = service.create_campaign_in_channel(
        FakeNarrator(),
        channel_id="cX", guild_id="g1", owner_discord_id="u1",
        template="noir", campaign_name="", character_name="Sam",
    )
    assert dto.campaign_name.strip()           # nome generato, non vuoto
    assert "Sam" in dto.campaign_name          # dal titolo proposto dal narratore


def test_run_turn_in_channel(bot_db):
    _new_campaign()
    dto = service.run_player_turn(
        FakeNarrator(force_risky=False),
        channel_id="c1", discord_id="u1", action="mi guardo intorno nel locale",
    )
    assert dto is not None and dto.narration
    assert dto.outcome is None  # azione libera


def test_run_turn_unknown_channel_returns_none(bot_db):
    assert service.run_player_turn(
        FakeNarrator(), channel_id="non-esiste", discord_id="u1", action="x"
    ) is None


def test_sheet_inventory_objectives(bot_db):
    _new_campaign()
    sheet = service.get_sheet("c1")
    assert sheet.name == "Sam" and "Intuito" in sheet.attributes

    # L'apertura del FakeNarrator introduce un primo obiettivo.
    objectives = service.get_objectives("c1")
    assert len(objectives) == 1
    assert objectives[0]["status"] == "open"

    # Inventario inizialmente vuoto.
    assert service.get_inventory("c1") == []


def test_readonly_helpers_on_unknown_channel(bot_db):
    assert service.get_sheet("nope") is None
    assert service.get_inventory("nope") is None
    assert service.get_objectives("nope") is None
