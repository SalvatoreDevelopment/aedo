"""Memoria narrativa: indicizzazione e recupero ibrido dei ricordi.

Il recupero combina tre segnali, pensati per un RPG:
- **semantico** (cosine fra embedding): cattura il significato ("tradito" ~ "pugnalato");
- **lessicale** (parole in comune, con spinta ai nomi propri): cattura i nomi
  esatti di NPC e luoghi, che l'embedding tende a diluire;
- **entità presenti**: dà priorità ai ricordi che coinvolgono i personaggi in scena.
Il punteggio finale è pesato anche per l'importanza del ricordo.

La similarità è calcolata in Python: a volumi di una campagna è istantanea.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from aedo.core.models import Memory
from .embedder import Embedder

# Parole troppo comuni per essere informative nel match lessicale.
_STOPWORDS = {
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di", "a", "da",
    "in", "con", "su", "per", "tra", "fra", "e", "o", "ma", "che", "chi",
    "non", "mi", "ti", "ci", "vi", "si", "ho", "hai", "ha", "hanno", "del",
    "della", "dei", "delle", "al", "alla", "ai", "alle", "nel", "nella",
    "sul", "sulla", "come", "dove", "quando", "cosa", "mio", "tuo", "suo",
    "questo", "quello", "sono", "era", "essere", "fare",
}

_WORD_RE = re.compile(r"\w+")
_PROPER_RE = re.compile(r"\b([A-ZÀ-Ý]\w{2,})\b")


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _significant_words(text: str) -> set[str]:
    return {
        w for w in _WORD_RE.findall(text.lower())
        if w not in _STOPWORDS and len(w) > 2
    }


def _lexical_score(query_words: set[str], text: str) -> float:
    """Frazione di parole significative della query presenti nel ricordo."""
    if not query_words:
        return 0.0
    text_words = set(_WORD_RE.findall(text.lower()))
    hits = sum(1 for w in query_words if w in text_words)
    return hits / len(query_words)


def _proper_noun_hits(proper_nouns: list[str], text: str) -> int:
    """Quanti nomi propri della query compaiono nel ricordo (nomi = preziosi)."""
    text_words = set(_WORD_RE.findall(text.lower()))
    return sum(1 for n in proper_nouns if n.lower() in text_words)


class MemoryService:
    """Indicizza e recupera i ricordi di una campagna (RAG ibrido)."""

    def __init__(self, embedder: Embedder, *, k: int = 4, min_score: float = 0.12) -> None:
        self.embedder = embedder
        self.k = k
        self.min_score = min_score

    def index_pending(self, session: Session, campaign_id: int) -> int:
        """Calcola l'embedding dei ricordi non ancora indicizzati. Ritorna quanti."""
        pending = session.scalars(
            select(Memory).where(
                Memory.campaign_id == campaign_id, Memory.embedded.is_(False)
            )
        ).all()
        for mem in pending:
            mem.embedding = self.embedder.embed(mem.text)
            mem.embedded = True
        if pending:
            session.flush()
        return len(pending)

    def recall(
        self,
        session: Session,
        campaign_id: int,
        query_text: str,
        present_ids: list[int] | None = None,
    ) -> list[str]:
        """Ricordi più rilevanti per la situazione, con recupero ibrido.

        `present_ids`: id dei personaggi in scena, per dare priorità ai ricordi
        che li coinvolgono (utile soprattutto per le relazioni / il romance).
        """
        if not query_text.strip():
            return []
        memories = session.scalars(
            select(Memory).where(
                Memory.campaign_id == campaign_id, Memory.embedded.is_(True)
            )
        ).all()
        if not memories:
            return []

        query_vec = self.embedder.embed(query_text)
        query_words = _significant_words(query_text)
        proper_nouns = _PROPER_RE.findall(query_text)
        present = set(present_ids or [])

        scored: list[tuple[float, Memory]] = []
        for mem in memories:
            if not mem.embedding:
                continue
            sim = _cosine(query_vec, mem.embedding)
            lex = _lexical_score(query_words, mem.text)
            combined = 0.7 * sim + 0.3 * lex
            combined += 0.12 * _proper_noun_hits(proper_nouns, mem.text)
            if present and set(mem.involved_ids or []) & present:
                combined += 0.2  # un personaggio in scena è coinvolto in questo ricordo
            if combined < self.min_score:
                continue
            score = combined * (0.7 + 0.3 * mem.importance)
            scored.append((score, mem))

        scored.sort(key=lambda t: t[0], reverse=True)
        return [mem.text for _, mem in scored[: self.k]]
