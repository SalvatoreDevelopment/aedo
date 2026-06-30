"""Persistenza: engine, sessioni e inizializzazione dello schema."""

from __future__ import annotations

from .database import SessionLocal, engine, init_db, session_scope

__all__ = ["engine", "SessionLocal", "init_db", "session_scope"]
