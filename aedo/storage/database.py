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
def _enable_sqlite_fk(dbapi_connection, _record) -> None:
    """SQLite non applica le foreign key di default: attiviamole."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
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
