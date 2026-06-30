"""Calcolo degli embedding testuali.

Due implementazioni dietro un protocollo comune:
- `LocalEmbedder`: modello `sentence-transformers` in locale (gratis, offline).
  Caricato in modo pigro (il modello è pesante: si paga solo al primo uso).
- `FakeEmbedder`: deterministico, senza dipendenze pesanti, per i test. Usa
  l'hashing delle parole, così testi che condividono parole risultano simili
  (abbastanza per verificare la logica di recupero).
"""

from __future__ import annotations

import hashlib
import re
from typing import Protocol

from aedo.config import settings


class Embedder(Protocol):
    """Trasforma testo in un vettore."""

    def embed(self, text: str) -> list[float]: ...


class LocalEmbedder:
    """Embedding tramite sentence-transformers (caricamento pigro)."""

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or settings.aedo_embedding_model
        self._model = None  # caricato al primo uso

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed(self, text: str) -> list[float]:
        model = self._ensure_model()
        vector = model.encode(text, normalize_embeddings=True)
        return [float(x) for x in vector]


class FakeEmbedder:
    """Embedder lessicale deterministico per i test (hashing trick)."""

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for word in re.findall(r"\w+", text.lower()):
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        # Normalizza (vettori unitari → il prodotto scalare è la cosine).
        norm = sum(x * x for x in vec) ** 0.5
        if norm:
            vec = [x / norm for x in vec]
        return vec
