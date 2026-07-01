"""Ponte fra il bot Discord (async) e il core (sync + DB).

Ogni funzione apre la PROPRIA sessione, fa il lavoro e restituisce DTO di soli
primitivi: così può essere eseguita in un thread separato (via asyncio.to_thread)
senza bloccare l'event loop di Discord né far attraversare oggetti ORM ai thread.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select

from aedo.core.memory import LocalEmbedder, MemoryService
from aedo.core.models import Campaign, Character
from aedo.core.narrator.base import NarratorProvider
from aedo.core.services.campaign_service import (
    create_campaign_from_template,
    create_player_character,
)
from aedo.core.services import regia
from aedo.core.services.game_service import play_turn, start_campaign
from aedo.core.services.regia import RegiaJob, run_pending
from aedo.storage import SessionLocal

# Servizio di memoria condiviso (embedder locale, caricato pigramente al
# primo ricordo). Sostituibile nei test con un embedder finto.
_memory_service: MemoryService | None = None


def _get_memory() -> MemoryService:
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService(LocalEmbedder())
    return _memory_service


# --- DTO (dati semplici, sicuri fra thread) -------------------------------

@dataclass
class NewCampaignDTO:
    campaign_name: str
    character_name: str
    genre: str
    attributes: dict[str, int]
    resources: dict[str, int]
    opening: str


@dataclass
class TurnDTO:
    narration: str
    roll_summary: str | None = None
    outcome: str | None = None
    genre: str = ""


@dataclass
class SheetDTO:
    name: str
    genre: str
    attributes: dict[str, int]
    resources: dict[str, int]
    conditions: list[str] = field(default_factory=list)


# --- Operazioni ------------------------------------------------------------

def _default_attributes(blueprint) -> dict[str, int]:
    names = [a["name"] for a in blueprint.attributes]
    attrs = {n: 2 for n in names}
    if names:
        attrs[names[0]] = 3
    return attrs


def create_campaign_in_channel(
    narrator: NarratorProvider,
    *,
    channel_id: str,
    guild_id: str,
    owner_discord_id: str,
    template: str,
    campaign_name: str,
    character_name: str,
    premise: str = "",
) -> NewCampaignDTO:
    """Crea campagna + personaggio nel canale e genera la scena d'apertura."""
    with SessionLocal() as session:
        campaign = create_campaign_from_template(
            session, template_name=template, campaign_name=campaign_name,
            owner_discord_id=owner_discord_id,
        )
        campaign.discord_channel_id = channel_id
        campaign.discord_guild_id = guild_id
        pc = create_player_character(
            session, campaign, name=character_name, discord_id=owner_discord_id,
            attributes=_default_attributes(campaign.blueprint),
        )
        opening = start_campaign(
            session, campaign, pc, narrator, premise=premise, memory=_get_memory()
        )
        dto = NewCampaignDTO(
            campaign_name=campaign.name, character_name=pc.name,
            genre=campaign.blueprint.genre, attributes=dict(pc.attributes),
            resources=dict(pc.resources), opening=opening,
        )
        session.commit()
        return dto


def _campaign_in_channel(session, channel_id: str) -> Campaign | None:
    return session.scalar(
        select(Campaign).where(Campaign.discord_channel_id == channel_id)
    )


def is_campaign_channel(channel_id: str) -> bool:
    """Check rapido: il canale ospita una campagna? (per evitare AI inutili)."""
    with SessionLocal() as session:
        return _campaign_in_channel(session, channel_id) is not None


def _player_in_campaign(session, campaign: Campaign, discord_id: str) -> Character | None:
    pc = session.scalar(
        select(Character).where(
            Character.campaign_id == campaign.id,
            Character.discord_id == discord_id,
        )
    )
    if pc:
        return pc
    # Fallback single player: il primo PG della campagna.
    return session.scalar(
        select(Character).where(
            Character.campaign_id == campaign.id, Character.is_player.is_(True)
        )
    )


def run_player_turn(
    narrator: NarratorProvider, *, channel_id: str, discord_id: str, action: str
) -> TurnDTO | None:
    """Esegue un turno per il canale. None se il canale non ospita una campagna."""
    with SessionLocal() as session:
        campaign = _campaign_in_channel(session, channel_id)
        if campaign is None:
            return None
        pc = _player_in_campaign(session, campaign, discord_id)
        if pc is None:
            return None
        result = play_turn(session, campaign, pc, action, narrator, memory=_get_memory())
        dto = TurnDTO(
            narration=result.narration,
            roll_summary=result.resolution.summary if result.resolution else None,
            outcome=result.resolution.outcome.value if result.resolution else None,
            genre=campaign.blueprint.genre,
        )
        session.commit()
        return dto


def get_sheet(channel_id: str) -> SheetDTO | None:
    with SessionLocal() as session:
        campaign = _campaign_in_channel(session, channel_id)
        if campaign is None:
            return None
        pc = session.scalar(
            select(Character).where(
                Character.campaign_id == campaign.id, Character.is_player.is_(True)
            )
        )
        if pc is None:
            return None
        return SheetDTO(
            name=pc.name, genre=campaign.blueprint.genre,
            attributes=dict(pc.attributes), resources=dict(pc.resources),
            conditions=list(pc.conditions),
        )


def get_inventory(channel_id: str) -> list[dict] | None:
    with SessionLocal() as session:
        campaign = _campaign_in_channel(session, channel_id)
        if campaign is None:
            return None
        pc = session.scalar(
            select(Character).where(
                Character.campaign_id == campaign.id, Character.is_player.is_(True)
            )
        )
        if pc is None:
            return None
        return [
            {"name": it.name, "quantity": it.quantity, "description": it.description}
            for it in pc.items
        ]


def take_regia_jobs(narrator: NarratorProvider) -> list[RegiaJob]:
    """Esegue i comandi di regia in coda e restituisce cosa postare nei canali.

    Chiamata periodicamente dal bot (in un thread): fa il lavoro sul DB — incluse
    le eventuali chiamate al narratore — e torna DTO di soli primitivi, così il
    bot deve solo inviare gli embed.
    """
    with SessionLocal() as session:
        jobs = run_pending(session, narrator)
        session.commit()
        return jobs


def take_channel_deletions() -> list[dict]:
    """Canali da cancellare (accodati dal Banco quando elimina una campagna)."""
    with SessionLocal() as session:
        dels = regia.pending_channel_deletions(session)
        result = [{"id": d.id, "channel_id": d.channel_id} for d in dels]
        session.commit()
        return result


def complete_channel_deletion(deletion_id: int, error: str | None = None) -> None:
    with SessionLocal() as session:
        regia.mark_channel_deletion(session, deletion_id, error)
        session.commit()


def get_objectives(channel_id: str) -> list[dict] | None:
    with SessionLocal() as session:
        campaign = _campaign_in_channel(session, channel_id)
        if campaign is None:
            return None
        return [
            {"title": o.title, "status": o.status.value, "description": o.description}
            for o in campaign.objectives
        ]
