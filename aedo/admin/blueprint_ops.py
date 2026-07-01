"""Editor del Blueprint — le regole e il genere di una campagna, senza codice.

Il Blueprint è ciò che rende Aedo genere-agnostico: attributi, tono, dado e
regole speciali sono *dati*, non codice. Qui il master li modifica dal Banco.

Le modifiche agli attributi **non** ritoccano i personaggi già esistenti (che
tengono il proprio dizionario): un attributo nuovo comparirà a 0 finché non lo
si valorizza dal Controllo dello Stato. È una scelta prudente — cambiare le
regole non deve riscrivere di nascosto le schede.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from aedo.core.models import Blueprint, Campaign, CrunchLevel

from .state_ops import Invalid, NotFound

_DICE_RE = re.compile(r"^\s*\d+\s*d\s*\d+\s*$", re.IGNORECASE)


def get_blueprint(session: Session, campaign_id: int) -> tuple[Campaign, Blueprint]:
    camp = session.get(Campaign, campaign_id)
    if camp is None:
        raise NotFound(f"Campagna {campaign_id} inesistente.")
    return camp, camp.blueprint


def _clean_attributes(raw: list) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise Invalid("Formato attributo non valido.")
        name = str(item.get("name", "")).strip()
        if not name:
            raise Invalid("Un attributo ha il nome vuoto.")
        if name.lower() in seen:
            raise Invalid(f"Attributo duplicato: {name!r}.")
        seen.add(name.lower())
        out.append({"name": name, "description": str(item.get("description", "")).strip()})
    return out


def _clean_resources(raw: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for key, value in raw.items():
        name = str(key).strip()
        if not name:
            raise Invalid("Una risorsa ha il nome vuoto.")
        try:
            out[name] = max(0, int(value))
        except (TypeError, ValueError) as exc:
            raise Invalid(f"Valore risorsa non valido per {name!r}.") from exc
    return out


def _clean_conflicts(raw: list) -> list[str]:
    out: list[str] = []
    for item in raw:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    return out


def update_blueprint(session: Session, blueprint: Blueprint, patch: dict) -> Blueprint:
    """Applica un aggiornamento parziale al Blueprint, con validazioni."""
    if "name" in patch:
        name = str(patch["name"]).strip()
        if not name:
            raise Invalid("Il nome del ruleset è vuoto.")
        blueprint.name = name
    for field in ("genre", "tone", "narrator_persona", "special_rules"):
        if field in patch:
            setattr(blueprint, field, str(patch[field]))

    if "crunch_level" in patch:
        try:
            blueprint.crunch_level = CrunchLevel(patch["crunch_level"])
        except ValueError as exc:
            raise Invalid(f"Livello di meccaniche non valido: {patch['crunch_level']!r}.") from exc

    if "dice_formula" in patch:
        formula = str(patch["dice_formula"]).strip()
        if not _DICE_RE.match(formula):
            raise Invalid("Formula del dado non valida (usa un formato tipo 2d6 o 1d20).")
        blueprint.dice_formula = formula.lower().replace(" ", "")

    if "success_band" in patch:
        try:
            band = int(patch["success_band"])
        except (TypeError, ValueError) as exc:
            raise Invalid("La fascia di successo deve essere un numero.") from exc
        if band < 0:
            raise Invalid("La fascia di successo non può essere negativa.")
        blueprint.success_band = band

    if "attributes" in patch:
        blueprint.attributes = _clean_attributes(patch["attributes"])
    if "default_resources" in patch:
        blueprint.default_resources = _clean_resources(patch["default_resources"])
    if "conflict_types" in patch:
        blueprint.conflict_types = _clean_conflicts(patch["conflict_types"])

    session.flush()
    return blueprint
