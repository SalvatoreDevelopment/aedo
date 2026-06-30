"""Relationship — un legame fra due personaggi.

È qui che vive il sistema di romance/relazioni, ma il concetto è universale:
amicizia, rivalità, fiducia, attrazione. L'affinità è un numero; le sfumature
narrative ("le hai regalato l'amuleto di tua madre") stanno nella memoria.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin


class Relationship(Base, IdMixin, TimestampMixin):
    __tablename__ = "relationships"

    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    campaign: Mapped["Campaign"] = relationship(  # noqa: F821
        back_populates="relationships"
    )

    # Legame direzionale: come "from" si pone verso "to".
    from_id: Mapped[int] = mapped_column(ForeignKey("characters.id"))
    to_id: Mapped[int] = mapped_column(ForeignKey("characters.id"))

    from_character: Mapped["Character"] = relationship(  # noqa: F821
        foreign_keys=[from_id]
    )
    to_character: Mapped["Character"] = relationship(  # noqa: F821
        foreign_keys=[to_id]
    )

    # Tipo di legame, es. "alleato", "rivale", "interesse romantico".
    kind: Mapped[str] = mapped_column(String(80), default="conoscente")
    # Affinità da -100 (odio) a +100 (devozione).
    affinity: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Relationship {self.from_id}->{self.to_id} {self.kind!r} ({self.affinity:+d})>"
