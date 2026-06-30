"""Test del game loop end-to-end con il narratore finto (nessuna chiave/rete)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from aedo.core.models import EventLog, ObjectiveStatus, Outcome, Relationship
from aedo.core.narrator import FakeNarrator, StateChanges
from aedo.core.services.campaign_service import (
    create_campaign_from_template,
    create_player_character,
)
from aedo.core.services.game_service import play_turn, start_campaign
from tests.conftest import FixedRng


def _setup(session: Session):
    campaign = create_campaign_from_template(
        session, template_name="noir", campaign_name="L'ombra sul molo"
    )
    sam = create_player_character(
        session, campaign, name="Sam", attributes={"Sangue freddo": 2, "Intuito": 3}
    )
    return campaign, sam


def test_start_campaign_creates_opening(session: Session):
    campaign, sam = _setup(session)
    opening = start_campaign(session, campaign, sam, FakeNarrator(), premise="vendetta")

    assert opening  # incipit non vuoto
    assert campaign.current_summary  # la "scena" è impostata
    # L'apertura è registrata come evento del narratore.
    first_event = campaign.events[0]
    assert first_event.actor == "Aedo"
    assert first_event.outcome is None
    # Ha introdotto un primo obiettivo.
    assert len(campaign.objectives) == 1


def test_start_campaign_auto_titles_when_unnamed(session: Session):
    campaign, sam = _setup(session)
    campaign.name = ""  # l'utente non ha dato un nome
    start_campaign(session, campaign, sam, FakeNarrator())
    assert campaign.name.strip()       # ora ha un titolo
    assert "Sam" in campaign.name      # proposto dal narratore


def test_start_campaign_keeps_given_name(session: Session):
    campaign, sam = _setup(session)  # nome = "L'ombra sul molo"
    start_campaign(session, campaign, sam, FakeNarrator())
    assert campaign.name == "L'ombra sul molo"  # il nome dato non viene toccato


def test_free_action_no_roll(session: Session):
    campaign, sam = _setup(session)
    result = play_turn(session, campaign, sam, "mi guardo intorno nella sala", FakeNarrator())

    assert result.assessment.is_risky is False
    assert result.resolution is None
    # L'evento è registrato senza esito di tiro.
    event = session.get(EventLog, result.event_id)
    assert event.outcome is None
    assert event.narration


def test_risky_action_rolls_and_logs(session: Session):
    campaign, sam = _setup(session)
    nar = FakeNarrator(force_risky=True, attribute="Sangue freddo", difficulty="hard")
    # 2d6 = 4+3 = 7, + Sangue freddo 2 = 9 vs 12 → fallimento
    result = play_turn(session, campaign, sam, "seguo Lou nella nebbia", nar, rng=FixedRng([4, 3]))

    assert result.resolution is not None
    assert result.resolution.total == 9
    assert result.resolution.outcome is Outcome.FAILURE
    event = session.get(EventLog, result.event_id)
    assert event.outcome is Outcome.FAILURE
    assert event.roll["attribute"] == "Sangue freddo"


def test_changes_applied_resources_conditions_memory(session: Session):
    campaign, sam = _setup(session)
    changes = StateChanges(
        resource_deltas={"nervi": -1, "salute": -10},  # salute non scende sotto 0
        conditions_add=["scosso"],
        memory="Sam ha visto qualcosa che non doveva.",
        memory_importance=0.8,
    )
    nar = FakeNarrator(force_risky=False, scripted_changes=changes)
    play_turn(session, campaign, sam, "apro la porta sul retro", nar)

    session.refresh(sam)
    assert sam.resources["nervi"] == 2  # 3 - 1
    assert sam.resources["salute"] == 0  # clampato a 0
    assert "scosso" in sam.conditions
    assert len(campaign.memories) == 1
    assert campaign.memories[0].embedded is False  # embedding rimandato alla Fase 3


def test_romance_relationship_created(session: Session):
    """Un cambiamento di relazione crea l'NPC e il legame: il romance funziona."""
    campaign, sam = _setup(session)
    changes = StateChanges(
        relationship_changes=[{"name": "Vivian", "kind": "interesse", "affinity_delta": 8}]
    )
    nar = FakeNarrator(force_risky=False, scripted_changes=changes)
    play_turn(session, campaign, sam, "offro da bere a Vivian", nar)

    rel = session.query(Relationship).one()
    assert rel.kind == "interesse"
    assert rel.affinity == 8
    # L'NPC Vivian è stato creato automaticamente.
    npc = rel.to_character
    assert npc.name == "Vivian" and npc.is_player is False


def test_objectives_open_and_complete(session: Session):
    campaign, sam = _setup(session)
    # Turno 1: apre un obiettivo.
    play_turn(
        session, campaign, sam, "accetto l'incarico",
        FakeNarrator(scripted_changes=StateChanges(
            new_objectives=[{"title": "Scopri chi ha ucciso la cantante"}]
        )),
    )
    assert campaign.objectives[0].status is ObjectiveStatus.OPEN

    # Turno 2: lo completa.
    play_turn(
        session, campaign, sam, "smaschero l'assassino",
        FakeNarrator(scripted_changes=StateChanges(
            completed_objectives=["Scopri chi ha ucciso la cantante"]
        )),
    )
    session.refresh(campaign.objectives[0])
    assert campaign.objectives[0].status is ObjectiveStatus.COMPLETED


def test_play_turn_with_memory_indexes_and_recalls(session: Session):
    from aedo.core.memory import FakeEmbedder, MemoryService

    campaign, sam = _setup(session)
    mem = MemoryService(FakeEmbedder())

    # Turno che genera un ricordo saliente.
    nar = FakeNarrator(
        force_risky=False,
        scripted_changes=StateChanges(
            memory="Lou il topo ti ha mentito al molo", memory_importance=0.9
        ),
    )
    play_turn(session, campaign, sam, "interrogo Lou", nar, memory=mem)

    # Il ricordo è stato indicizzato (embedding calcolato).
    assert campaign.memories[0].embedded is True
    # E viene recuperato da una situazione pertinente, anche turni dopo.
    relevant = mem.recall(session, campaign.id, "cosa mi aveva detto Lou il topo al molo?")
    assert any("Lou il topo" in r for r in relevant)


def test_recent_events_feed_context(session: Session):
    campaign, sam = _setup(session)
    play_turn(session, campaign, sam, "entro nel locale", FakeNarrator())
    play_turn(session, campaign, sam, "ordino un whisky", FakeNarrator())
    # Il terzo turno deve "vedere" i due precedenti nel contesto.
    from aedo.core.services.game_service import build_context

    ctx = build_context(session, campaign, sam, "studio la sala")
    assert len(ctx.recent_events) == 2
