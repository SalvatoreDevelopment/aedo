"""Narratore reale via OpenRouter (API OpenAI-compatibile).

Usa il client `openai` puntato a OpenRouter. Il modello è configurabile, così
si può cambiare DM senza toccare il codice (DeepSeek, MiniMax, ...).
"""

from __future__ import annotations

import logging

from openai import OpenAI

from aedo.config import settings
from aedo.core.resolution import ResolutionResult
from .base import Assessment, Narration, NarratorContext, NarratorProvider
from .parsing import parse_assessment, parse_narration, parse_turn
from .prompts import (
    build_assess_messages,
    build_narrate_messages,
    build_opening_messages,
    build_turn_messages,
)

logger = logging.getLogger("aedo.narrator.openrouter")


class OpenRouterNarrator(NarratorProvider):
    name = "openrouter"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        key = api_key or settings.openrouter_api_key
        if not key:
            raise ValueError(
                "Manca la chiave OpenRouter: imposta OPENROUTER_API_KEY nel file .env"
            )
        self.model = model or settings.aedo_model
        self._client = OpenAI(
            api_key=key,
            base_url=base_url or settings.openrouter_base_url,
            default_headers={
                "HTTP-Referer": "https://github.com/aedo-rpg",
                "X-Title": "Aedo",
            },
        )

    def _complete(self, messages: list[dict[str, str]], *, max_tokens: int) -> str:
        """Una completion, con response_format JSON e fallback se non supportato.

        Il reasoning è disattivato: per narrare/valutare non serve, e dimezza
        latenza e token (misurato: ~25s → ~9s per chiamata).
        """
        kwargs = dict(
            model=self.model, messages=messages, max_tokens=max_tokens,
            temperature=0.8, extra_body={"reasoning": {"enabled": False}},
        )
        try:
            resp = self._client.chat.completions.create(
                response_format={"type": "json_object"}, **kwargs
            )
        except Exception as exc:  # il modello potrebbe non supportare response_format
            logger.info("response_format non supportato (%s); riprovo senza", exc)
            resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    # max_tokens è solo un tetto di sicurezza (paghi i token davvero generati):
    # tenerlo alto evita JSON troncati su narrazioni + cambiamenti corposi.
    def open_scene(self, ctx: NarratorContext, premise: str = "") -> Narration:
        text = self._complete(build_opening_messages(ctx, premise), max_tokens=1500)
        return parse_narration(text)

    def turn(self, ctx: NarratorContext):
        """Una sola chiamata: valuta e, se non rischiosa, narra subito."""
        text = self._complete(build_turn_messages(ctx), max_tokens=1500)
        return parse_turn(text)

    def assess(self, ctx: NarratorContext) -> Assessment:
        # Senza reasoning bastano pochi token: è solo una decisione strutturata.
        text = self._complete(build_assess_messages(ctx), max_tokens=300)
        return parse_assessment(text)

    def narrate(
        self, ctx: NarratorContext, resolution: ResolutionResult | None
    ) -> Narration:
        outcome = resolution.outcome.value if resolution else None
        text = self._complete(build_narrate_messages(ctx, outcome), max_tokens=1500)
        return parse_narration(text)
