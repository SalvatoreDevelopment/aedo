"""Interpretazione tollerante degli output JSON del modello.

I modelli a volte avvolgono il JSON in ```fence``` o aggiungono testo: qui lo
estraiamo e lo convertiamo nelle dataclass del narratore, con default sicuri.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .base import Assessment, Narration, StateChanges

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> dict[str, Any]:
    """Estrae il primo oggetto JSON da una risposta del modello."""
    if not text:
        raise ValueError("Risposta vuota dal modello")

    candidates: list[str] = []
    fenced = _FENCE_RE.search(text)
    if fenced:
        candidates.append(fenced.group(1))
    # Dal primo '{' all'ultimo '}' come fallback.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(text[start : end + 1])
    candidates.append(text)

    for cand in candidates:
        try:
            data = json.loads(cand)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    raise ValueError(f"Nessun JSON valido nella risposta: {text[:200]!r}")


def parse_assessment(text: str) -> Assessment:
    return _assessment_from_dict(extract_json(text))


def _assessment_from_dict(data: dict[str, Any]) -> Assessment:
    is_risky = bool(data.get("is_risky", False))
    return Assessment(
        is_risky=is_risky,
        attribute=(data.get("attribute") or None) if is_risky else None,
        difficulty=(data.get("difficulty") or None) if is_risky else None,
        reason=str(data.get("reason", "")),
    )


def _narration_from_dict(data: dict[str, Any]) -> Narration:
    raw = data.get("changes") or {}
    if not isinstance(raw, dict):
        raw = {}
    changes = StateChanges(
        resource_deltas=_as_int_dict(raw.get("resource_deltas")),
        conditions_add=[str(c) for c in _as_list(raw.get("conditions_add"))],
        conditions_remove=[str(c) for c in _as_list(raw.get("conditions_remove"))],
        relationship_changes=[d for d in _as_list(raw.get("relationship_changes")) if isinstance(d, dict)],
        new_items=[d for d in _as_list(raw.get("new_items")) if isinstance(d, dict)],
        removed_items=[str(s) for s in _as_list(raw.get("removed_items"))],
        new_objectives=[d for d in _as_list(raw.get("new_objectives")) if isinstance(d, dict)],
        completed_objectives=[str(s) for s in _as_list(raw.get("completed_objectives"))],
        memory=(str(raw["memory"]) if raw.get("memory") else None),
        memory_importance=float(raw.get("memory_importance", 0.5) or 0.5),
    )
    return Narration(
        text=str(data.get("narration", "")).strip(),
        new_summary=(str(data["new_summary"]) if data.get("new_summary") else None),
        changes=changes,
        title=(str(data["title"]).strip() if data.get("title") else None),
    )


def parse_turn(text: str) -> tuple[Assessment, Narration | None]:
    """Interpreta la risposta combinata: valutazione + narrazione se non rischiosa."""
    try:
        data = extract_json(text)
    except ValueError:
        # JSON irrecuperabile: trattala come azione libera con narrazione salvata.
        return Assessment(is_risky=False, reason="parsing fallito"), _salvage_narration(text)
    assessment = _assessment_from_dict(data)
    if assessment.is_risky:
        return assessment, None
    return assessment, _narration_from_dict(data)


def _as_int_dict(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, int] = {}
    for k, v in value.items():
        try:
            out[str(k)] = int(v)
        except (TypeError, ValueError):
            continue
    return out


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


_NARRATION_RE = re.compile(r'"narration"\s*:\s*"(.*?)(?:"\s*[,}]|$)', re.DOTALL)


def _salvage_narration(text: str) -> Narration:
    """Recupero "best effort" quando il JSON è malformato o troncato.

    Meglio una narrazione senza i cambiamenti di stato che un turno andato in
    errore: il gioco non deve mai bloccarsi per un output imperfetto.
    """
    match = _NARRATION_RE.search(text)
    raw = match.group(1) if match else text
    cleaned = raw.replace('\\"', '"').replace("\\n", "\n").strip()
    return Narration(text=cleaned, new_summary=None, changes=StateChanges())


def parse_narration(text: str) -> Narration:
    try:
        return _narration_from_dict(extract_json(text))
    except ValueError:
        return _salvage_narration(text)
