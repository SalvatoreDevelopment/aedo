"""Blueprint — il "ruleset" configurabile di una campagna.

È ciò che rende Aedo indipendente dal genere: gli attributi, il tono e le
regole NON sono scritti nel codice, ma sono *dati* definiti qui. Lo stesso
motore fa girare un noir e un fantasy: cambia solo il Blueprint.

Un Blueprint con `is_template=True` è un preset riutilizzabile (Fantasy,
Sci-Fi, Noir, Romance...) da cui si possono creare nuove campagne.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin
from .enums import CrunchLevel


class Blueprint(Base, IdMixin, TimestampMixin):
    __tablename__ = "blueprints"

    name: Mapped[str] = mapped_column(String(120))
    # Genere e ambientazione in linguaggio naturale (es. "cyberpunk noir").
    genre: Mapped[str] = mapped_column(String(120), default="")
    # Tono / voce richiesti al narratore (es. "cupo, ironico, adulto").
    tone: Mapped[str] = mapped_column(String(255), default="")
    # Persona del Dungeon Master (spunto da Dungeon-master-OS): come "recita" Aedo.
    narrator_persona: Mapped[str] = mapped_column(Text, default="")

    # Quanto mostrare le meccaniche (configurabile per campagna).
    crunch_level: Mapped[CrunchLevel] = mapped_column(default=CrunchLevel.BALANCED)

    # --- Dati flessibili: ciò che varia da genere a genere ---
    # Attributi della campagna: lista di {"name", "description"}.
    # Es. fantasy → Forza/Magia; cyberpunk → Hacking/Strada/Sangue freddo.
    attributes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # Tipi di conflitto tipici (es. "combattimento", "indagine", "seduzione").
    conflict_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Risorse tracciate sui personaggi (es. {"hp": 10, "mana": 5}).
    default_resources: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Regole speciali in linguaggio naturale, passate al narratore.
    special_rules: Mapped[str] = mapped_column(Text, default="")

    # --- Regole meccaniche del motore di risoluzione ---
    # Formula del dado base (es. "2d6", "1d20"): un noir può usare dadi "calmi".
    dice_formula: Mapped[str] = mapped_column(String(20), default="2d6")
    # Ampiezza della fascia "riesci, ma…" sotto la soglia di difficoltà.
    success_band: Mapped[int] = mapped_column(Integer, default=2)

    # True = preset riutilizzabile; False = blueprint di una campagna specifica.
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)

    campaigns: Mapped[list["Campaign"]] = relationship(  # noqa: F821
        back_populates="blueprint"
    )

    def __repr__(self) -> str:  # pragma: no cover
        kind = "template" if self.is_template else "campaign"
        return f"<Blueprint {self.name!r} ({self.genre!r}, {kind})>"
