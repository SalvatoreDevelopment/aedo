"""Test della regia narrativa (coda comandi + esecuzione), col narratore finto."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from aedo.core.models import (
    Base,
    CommandKind,
    CommandStatus,
    EventLog,
    MasterCommand,
    Outcome,
)
from aedo.core.narrator.fake import FakeNarrator
from aedo.core.services import regia
from aedo.core.services.campaign_service import (
    create_campaign_from_template,
    create_player_character,
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool, future=True,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestSession() as s:
        camp = create_campaign_from_template(s, template_name="noir", campaign_name="Ombre")
        camp.discord_channel_id = "555"
        create_player_character(s, camp, name="Sam")
        s.add(EventLog(
            campaign=camp, actor="Sam", action_text="scasso la porta",
            outcome=Outcome.FAILURE, narration="Non ci riesci.",
        ))
        s.commit()
        cid = camp.id
    return TestSession, cid


def test_inject_event_posts_text_verbatim(db):
    TestSession, cid = db
    with TestSession() as s:
        regia.enqueue(s, cid, CommandKind.INJECT_EVENT, "Le luci si spengono di colpo.")
        s.commit()
    with TestSession() as s:
        jobs = regia.run_pending(s, FakeNarrator())
        s.commit()
        assert len(jobs) == 1
        assert jobs[0].narration == "Le luci si spengono di colpo."
        assert jobs[0].channel_id == "555"
    with TestSession() as s:
        cmd = s.scalar(select(MasterCommand))
        assert cmd.status is CommandStatus.DONE
        aedo_events = s.scalars(select(EventLog).where(EventLog.actor == "Aedo")).all()
        assert any("luci si spengono" in e.narration for e in aedo_events)


def test_narrate_event_runs_through_narrator(db):
    TestSession, cid = db
    with TestSession() as s:
        regia.enqueue(s, cid, CommandKind.NARRATE_EVENT, "un corvo entra dalla finestra")
        s.commit()
    with TestSession() as s:
        jobs = regia.run_pending(s, FakeNarrator())
        s.commit()
        assert len(jobs) == 1
        assert "corvo" in jobs[0].narration  # il fake ripete l'azione nel testo
        assert jobs[0].outcome is None


def test_override_rewrites_last_outcome(db):
    TestSession, cid = db
    with TestSession() as s:
        regia.enqueue(s, cid, CommandKind.OVERRIDE_LAST, "success")
        s.commit()
    with TestSession() as s:
        jobs = regia.run_pending(s, FakeNarrator())
        s.commit()
        assert jobs[0].outcome == "success"
    with TestSession() as s:
        ev = s.scalar(select(EventLog).where(EventLog.action_text == "scasso la porta"))
        assert ev.outcome is Outcome.SUCCESS  # corretto retroattivamente


def test_override_without_resolved_event_errors(db):
    TestSession, _ = db
    with TestSession() as s:
        camp = create_campaign_from_template(s, template_name="noir", campaign_name="Vuota")
        camp.discord_channel_id = "1"
        create_player_character(s, camp, name="X")
        s.commit()
        cid2 = camp.id
        regia.enqueue(s, cid2, CommandKind.OVERRIDE_LAST, "success")
        s.commit()
    with TestSession() as s:
        jobs = regia.run_pending(s, FakeNarrator())
        s.commit()
        assert jobs == []
        cmd = s.scalar(select(MasterCommand).where(MasterCommand.campaign_id == cid2))
        assert cmd.status is CommandStatus.ERROR


def test_command_without_channel_errors(db):
    TestSession, _ = db
    with TestSession() as s:
        camp = create_campaign_from_template(s, template_name="noir", campaign_name="SenzaCanale")
        create_player_character(s, camp, name="Y")
        s.commit()
        cid3 = camp.id
        regia.enqueue(s, cid3, CommandKind.INJECT_EVENT, "boom")
        s.commit()
    with TestSession() as s:
        jobs = regia.run_pending(s, FakeNarrator())
        s.commit()
        assert jobs == []
        cmd = s.scalar(select(MasterCommand).where(MasterCommand.campaign_id == cid3))
        assert cmd.status is CommandStatus.ERROR


def test_notes_crud(db):
    TestSession, cid = db
    with TestSession() as s:
        note = regia.add_note(s, cid, "il maggiordomo mente")
        s.commit()
        nid = note.id
    with TestSession() as s:
        notes = regia.list_notes(s, cid)
        assert len(notes) == 1 and "maggiordomo" in notes[0].text
        assert regia.delete_note(s, cid, nid) is True
        s.commit()
    with TestSession() as s:
        assert regia.list_notes(s, cid) == []
