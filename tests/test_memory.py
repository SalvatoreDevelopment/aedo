"""Test della memoria narrativa: embedding e recupero per similarità."""

from __future__ import annotations

from sqlalchemy.orm import Session

from aedo.core.memory import FakeEmbedder, MemoryService
from aedo.core.memory.store import _cosine
from aedo.core.models import Memory
from aedo.core.services.campaign_service import create_campaign_from_template


def _campaign(session: Session):
    return create_campaign_from_template(
        session, template_name="noir", campaign_name="Test"
    )


def test_fake_embedder_is_deterministic_and_lexical():
    emb = FakeEmbedder()
    # Stesso testo → stesso vettore.
    assert emb.embed("Lou il topo") == emb.embed("Lou il topo")
    # Testi che condividono parole sono più simili di testi scollegati.
    a = emb.embed("Lou il topo ha tradito al molo")
    simile = emb.embed("ho rivisto Lou il topo al molo")
    diverso = emb.embed("la magia degli antichi draghi")
    assert _cosine(a, simile) > _cosine(a, diverso)


def test_index_pending_embeds_memories(session: Session):
    campaign = _campaign(session)
    session.add(Memory(campaign=campaign, text="Lou ha tradito il gruppo"))
    session.add(Memory(campaign=campaign, text="Vivian canta al locale"))
    session.flush()

    svc = MemoryService(FakeEmbedder())
    count = svc.index_pending(session, campaign.id)
    assert count == 2
    for mem in campaign.memories:
        assert mem.embedded is True
        assert mem.embedding is not None
    # Già indicizzati: una seconda passata non fa nulla.
    assert svc.index_pending(session, campaign.id) == 0


def test_recall_retrieves_most_relevant(session: Session):
    campaign = _campaign(session)
    session.add_all([
        Memory(campaign=campaign, text="Lou il topo ha tradito il gruppo al molo"),
        Memory(campaign=campaign, text="Vivian canta al locale ogni sera"),
        Memory(campaign=campaign, text="Il vecchio faro è abbandonato da anni"),
    ])
    session.flush()

    svc = MemoryService(FakeEmbedder(), k=2)
    svc.index_pending(session, campaign.id)

    recalled = svc.recall(session, campaign.id, "cosa sai di Lou il topo al molo?")
    assert recalled  # ha trovato qualcosa
    assert "Lou il topo" in recalled[0]  # il più pertinente è in cima


def test_recall_empty_without_memories(session: Session):
    campaign = _campaign(session)
    svc = MemoryService(FakeEmbedder())
    assert svc.recall(session, campaign.id, "qualunque cosa") == []


def test_hybrid_search_boosts_proper_nouns(session: Session):
    """Raffinamento 1: un nome proprio nella query premia il ricordo che lo cita."""
    campaign = _campaign(session)
    session.add_all([
        Memory(campaign=campaign, text="Garrett ti ha promesso aiuto al porto"),
        Memory(campaign=campaign, text="un mercante qualunque ti ha venduto del pane"),
    ])
    session.flush()
    svc = MemoryService(FakeEmbedder(), k=1)
    svc.index_pending(session, campaign.id)

    recalled = svc.recall(session, campaign.id, "cosa mi aveva detto Garrett?")
    assert recalled and "Garrett" in recalled[0]


def test_present_entities_get_priority(session: Session):
    """Raffinamento 2: a parità di pertinenza, vince il ricordo sull'NPC in scena."""
    campaign = _campaign(session)
    session.add_all([
        Memory(campaign=campaign, text="confidenza condivisa sotto le stelle versione A",
               involved_ids=[101]),
        Memory(campaign=campaign, text="confidenza condivisa sotto le stelle versione B",
               involved_ids=[202]),
    ])
    session.flush()
    svc = MemoryService(FakeEmbedder(), k=1)
    svc.index_pending(session, campaign.id)

    # Con il personaggio 202 in scena, deve emergere il ricordo che lo coinvolge.
    recalled = svc.recall(
        session, campaign.id, "confidenza condivisa sotto le stelle", present_ids=[202]
    )
    assert recalled and "versione B" in recalled[0]
