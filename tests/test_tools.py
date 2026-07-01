"""Test degli strumenti del master: oracolo, generatori, statistiche."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from aedo.core.models import Base, Character, EventLog, Objective, Outcome
from aedo.core.services import tools
from aedo.core.services.campaign_service import (
    create_campaign_from_template,
    create_player_character,
)


class FakeRng:
    """RNG deterministico: random() fisso, choice() prende il primo."""

    def __init__(self, value: float) -> None:
        self.value = value

    def random(self) -> float:
        return self.value

    def choice(self, seq):
        return seq[0]


def test_oracle_grades_by_threshold():
    # score 0.6 → "Sì, ma…"; il bias sposta il risultato in su o in giù.
    assert tools.ask_oracle("?", "even", FakeRng(0.6)).grade == "yes_but"
    assert tools.ask_oracle("?", "likely", FakeRng(0.6)).grade == "yes"      # 0.82
    assert tools.ask_oracle("?", "unlikely", FakeRng(0.6)).grade == "no_but"  # 0.38


def test_oracle_extremes():
    assert tools.ask_oracle("?", "even", FakeRng(0.9)).answer == "Sì"
    assert tools.ask_oracle("?", "even", FakeRng(0.05)).answer == "No"


def test_category_and_generators():
    assert tools.category_of("megalopoli al neon") == "cyber"
    assert tools.category_of("noir anni '40") == "noir"
    assert tools.category_of("fantasy epico") == "fantasy"
    assert tools.category_of("qualcosa di strano") == "generic"

    names = tools.generate_names("fantasy epico", 6)
    assert len(names) == 6 and all(names)
    npc = tools.generate_npc("noir")
    assert npc["name"] and npc["role"] and npc["trait"]
    hook = tools.generate_hook("cyberpunk")
    assert hook and "{" not in hook  # i segnaposto sono stati riempiti


@pytest.fixture()
def session_with_data():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool, future=True,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestSession() as s:
        camp = create_campaign_from_template(s, template_name="noir", campaign_name="Indagine")
        create_player_character(s, camp, name="Sam")
        s.add(Character(campaign=camp, name="Lou", is_player=False))
        s.add(EventLog(campaign=camp, actor="Aedo", action_text="(apertura)", narration="Inizio."))
        s.add(EventLog(campaign=camp, actor="Sam", action_text="salto il muro",
                       outcome=Outcome.SUCCESS, narration="Ce la fai."))
        s.add(Objective(campaign=camp, title="Trova il colpevole"))
        s.commit()
        cid = camp.id
    with TestSession() as s:
        yield s, cid


def test_campaign_stats(session_with_data):
    s, cid = session_with_data
    st = tools.campaign_stats(s, cid)
    assert st.turns == 1                      # l'apertura non conta
    assert st.events_total == 2
    assert st.outcomes["success"] == 1
    assert st.npc_count == 1                  # Lou
    assert st.objectives["open"] == 1
