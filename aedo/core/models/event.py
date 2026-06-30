"""EventLog — la cronologia grezza della campagna (il "diario").

Ogni riga è un turno: chi ha agito, cosa ha tentato, l'esito del tiro e la
narrazione prodotta da Aedo. È la fonte da cui si distillano i ricordi e da
cui la dashboard web ricostruisce il racconto della partita.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin
from .enums import Outcome


class EventLog(Base, IdMixin, TimestampMixin):
    __tablename__ = "events"

    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    campaign: Mapped["Campaign"] = relationship(  # noqa: F821
        back_populates="events"
    )

    # Chi agisce (nome del personaggio o "narratore" per eventi del mondo).
    actor: Mapped[str] = mapped_column(String(120), default="")
    # Cosa il giocatore ha dichiarato di fare, in linguaggio naturale.
    action_text: Mapped[str] = mapped_column(Text, default="")
    # Esito della risoluzione, se l'azione era rischiosa (altrimenti None).
    outcome: Mapped[Outcome | None] = mapped_column(nullable=True)
    # Dettagli del tiro (dado, attributo, difficoltà...), per trasparenza.
    roll: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # La narrazione prodotta da Aedo in risposta.
    narration: Mapped[str] = mapped_column(Text, default="")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EventLog {self.actor!r}: {self.action_text[:30]!r}>"
