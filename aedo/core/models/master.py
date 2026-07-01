"""Regia del master: coda di comandi e note segrete.

Il Banco del Master è un processo separato dal bot; non può scrivere nel canale
Discord da solo. Il **ponte** è il database: il Banco accoda un
:class:`MasterCommand`, il bot (che è connesso a Discord) lo esegue nel canale e
ne aggiorna lo stato. Le :class:`MasterNote` invece non escono mai dal Banco:
sono appunti privati del master sulla campagna.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin
from .enums import CommandKind, CommandStatus


class MasterCommand(Base, IdMixin, TimestampMixin):
    __tablename__ = "master_commands"

    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    campaign: Mapped["Campaign"] = relationship(  # noqa: F821
        back_populates="master_commands"
    )

    kind: Mapped[CommandKind] = mapped_column()
    # Contenuto dell'ordine: il testo dell'evento, lo spunto da narrare, oppure
    # il nuovo esito ("success"/"success_cost"/"failure") per l'override.
    payload: Mapped[str] = mapped_column(Text, default="")

    status: Mapped[CommandStatus] = mapped_column(default=CommandStatus.PENDING)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Cosa è finito nel canale (per mostrarlo nel Banco), o il motivo dell'errore.
    result_narration: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MasterCommand {self.kind.value} [{self.status.value}]>"


class ChannelDeletion(Base, IdMixin, TimestampMixin):
    """Ordine di cancellare un canale Discord, eseguito dal bot.

    Volutamente SENZA legame con la campagna: viene creato mentre la campagna
    viene eliminata, quindi deve sopravviverle (un cascade la cancellerebbe
    insieme alla campagna prima che il bot possa agire). Tiene solo l'id del
    canale da rimuovere.
    """

    __tablename__ = "channel_deletions"

    channel_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[CommandStatus] = mapped_column(default=CommandStatus.PENDING)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ChannelDeletion {self.channel_id} [{self.status.value}]>"


class MasterNote(Base, IdMixin, TimestampMixin):
    __tablename__ = "master_notes"

    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    campaign: Mapped["Campaign"] = relationship(  # noqa: F821
        back_populates="master_notes"
    )

    # Appunto privato del master: non viene mai mostrato ai giocatori.
    text: Mapped[str] = mapped_column(Text, default="")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MasterNote {self.text[:30]!r}>"
