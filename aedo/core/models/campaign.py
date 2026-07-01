"""Campaign — una partita in corso.

Aggrega tutto lo stato: personaggi, oggetti, relazioni, obiettivi, ricordi
ed eventi. Fa riferimento a un Blueprint che ne definisce le regole.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin
from .enums import CampaignMode, CampaignStatus


class Campaign(Base, IdMixin, TimestampMixin):
    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(String(120))
    mode: Mapped[CampaignMode] = mapped_column(default=CampaignMode.SINGLE)
    status: Mapped[CampaignStatus] = mapped_column(default=CampaignStatus.ACTIVE)

    # Discord id del proprietario / master della campagna.
    owner_discord_id: Mapped[str] = mapped_column(String(64), default="")
    # Canale testuale dedicato alla campagna (ogni campagna vive nel suo canale).
    discord_channel_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    discord_guild_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Sintesi corrente della situazione (aggiornata dal narratore): la "scena".
    current_summary: Mapped[str] = mapped_column(Text, default="")

    blueprint_id: Mapped[int] = mapped_column(ForeignKey("blueprints.id"))
    blueprint: Mapped["Blueprint"] = relationship(  # noqa: F821
        back_populates="campaigns"
    )

    # Collezioni figlie: cancellate insieme alla campagna.
    characters: Mapped[list["Character"]] = relationship(  # noqa: F821
        back_populates="campaign", cascade="all, delete-orphan"
    )
    items: Mapped[list["Item"]] = relationship(  # noqa: F821
        back_populates="campaign", cascade="all, delete-orphan"
    )
    relationships: Mapped[list["Relationship"]] = relationship(  # noqa: F821
        back_populates="campaign", cascade="all, delete-orphan"
    )
    objectives: Mapped[list["Objective"]] = relationship(  # noqa: F821
        back_populates="campaign", cascade="all, delete-orphan"
    )
    memories: Mapped[list["Memory"]] = relationship(  # noqa: F821
        back_populates="campaign", cascade="all, delete-orphan"
    )
    events: Mapped[list["EventLog"]] = relationship(  # noqa: F821
        back_populates="campaign", cascade="all, delete-orphan"
    )
    master_commands: Mapped[list["MasterCommand"]] = relationship(  # noqa: F821
        back_populates="campaign", cascade="all, delete-orphan"
    )
    master_notes: Mapped[list["MasterNote"]] = relationship(  # noqa: F821
        back_populates="campaign", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Campaign {self.name!r} ({self.mode.value})>"
