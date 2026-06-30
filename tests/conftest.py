"""Fixture condivise dai test."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from aedo.core.models import Base


@pytest.fixture()
def session() -> Iterator[Session]:
    """Sessione su un database SQLite in memoria, isolata per ogni test."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as s:
        yield s


class FixedRng:
    """RNG deterministico: `randint` restituisce i valori forniti in ordine."""

    def __init__(self, values: list[int]) -> None:
        self._values = list(values)
        self._i = 0

    def randint(self, _a: int, _b: int) -> int:
        value = self._values[self._i]
        self._i += 1
        return value
