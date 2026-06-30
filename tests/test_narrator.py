"""Test del parsing degli output del modello e del narratore finto."""

from __future__ import annotations

from aedo.core.narrator import FakeNarrator, NarratorContext, get_narrator
from aedo.core.narrator.parsing import (
    extract_json,
    parse_assessment,
    parse_narration,
    parse_turn,
)


def _ctx(action: str) -> NarratorContext:
    return NarratorContext(
        genre="noir", tone="cupo", narrator_persona="", special_rules="",
        crunch_level="narrative", attribute_names=["Intuito", "Sangue freddo"],
        difficulty_options=["easy", "medium", "hard"],
        character_name="Sam", character_description="",
        character_attributes={"Intuito": 2, "Sangue freddo": 1},
        character_resources={"salute": 5}, character_conditions=[],
        current_summary="", player_action=action,
    )


def test_extract_json_from_fence():
    raw = 'Ecco:\n```json\n{"is_risky": true}\n```\nfine'
    assert extract_json(raw) == {"is_risky": True}


def test_extract_json_from_loose_text():
    raw = 'certo {"a": 1, "b": 2} ok'
    assert extract_json(raw) == {"a": 1, "b": 2}


def test_parse_assessment_risky():
    a = parse_assessment('{"is_risky": true, "attribute": "Intuito", "difficulty": "hard"}')
    assert a.is_risky and a.attribute == "Intuito" and a.difficulty == "hard"


def test_parse_assessment_non_risky_nullifies_fields():
    a = parse_assessment('{"is_risky": false, "attribute": "Intuito", "difficulty": "hard"}')
    assert a.is_risky is False
    assert a.attribute is None and a.difficulty is None


def test_parse_narration_full():
    raw = """{
      "narration": "Lou parla.",
      "new_summary": "Sei nel vicolo.",
      "changes": {
        "resource_deltas": {"salute": -1, "ignota": "x"},
        "conditions_add": ["ferito"],
        "relationship_changes": [{"name": "Lou", "kind": "informatore", "affinity_delta": 5}],
        "new_items": [{"name": "biglietto", "quantity": 1}],
        "new_objectives": [{"title": "Trova il porto"}],
        "memory": "Lou ha fatto un nome.", "memory_importance": 0.9
      }
    }"""
    n = parse_narration(raw)
    assert n.text == "Lou parla."
    assert n.new_summary == "Sei nel vicolo."
    # 'ignota' con valore non intero viene scartata.
    assert n.changes.resource_deltas == {"salute": -1}
    assert n.changes.conditions_add == ["ferito"]
    assert n.changes.relationship_changes[0]["name"] == "Lou"
    assert n.changes.memory_importance == 0.9


def test_parse_turn_free_action_includes_narration():
    raw = '{"is_risky": false, "narration": "Cammini nel vicolo.", "new_summary": "Sei nel vicolo.", "changes": {"resource_deltas": {"nervi": -1}}}'
    assessment, narration = parse_turn(raw)
    assert assessment.is_risky is False
    assert narration is not None
    assert narration.text == "Cammini nel vicolo."
    assert narration.changes.resource_deltas == {"nervi": -1}


def test_parse_turn_risky_has_no_narration():
    raw = '{"is_risky": true, "attribute": "Intuito", "difficulty": "hard"}'
    assessment, narration = parse_turn(raw)
    assert assessment.is_risky and assessment.attribute == "Intuito"
    assert narration is None


def test_default_turn_free_action_narrates():
    """Il metodo turn() di default narra subito le azioni libere."""
    nar = FakeNarrator(force_risky=False)
    assessment, narration = nar.turn(_ctx("mi guardo intorno"))
    assert assessment.is_risky is False
    assert narration is not None and narration.text


def test_default_turn_risky_defers_narration():
    nar = FakeNarrator(force_risky=True, attribute="Intuito")
    assessment, narration = nar.turn(_ctx("attacco"))
    assert assessment.is_risky is True
    assert narration is None  # la narrazione arriva dopo il tiro


def test_parse_narration_salvages_truncated_json():
    # JSON troncato a metà (come quando il modello supera max_tokens).
    truncated = '{"narration": "Scavalchi il bancone e afferri il barista", "changes": {"resource_delt'
    n = parse_narration(truncated)
    assert "Scavalchi il bancone" in n.text  # narrazione recuperata, niente crash


def test_parse_turn_salvages_truncated_json():
    truncated = '{"is_risky": false, "narration": "Cammini lentamente nel vicolo buio'
    assessment, narration = parse_turn(truncated)
    assert assessment.is_risky is False
    assert narration is not None and "Cammini" in narration.text


def test_fake_assess_heuristic():
    nar = FakeNarrator()
    assert nar.assess(_ctx("mi guardo intorno")).is_risky is False
    assert nar.assess(_ctx("attacco la guardia")).is_risky is True


def test_fake_assess_forced():
    nar = FakeNarrator(force_risky=True, attribute="Sangue freddo", difficulty="hard")
    a = nar.assess(_ctx("respiro"))
    assert a.is_risky and a.attribute == "Sangue freddo" and a.difficulty == "hard"


def test_get_narrator_fake():
    assert get_narrator("fake").name == "fake"
