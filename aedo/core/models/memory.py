"""Memory — un ricordo della memoria narrativa.

Questo è il livello "semantico" della memoria a due livelli: eventi vissuti,
sintetizzati in frasi memorizzabili e richiamabili quando rilevanti.

Il vettore di embedding vero e proprio NON sta qui: in Fase 3 vivrà in una
tabella virtuale `sqlite-vec`, collegata tramite `id`. Qui teniamo il testo e
i metadati; `embedded` segnala se il vettore è già stato calcolato.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin


class Memory(Base, IdMixin, TimestampMixin):
    __tablename__ = "memories"

    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    campaign: Mapped["Campaign"] = relationship(  # noqa: F821
        back_populates="memories"
    )

    # Il ricordo in linguaggio naturale (es. "Aelar ha tradito il gruppo a Porto").
    text: Mapped[str] = mapped_column(Text)
    # Rilevanza/peso del ricordo (0..1): aiuta a decidere cosa richiamare.
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    # Id dei personaggi coinvolti, per filtrare i ricordi per entità.
    involved_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    # True quando il vettore di embedding è stato calcolato (Fase 3).
    embedded: Mapped[bool] = mapped_column(Boolean, default=False)
    # Il vettore di embedding (lista di float). Calcolato in locale; usato per il
    # recupero per similarità. None finché non calcolato.
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        snippet = (self.text[:40] + "…") if len(self.text) > 40 else self.text
        return f"<Memory {snippet!r}>"
