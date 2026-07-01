"""Test dei messaggi testuali del bot (Aedo che racconta in chat normale)."""

from __future__ import annotations

from aedo.bots.discord import messages
from aedo.bots.discord.service import NewCampaignDTO, TurnDTO
from aedo.core.services.regia import RegiaJob


def test_turn_text_free_action_is_plain():
    dto = TurnDTO(narration="Ti guardi intorno.", roll_summary=None, outcome=None, genre="noir")
    assert messages.turn_text(dto) == "Ti guardi intorno."


def test_turn_text_with_outcome_adds_roll_line():
    dto = TurnDTO(narration="Salti il muro.", roll_summary="2d6=9", outcome="success", genre="fantasy")
    text = messages.turn_text(dto)
    assert "Salti il muro." in text
    assert "🎲" in text and "successo" in text


def test_opening_text_has_scene_and_character():
    dto = NewCampaignDTO(
        campaign_name="Ombre sul molo", character_name="Sam", genre="noir",
        attributes={"Intuito": 3, "Strada": 2}, resources={"salute": 5},
        opening="Piove sul porto.",
    )
    text = messages.opening_text(dto)
    assert "Ombre sul molo" in text
    assert "Piove sul porto." in text
    assert "Sam" in text and "Intuito" in text
    assert "scrivi cosa fai" in text


def test_master_event_text_override_has_prefix():
    job = RegiaJob(command_id=1, channel_id="c", kind="override_last",
                   narration="Il colpo va a segno.", outcome="success", genre="noir")
    text = messages.master_event_text(job)
    assert "Il destino si riscrive" in text
    assert "successo" in text


def test_master_event_text_plain_event():
    job = RegiaJob(command_id=2, channel_id="c", kind="inject_event",
                   narration="Le luci si spengono.", outcome=None, genre="noir")
    assert messages.master_event_text(job) == "Le luci si spengono."


def test_chunks_splits_long_text_under_limit():
    long_text = " ".join(["parola"] * 800)  # ~5600 caratteri
    parts = messages.chunks(long_text)
    assert len(parts) > 1
    assert all(len(p) <= 1900 for p in parts)
    assert "".join(p for p in parts).replace(" ", "").count("parola") == 800


def test_chunks_short_text_single_message():
    assert messages.chunks("ciao") == ["ciao"]
