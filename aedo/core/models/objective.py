"""Objective — un obiettivo / quest astratto.

Niente "tipi di quest" hard-coded (KILL/FETCH/...): un obiettivo è solo una
cosa da raggiungere, descritta in linguaggio naturale. Vale per "uccidi il
drago", "risolvi l'omicidio" o "conquista il suo cuore".
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin
from .enums import ObjectiveStatus


class Objective(Base, IdMixin, TimestampMixin):
    __tablename__ = "objectives"

    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    campaign: Mapped["Campaign"] = relationship(  # noqa: F821
        back_populates="objectives"
    )

    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ObjectiveStatus] = mapped_column(default=ObjectiveStatus.OPEN)
    # Criteri di completamento liberi, interpretati dal narratore.
    criteria: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Personaggio che ha assegnato l'obiettivo (opzionale).
    giver_id: Mapped[int | None] = mapped_column(
        ForeignKey("characters.id"), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Objective {self.title!r} ({self.status.value})>"
