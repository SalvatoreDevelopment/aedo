"""Operazioni di scrittura sullo stato di una campagna — i poteri del master.

Sono le stesse regole che l'``state_apply`` applica ai cambiamenti proposti dal
narratore, ma qui l'origine è il master che agisce a mano dal Banco: correggere
risorse, dare/togliere oggetti, aggiustare un'affinità, aprire o chiudere una
quest, creare o ritoccare un NPC.

Ogni funzione riceve una ``Session`` e fa ``flush`` ma **non** committa: la
transazione è gestita dall'endpoint (commit a richiesta riuscita, rollback in
caso di errore). Le funzioni sollevano:

* :class:`NotFound`  → entità inesistente        (l'API risponde 404)
* :class:`Invalid`   → input non valido/incoerente (l'API risponde 400)

Tenere qui la logica, separata dagli endpoint HTTP, la rende testabile senza
rete e riusabile (domani anche da un comando Discord del master).
"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from aedo.core.models import (
    Blueprint,
    Campaign,
    ChannelDeletion,
    Character,
    Item,
    Objective,
    ObjectiveStatus,
    Relationship,
)

AFFINITY_MIN = -100
AFFINITY_MAX = 100


class NotFound(LookupError):
    """L'entità richiesta non esiste."""


class Invalid(ValueError):
    """L'input è incoerente o non ammesso."""


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


# --- lookup ---------------------------------------------------------------
def get_campaign(session: Session, campaign_id: int) -> Campaign:
    camp = session.get(Campaign, campaign_id)
    if camp is None:
        raise NotFound(f"Campagna {campaign_id} inesistente.")
    return camp


def get_character(session: Session, campaign_id: int, character_id: int) -> Character:
    ch = session.get(Character, character_id)
    if ch is None or ch.campaign_id != campaign_id:
        raise NotFound(f"Personaggio {character_id} inesistente in questa campagna.")
    return ch


def _owned_item(session: Session, campaign_id: int, item_id: int) -> Item:
    it = session.get(Item, item_id)
    if it is None or it.campaign_id != campaign_id:
        raise NotFound(f"Oggetto {item_id} inesistente in questa campagna.")
    return it


def _owned_relationship(session: Session, campaign_id: int, rel_id: int) -> Relationship:
    rel = session.get(Relationship, rel_id)
    if rel is None or rel.campaign_id != campaign_id:
        raise NotFound(f"Relazione {rel_id} inesistente in questa campagna.")
    return rel


def _owned_objective(session: Session, campaign_id: int, obj_id: int) -> Objective:
    obj = session.get(Objective, obj_id)
    if obj is None or obj.campaign_id != campaign_id:
        raise NotFound(f"Obiettivo {obj_id} inesistente in questa campagna.")
    return obj


# --- risorse / condizioni -------------------------------------------------
def set_resource(session: Session, character: Character, name: str, value: int) -> Character:
    """Imposta (o crea) una risorsa a un valore preciso, mai sotto zero."""
    name = name.strip()
    if not name:
        raise Invalid("Nome risorsa vuoto.")
    resources = dict(character.resources)
    resources[name] = max(0, int(value))
    character.resources = resources
    session.flush()
    return character


def adjust_resource(session: Session, character: Character, name: str, delta: int) -> Character:
    """Somma un delta a una risorsa (parte da 0 se nuova); non scende sotto zero."""
    name = name.strip()
    if not name:
        raise Invalid("Nome risorsa vuoto.")
    resources = dict(character.resources)
    resources[name] = max(0, int(resources.get(name, 0)) + int(delta))
    character.resources = resources
    session.flush()
    return character


def remove_resource(session: Session, character: Character, name: str) -> Character:
    """Elimina del tutto una risorsa dalla scheda."""
    resources = dict(character.resources)
    resources.pop(name, None)
    character.resources = resources
    session.flush()
    return character


def add_condition(session: Session, character: Character, condition: str) -> Character:
    condition = condition.strip()
    if not condition:
        raise Invalid("Condizione vuota.")
    conditions = list(character.conditions)
    if condition not in conditions:
        conditions.append(condition)
    character.conditions = conditions
    session.flush()
    return character


def remove_condition(session: Session, character: Character, condition: str) -> Character:
    conditions = [c for c in character.conditions if c != condition]
    character.conditions = conditions
    session.flush()
    return character


# --- inventario -----------------------------------------------------------
def grant_item(
    session: Session,
    campaign: Campaign,
    owner: Character,
    *,
    name: str,
    quantity: int = 1,
    description: str = "",
) -> Item:
    """Dà un oggetto a un personaggio. Se ne possiede già uno con lo stesso
    nome, ne aumenta la quantità (evita doppioni)."""
    name = name.strip()
    if not name:
        raise Invalid("Nome oggetto vuoto.")
    quantity = int(quantity)
    if quantity < 1:
        raise Invalid("La quantità deve essere almeno 1.")
    existing = session.scalar(
        select(Item).where(Item.owner_id == owner.id, Item.name == name)
    )
    if existing is not None:
        existing.quantity += quantity
        if description:
            existing.description = description
        session.flush()
        return existing
    item = Item(
        campaign=campaign, owner=owner, name=name,
        quantity=quantity, description=description,
    )
    session.add(item)
    session.flush()
    return item


def set_item_quantity(session: Session, campaign_id: int, item_id: int, quantity: int) -> Item | None:
    """Imposta la quantità di un oggetto. Se ≤ 0, l'oggetto viene rimosso."""
    item = _owned_item(session, campaign_id, item_id)
    quantity = int(quantity)
    if quantity <= 0:
        session.delete(item)
        session.flush()
        return None
    item.quantity = quantity
    session.flush()
    return item


def remove_item(session: Session, campaign_id: int, item_id: int) -> None:
    """Toglie del tutto un oggetto."""
    item = _owned_item(session, campaign_id, item_id)
    session.delete(item)
    session.flush()


# --- relazioni ------------------------------------------------------------
def create_relationship(
    session: Session,
    campaign: Campaign,
    *,
    from_id: int,
    to_id: int,
    kind: str = "conoscente",
    affinity: int = 0,
) -> Relationship:
    """Crea un legame direzionale fra due personaggi della campagna."""
    if from_id == to_id:
        raise Invalid("Un personaggio non può avere una relazione con sé stesso.")
    frm = get_character(session, campaign.id, from_id)
    to = get_character(session, campaign.id, to_id)
    existing = session.scalar(
        select(Relationship).where(
            Relationship.campaign_id == campaign.id,
            Relationship.from_id == frm.id,
            Relationship.to_id == to.id,
        )
    )
    if existing is not None:
        raise Invalid("Esiste già un legame fra questi due personaggi in questa direzione.")
    rel = Relationship(
        campaign=campaign, from_id=frm.id, to_id=to.id,
        kind=(kind.strip() or "conoscente"),
        affinity=_clamp(int(affinity), AFFINITY_MIN, AFFINITY_MAX),
    )
    session.add(rel)
    session.flush()
    return rel


def update_relationship(
    session: Session,
    campaign_id: int,
    rel_id: int,
    *,
    kind: str | None = None,
    affinity: int | None = None,
    affinity_delta: int | None = None,
    notes: str | None = None,
) -> Relationship:
    """Ritocca un legame: tipo, affinità assoluta o a delta, note."""
    rel = _owned_relationship(session, campaign_id, rel_id)
    if kind is not None:
        rel.kind = kind.strip() or rel.kind
    if affinity is not None:
        rel.affinity = _clamp(int(affinity), AFFINITY_MIN, AFFINITY_MAX)
    if affinity_delta is not None:
        rel.affinity = _clamp(rel.affinity + int(affinity_delta), AFFINITY_MIN, AFFINITY_MAX)
    if notes is not None:
        rel.notes = notes
    session.flush()
    return rel


def delete_relationship(session: Session, campaign_id: int, rel_id: int) -> None:
    rel = _owned_relationship(session, campaign_id, rel_id)
    session.delete(rel)
    session.flush()


# --- obiettivi / quest ----------------------------------------------------
def create_objective(
    session: Session, campaign: Campaign, *, title: str, description: str = ""
) -> Objective:
    title = title.strip()
    if not title:
        raise Invalid("Titolo obiettivo vuoto.")
    obj = Objective(campaign=campaign, title=title, description=description)
    session.add(obj)
    session.flush()
    return obj


def set_objective_status(
    session: Session, campaign_id: int, obj_id: int, status: str
) -> Objective:
    obj = _owned_objective(session, campaign_id, obj_id)
    try:
        obj.status = ObjectiveStatus(status)
    except ValueError as exc:
        raise Invalid(f"Stato obiettivo non valido: {status!r}.") from exc
    session.flush()
    return obj


def update_objective(
    session: Session,
    campaign_id: int,
    obj_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
) -> Objective:
    obj = _owned_objective(session, campaign_id, obj_id)
    if title is not None:
        title = title.strip()
        if not title:
            raise Invalid("Titolo obiettivo vuoto.")
        obj.title = title
    if description is not None:
        obj.description = description
    session.flush()
    return obj


def delete_objective(session: Session, campaign_id: int, obj_id: int) -> None:
    obj = _owned_objective(session, campaign_id, obj_id)
    session.delete(obj)
    session.flush()


# --- NPC / personaggi -----------------------------------------------------
def create_npc(
    session: Session,
    campaign: Campaign,
    *,
    name: str,
    description: str = "",
    attributes: dict[str, int] | None = None,
    resources: dict[str, int] | None = None,
) -> Character:
    """Crea un NPC. Gli attributi non indicati partono da quelli del Blueprint a 0."""
    name = name.strip()
    if not name:
        raise Invalid("Nome NPC vuoto.")
    bp_attr_names = [a["name"] for a in campaign.blueprint.attributes]
    provided = attributes or {}
    resolved_attrs = {n: int(provided.get(n, 0)) for n in bp_attr_names}
    # Un attributo fuori dal blueprint è comunque ammesso (potere del master).
    for extra, val in provided.items():
        if extra not in resolved_attrs:
            resolved_attrs[extra] = int(val)
    npc = Character(
        campaign=campaign,
        name=name,
        is_player=False,
        description=description,
        attributes=resolved_attrs,
        resources={k: int(v) for k, v in (resources or {}).items()},
    )
    session.add(npc)
    session.flush()
    return npc


def update_character(
    session: Session,
    campaign_id: int,
    character_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
    attributes: dict[str, int] | None = None,
) -> Character:
    """Modifica nome, descrizione o attributi di un personaggio (PG o NPC)."""
    ch = get_character(session, campaign_id, character_id)
    if name is not None:
        name = name.strip()
        if not name:
            raise Invalid("Nome vuoto.")
        ch.name = name
    if description is not None:
        ch.description = description
    if attributes is not None:
        merged = dict(ch.attributes)
        for k, v in attributes.items():
            merged[k] = int(v)
        ch.attributes = merged
    session.flush()
    return ch


def delete_campaign(session: Session, campaign_id: int) -> str | None:
    """Elimina una campagna e tutto ciò che le appartiene.

    Le collezioni figlie (personaggi, oggetti, relazioni, obiettivi, ricordi,
    eventi, comandi e note di regia) spariscono a cascata. Il Blueprint viene
    rimosso se era di questa sola campagna e non è un template riutilizzabile.
    Se la campagna aveva un canale Discord, accoda la sua cancellazione (che il
    bot eseguirà): restituisce l'id del canale, o ``None`` se non ce n'era.
    """
    camp = session.get(Campaign, campaign_id)
    if camp is None:
        raise NotFound(f"Campagna {campaign_id} inesistente.")
    channel_id = camp.discord_channel_id
    blueprint = camp.blueprint

    if channel_id:
        # Coda separata: deve sopravvivere alla cancellazione della campagna.
        session.add(ChannelDeletion(channel_id=channel_id))

    session.delete(camp)
    session.flush()

    if blueprint is not None and not blueprint.is_template:
        others = session.scalar(
            select(func.count()).select_from(Campaign).where(
                Campaign.blueprint_id == blueprint.id
            )
        )
        if not others:
            session.delete(blueprint)
            session.flush()

    return channel_id


def delete_character(session: Session, campaign_id: int, character_id: int) -> None:
    """Elimina un NPC. Il personaggio giocante non è eliminabile dal Banco.

    Prima rimuove i legami che lo coinvolgono (in entrambe le direzioni): non
    sono figli del Character ma della Campagna, quindi non verrebbero cancellati
    a cascata — e resterebbero a puntare a un personaggio inesistente (con le FK
    attive, il delete fallirebbe del tutto). Gli oggetti posseduti, invece, sono
    già a cascata via ``Character.items``.
    """
    ch = get_character(session, campaign_id, character_id)
    if ch.is_player:
        raise Invalid("Il personaggio giocante non può essere eliminato dal Banco.")
    orphan_rels = session.scalars(
        select(Relationship).where(
            Relationship.campaign_id == campaign_id,
            or_(Relationship.from_id == ch.id, Relationship.to_id == ch.id),
        )
    ).all()
    for rel in orphan_rels:
        session.delete(rel)
    session.flush()
    session.delete(ch)
    session.flush()
