"""Layer di accesso al database (SQLAlchemy + SQLite).

Espone l'engine, una factory di sessioni e `init_db()` per creare lo schema.
SQLite ora, ma usando SQLAlchemy il passaggio a PostgreSQL è una sola riga.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from aedo.config import settings
from aedo.core.models import Base

engine: Engine = create_engine(
    settings.db_url,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


@event.listens_for(engine, "connect")
def _tune_sqlite(dbapi_connection, _record) -> None:
    """Impostazioni per-connessione di SQLite.

    * ``foreign_keys=ON`` — SQLite non applica le FK di default.
    * ``journal_mode=WAL`` — ora due processi scrivono sullo stesso db (il bot
      che gioca e il Banco del Master che corregge lo stato): il WAL consente
      letture concorrenti mentre uno scrive, senza bloccare tutto.
    * ``busy_timeout`` — se il db è momentaneamente occupato, aspetta invece di
      fallire subito con "database is locked".
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def init_db() -> None:
    """Crea tutte le tabelle se non esistono."""
    Base.metadata.create_all(engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Sessione transazionale: commit se ok, rollback se eccezione."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
