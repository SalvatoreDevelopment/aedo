"""Schemi Pydantic del Banco del Master.

A differenza dell'API giocatore (sola lettura, nasconde gli NPC e gli id
interni), qui il master vede *tutto* — id compresi, perché ogni azione di
scrittura lavora per id — e ci sono i modelli di **richiesta** per le modifiche.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# === Lettura (viste ricche per il master) =================================
class ServiceStatus(BaseModel):
    key: str
    label: str
    description: str
    url: str | None = None
    state: str
    pid: int | None = None
    started_at: str | None = None
    exit_code: int | None = None
    unavailable_hint: str = ""


class CommandResult(BaseModel):
    key: str
    state: str
    message: str


class CampaignRef(BaseModel):
    id: int
    name: str
    genre: str
    status: str


class CharacterAdmin(BaseModel):
    id: int
    name: str
    is_player: bool
    description: str
    attributes: dict[str, int]
    resources: dict[str, int]
    conditions: list[str]


class ItemAdmin(BaseModel):
    id: int
    owner_id: int | None
    name: str
    description: str
    quantity: int


class RelationshipAdmin(BaseModel):
    id: int
    from_id: int
    to_id: int
    from_name: str
    to_name: str
    kind: str
    affinity: int
    notes: str


class ObjectiveAdmin(BaseModel):
    id: int
    title: str
    description: str
    status: str


class AttributeDef(BaseModel):
    name: str
    description: str = ""


class CampaignStateAdmin(BaseModel):
    """Tutto lo stato modificabile di una campagna, in un colpo solo."""

    id: int
    name: str
    genre: str
    tone: str
    status: str
    crunch_level: str
    summary: str
    attributes: list[AttributeDef]
    characters: list[CharacterAdmin]
    items: list[ItemAdmin]
    relationships: list[RelationshipAdmin]
    objectives: list[ObjectiveAdmin]


# === Scrittura (richieste) ================================================
class ResourceSet(BaseModel):
    name: str
    value: int = Field(ge=0)


class ResourceAdjust(BaseModel):
    name: str
    delta: int


class ConditionReq(BaseModel):
    condition: str


class ItemGrant(BaseModel):
    owner_id: int
    name: str
    quantity: int = Field(default=1, ge=1)
    description: str = ""


class ItemQuantity(BaseModel):
    quantity: int


class RelationshipCreate(BaseModel):
    from_id: int
    to_id: int
    kind: str = "conoscente"
    affinity: int = 0


class RelationshipUpdate(BaseModel):
    kind: str | None = None
    affinity: int | None = None
    affinity_delta: int | None = None
    notes: str | None = None


class ObjectiveCreate(BaseModel):
    title: str
    description: str = ""


class ObjectiveStatusReq(BaseModel):
    status: str  # open | completed | failed


class ObjectiveUpdate(BaseModel):
    title: str | None = None
    description: str | None = None


class NpcCreate(BaseModel):
    name: str
    description: str = ""
    attributes: dict[str, int] = Field(default_factory=dict)
    resources: dict[str, int] = Field(default_factory=dict)


class CharacterUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    attributes: dict[str, int] | None = None


# === Regia narrativa ======================================================
class RegiaEventReq(BaseModel):
    mode: str = "narrated"  # "direct" (testo così com'è) | "narrated" (lo narra Aedo)
    text: str


class RegiaOverrideReq(BaseModel):
    outcome: str  # success | success_cost | failure


class NoteReq(BaseModel):
    text: str


class NoteOut(BaseModel):
    id: int
    text: str
    created_at: datetime


class CommandOut(BaseModel):
    id: int
    kind: str
    status: str
    payload: str
    result_narration: str
    error: str
    created_at: datetime
    processed_at: datetime | None


class LastEventOut(BaseModel):
    id: int
    action_text: str
    outcome: str | None


class RegiaState(BaseModel):
    """Tutto ciò che serve al pannello di regia in una risposta."""

    campaign_id: int
    has_channel: bool
    last_event: LastEventOut | None
    commands: list[CommandOut]
    notes: list[NoteOut]


# === Editor regole / genere (Blueprint) ===================================
class BlueprintOut(BaseModel):
    name: str
    genre: str
    tone: str
    narrator_persona: str
    crunch_level: str
    crunch_options: list[str]
    attributes: list[AttributeDef]
    conflict_types: list[str]
    default_resources: dict[str, int]
    special_rules: str
    dice_formula: str
    success_band: int
    ai_model: str  # modello AI in uso (informativo)


class BlueprintUpdate(BaseModel):
    name: str | None = None
    genre: str | None = None
    tone: str | None = None
    narrator_persona: str | None = None
    crunch_level: str | None = None
    attributes: list[AttributeDef] | None = None
    conflict_types: list[str] | None = None
    default_resources: dict[str, int] | None = None
    special_rules: str | None = None
    dice_formula: str | None = None
    success_band: int | None = None


# === Strumenti e statistiche ==============================================
class OracleReq(BaseModel):
    question: str
    likelihood: str = "even"  # unlikely | even | likely


class OracleOut(BaseModel):
    question: str
    likelihood: str
    answer: str
    grade: str


class GenerateReq(BaseModel):
    kind: str  # names | npc | hook


class NpcSuggestion(BaseModel):
    name: str
    role: str
    trait: str


class GenerateOut(BaseModel):
    kind: str
    genre: str
    items: list[str]
    npc: NpcSuggestion | None = None


class RelStat(BaseModel):
    name: str
    kind: str
    affinity: int


class StatsOut(BaseModel):
    turns: int
    events_total: int
    outcomes: dict[str, int]
    npc_count: int
    memory_count: int
    objectives: dict[str, int]
    relationships: list[RelStat]
