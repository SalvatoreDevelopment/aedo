"""Test dei template di genere e del servizio di creazione campagna."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from aedo.core.models import Blueprint, CampaignMode, CrunchLevel
from aedo.core.services.campaign_service import (
    create_campaign_from_template,
    create_player_character,
)
from aedo.templates import get_template, list_templates


def test_all_templates_present():
    names = list_templates()
    assert {"noir", "fantasy", "cyberpunk"} <= set(names)


def test_templates_are_genre_agnostic():
    """La prova del nove: tre generi, tre set di attributi diversi, stesso modello."""
    noir = {a["name"] for a in get_template("noir").attributes}
    fantasy = {a["name"] for a in get_template("fantasy").attributes}
    cyber = {a["name"] for a in get_template("cyberpunk").attributes}

    assert "Intuito" in noir
    assert "Forza" in fantasy
    assert "Hacking" in cyber
    # Nessun genere condivide l'intero set: sono davvero distinti.
    assert noir != fantasy != cyber


def test_template_carries_mechanics():
    cyber = get_template("cyberpunk")
    assert cyber.dice_formula == "1d20"
    assert cyber.success_band == 4
    assert cyber.crunch_level is CrunchLevel.TACTICAL
    assert cyber.is_template is True


def test_get_template_case_insensitive():
    assert get_template("NOIR").genre == get_template("noir").genre


def test_get_template_unknown():
    with pytest.raises(KeyError):
        get_template("western-spaziale")


def test_create_campaign_from_template(session: Session):
    campaign = create_campaign_from_template(
        session,
        template_name="noir",
        campaign_name="L'ombra sul molo",
        owner_discord_id="42",
    )
    assert campaign.id is not None
    assert campaign.mode is CampaignMode.SINGLE
    # La campagna possiede una COPIA del blueprint, non il template.
    assert campaign.blueprint.is_template is False
    assert campaign.blueprint.genre.startswith("noir")


def test_campaign_blueprint_is_independent_copy(session: Session):
    """Modificare il blueprint di una campagna non deve toccare il template
    né altre campagne create dallo stesso template."""
    c1 = create_campaign_from_template(
        session, template_name="fantasy", campaign_name="A"
    )
    c2 = create_campaign_from_template(
        session, template_name="fantasy", campaign_name="B"
    )
    c1.blueprint.tone = "STRAVOLTO"
    session.flush()

    assert c2.blueprint.tone != "STRAVOLTO"
    # Anche il template originale resta intatto.
    assert get_template("fantasy").tone != "STRAVOLTO"
    # Sono tre Blueprint distinti nel DB (2 campagne) + nessun template persistito.
    assert session.query(Blueprint).count() == 2


def test_create_player_character_defaults(session: Session):
    campaign = create_campaign_from_template(
        session, template_name="cyberpunk", campaign_name="Night City Blues"
    )
    pc = create_player_character(
        session,
        campaign,
        name="V",
        discord_id="7",
        attributes={"Hacking": 3},
    )
    # Attributi del blueprint inizializzati; quelli passati sovrascrivono.
    assert pc.attributes["Hacking"] == 3
    assert pc.attributes["Riflessi"] == 0
    assert set(pc.attributes) == {"Hacking", "Riflessi", "Strada", "Sangue freddo"}
    # Le risorse partono dai default del blueprint.
    assert pc.resources == {"salute": 6, "umanità": 5, "eddies": 200}
    assert pc.is_player is True
