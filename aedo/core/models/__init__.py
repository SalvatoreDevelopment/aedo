"""Modelli dati di Aedo — la spina dorsale dello stato di una campagna.

Importare i modelli da qui garantisce che tutte le tabelle siano registrate
sulla stessa `Base` prima di creare lo schema.
"""

from __future__ import annotations

from .base import Base, utcnow
from .blueprint import Blueprint
from .campaign import Campaign
from .character import Character
from .enums import (
    CampaignMode,
    CampaignStatus,
    CommandKind,
    CommandStatus,
    CrunchLevel,
    ObjectiveStatus,
    Outcome,
)
from .event import EventLog
from .item import Item
from .master import ChannelDeletion, MasterCommand, MasterNote
from .memory import Memory
from .objective import Objective
from .relationship import Relationship

__all__ = [
    "Base",
    "utcnow",
    "Blueprint",
    "Campaign",
    "Character",
    "Item",
    "Relationship",
    "Objective",
    "Memory",
    "EventLog",
    "MasterCommand",
    "MasterNote",
    "ChannelDeletion",
    "CampaignMode",
    "CampaignStatus",
    "CommandKind",
    "CommandStatus",
    "CrunchLevel",
    "ObjectiveStatus",
    "Outcome",
]
