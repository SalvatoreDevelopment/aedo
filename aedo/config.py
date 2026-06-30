"""Configurazione centrale di Aedo.

Legge i valori da variabili d'ambiente / file `.env` (vedi `.env.example`).
Un'unica istanza `settings` viene importata dal resto del codice.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Narratore AI (OpenRouter) ---
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    aedo_model: str = "deepseek/deepseek-v4-flash"

    # --- Bot Discord ---
    discord_token: str = ""

    # --- Database ---
    aedo_db_path: str = "data/aedo.db"

    # --- Memoria narrativa ---
    aedo_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    @property
    def db_url(self) -> str:
        """URL SQLAlchemy per il database SQLite."""
        path = Path(self.aedo_db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"


settings = Settings()
