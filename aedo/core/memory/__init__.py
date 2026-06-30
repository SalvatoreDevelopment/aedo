"""Memoria narrativa: embedding locali e recupero per similarità."""

from __future__ import annotations

from .embedder import Embedder, FakeEmbedder, LocalEmbedder
from .store import MemoryService

__all__ = ["Embedder", "LocalEmbedder", "FakeEmbedder", "MemoryService"]
