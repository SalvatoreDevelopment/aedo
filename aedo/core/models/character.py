"""Character — un personaggio della campagna (giocante o NPC).

Gli attributi NON sono colonne fisse: sono un dizionario che segue gli
attributi definiti dal Blueprint. È così che lo stesso modello rappresenta
un mago, un netrunner o un detective.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin


class Character(Base, IdMixin, TimestampMixin):
    __tablename__ = "characters"

    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    campaign: Mapped["Campaign"] = relationship(  # noqa: F821
        back_populates="characters"
    )

    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")

    # True = personaggio di un giocatore; False = NPC gestito dal narratore.
    is_player: Mapped[bool] = mapped_column(Boolean, default=False)
    # Discord id del giocatore (solo se is_player).
    discord_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Valori sugli attributi definiti dal Blueprint, es. {"Forza": 3, "Magia": 1}.
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Risorse correnti, es. {"hp": 8, "mana": 2}.
    resources: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Stati/condizioni temporanee, es. ["avvelenato", "innamorato"].
    conditions: Mapped[list[str]] = mapped_column(JSON, default=list)

    items: Mapped[list["Item"]] = relationship(  # noqa: F821
        back_populates="owner", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        role = "PG" if self.is_player else "NPC"
        return f"<Character {self.name!r} ({role})>"
