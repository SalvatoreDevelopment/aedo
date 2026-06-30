"""Test del motore di risoluzione: dadi ed esito a 3 gradi."""

from __future__ import annotations

import random

import pytest

from aedo.core.models.enums import Outcome
from aedo.core.resolution import (
    Difficulty,
    classify,
    parse_dice,
    resolve,
    roll,
)
from tests.conftest import FixedRng


# --- Dadi -----------------------------------------------------------------

@pytest.mark.parametrize(
    "formula,count,sides,mod",
    [
        ("2d6", 2, 6, 0),
        ("1d20", 1, 20, 0),
        ("d8", 1, 8, 0),
        ("3d6+1", 3, 6, 1),
        ("2d10-2", 2, 10, -2),
        (" 4d4 + 3 ", 4, 4, 3),
    ],
)
def test_parse_dice_valid(formula, count, sides, mod):
    spec = parse_dice(formula)
    assert (spec.count, spec.sides, spec.modifier) == (count, sides, mod)


@pytest.mark.parametrize("bad", ["2x6", "d1", "0d6", "abc", "6", "d"])
def test_parse_dice_invalid(bad):
    with pytest.raises(ValueError):
        parse_dice(bad)


def test_roll_within_range():
    rng = random.Random(42)
    for _ in range(200):
        result = roll("3d6+1", rng=rng)
        assert len(result.rolls) == 3
        assert all(1 <= r <= 6 for r in result.rolls)
        assert 4 <= result.total <= 19  # 3..18 + 1


# --- Classificazione esito ------------------------------------------------

def test_classify_three_tiers():
    # banda = 2, difficoltà = 12
    assert classify(12, 12, 2) is Outcome.SUCCESS
    assert classify(15, 12, 2) is Outcome.SUCCESS
    assert classify(11, 12, 2) is Outcome.SUCCESS_WITH_COST  # come nel mockup
    assert classify(10, 12, 2) is Outcome.SUCCESS_WITH_COST
    assert classify(9, 12, 2) is Outcome.FAILURE


# --- resolve() deterministico --------------------------------------------

def test_resolve_success():
    # 2d6 = 4+4 = 8, + Intuito 4 = 12 vs 12 → successo pieno (cfr. mockup 14 vs 12)
    res = resolve(
        attribute_name="Intuito",
        attribute_value=4,
        difficulty=Difficulty.HARD,  # 12
        rng=FixedRng([4, 4]),
    )
    assert res.outcome is Outcome.SUCCESS
    assert res.total == 12
    assert res.margin == 0
    assert res.summary == "Intuito · 12 vs 12"


def test_resolve_success_with_cost():
    # 2d6 = 4+3 = 7, + Sangue freddo 4 = 11 vs 12 → "riesci, ma…" (cfr. mockup)
    res = resolve(
        attribute_name="Sangue freddo",
        attribute_value=4,
        difficulty=12,
        rng=FixedRng([4, 3]),
    )
    assert res.outcome is Outcome.SUCCESS_WITH_COST
    assert res.total == 11
    assert res.margin == -1


def test_resolve_failure():
    res = resolve(
        attribute_name="Strada",
        attribute_value=2,
        difficulty=Difficulty.HARD,
        rng=FixedRng([2, 2]),
    )
    assert res.outcome is Outcome.FAILURE
    assert res.total == 6


def test_resolve_situational_modifier():
    # 2d6 = 3+3 = 6, + attr 2 + modificatore +2 = 10 vs 10 → successo
    res = resolve(
        attribute_name="Forza",
        attribute_value=2,
        difficulty=Difficulty.MEDIUM,  # 10
        modifier=2,
        rng=FixedRng([3, 3]),
    )
    assert res.outcome is Outcome.SUCCESS
    assert res.modifier == 2
    assert res.total == 10


def test_resolve_respects_blueprint_dice_and_band():
    # Dado e banda diversi (stile cyberpunk): 1d20 con banda 4.
    res = resolve(
        attribute_name="Hacking",
        attribute_value=3,
        difficulty=14,
        dice_formula="1d20",
        band=4,
        rng=FixedRng([8]),  # 8 + 3 = 11; 14-4=10 <= 11 < 14
    )
    assert res.outcome is Outcome.SUCCESS_WITH_COST
    assert res.dice_formula == "1d20"


def test_result_to_dict_serializable():
    res = resolve(
        attribute_name="Intuito",
        attribute_value=1,
        difficulty=10,
        rng=FixedRng([5, 5]),
    )
    d = res.to_dict()
    assert d["outcome"] == res.outcome.value
    assert d["attribute"] == "Intuito"
    assert d["difficulty"] == 10
    assert d["rolls"] == [5, 5]
    assert set(d) >= {"outcome", "attribute", "total", "margin", "dice"}
