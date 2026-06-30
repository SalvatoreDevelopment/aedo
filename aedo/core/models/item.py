"""Item — un oggetto generico.

Volutamente neutro rispetto al genere: può essere una spada, una pistola
laser, un indizio, una lettera d'amore. Le caratteristiche specifiche vivono
nel campo libero `properties`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin


class Item(Base, IdMixin, TimestampMixin):
    __tablename__ = "items"

    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    campaign: Mapped["Campaign"] = relationship(  # noqa: F821
        back_populates="items"
    )

    # Proprietario: un personaggio, oppure None se è "nel mondo".
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("characters.id"), nullable=True
    )
    owner: Mapped["Character | None"] = relationship(  # noqa: F821
        back_populates="items"
    )

    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    # Proprietà arbitrarie definite di volta in volta dal narratore.
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Item {self.name!r} x{self.quantity}>"
