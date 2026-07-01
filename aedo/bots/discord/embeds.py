"""Embed Discord per le schede di consultazione (scheda, inventario, obiettivi).

Solo presentazione di *dati*: qui gli embed hanno senso, perché sono tabelle.
Quando invece Aedo **racconta** (apertura, turni, regia) il bot scrive testo
normale in chat — vedi ``messages.py``.
"""

from __future__ import annotations

import discord

from .service import SheetDTO

# Icona del progetto, servita dal repo pubblico (per author/thumbnail).
ICON_URL = "https://raw.githubusercontent.com/SalvatoreDevelopment/aedo/main/assets/aedo_256.png"
AUTHOR_NAME = "Aedo · il cantastorie"
_AEDO_COLOR = discord.Color.from_str("#9b8cce")


def genre_color(genre: str) -> discord.Color:
    """Una tinta tematica in base al genere della campagna."""
    g = (genre or "").lower()
    if any(k in g for k in ("cyber", "neon", "corpo", "fantascienza", "sci-fi", "spazi", "futur")):
        return discord.Color.from_str("#c9379a")   # magenta neon
    if any(k in g for k in ("noir", "giallo", "investig", "detective", "anni '40")):
        return discord.Color.from_str("#6b7a8f")   # grigio-azzurro fumoso
    if any(k in g for k in ("fantasy", "regn", "magia", "draghi", "medioev", "epic")):
        return discord.Color.from_str("#c9a36b")   # oro
    if any(k in g for k in ("horror", "incub", "terrore", "gotic", "soprannatur")):
        return discord.Color.from_str("#8b2f3a")   # rosso scuro
    return _AEDO_COLOR


def sheet_embed(dto: SheetDTO) -> discord.Embed:
    embed = discord.Embed(title=f"📋 {dto.name}", color=genre_color(dto.genre))
    embed.set_author(name=AUTHOR_NAME, icon_url=ICON_URL)
    embed.add_field(
        name="Attributi",
        value="\n".join(f"{k}  **{v}**" for k, v in dto.attributes.items()) or "—",
        inline=True,
    )
    embed.add_field(
        name="Risorse",
        value="\n".join(f"{k}  `{v}`" for k, v in dto.resources.items()) or "—",
        inline=True,
    )
    if dto.conditions:
        embed.add_field(name="Condizioni", value="  ".join(f"`{c}`" for c in dto.conditions), inline=False)
    embed.set_footer(text=dto.genre)
    return embed


def inventory_embed(items: list[dict]) -> discord.Embed:
    embed = discord.Embed(title="🎒 Inventario", color=_AEDO_COLOR)
    embed.set_author(name=AUTHOR_NAME, icon_url=ICON_URL)
    if not items:
        embed.description = "Le tue tasche sono vuote."
        return embed
    for it in items:
        qty = f"  ×{it['quantity']}" if it["quantity"] != 1 else ""
        embed.add_field(name=f"{it['name']}{qty}", value=it["description"] or "—", inline=False)
    return embed


def objectives_embed(objs: list[dict]) -> discord.Embed:
    embed = discord.Embed(title="🎯 Obiettivi", color=_AEDO_COLOR)
    embed.set_author(name=AUTHOR_NAME, icon_url=ICON_URL)
    if not objs:
        embed.description = "Nessun obiettivo, per ora."
        return embed
    icon = {"open": "⏳", "completed": "✅", "failed": "❌"}
    for o in objs:
        embed.add_field(
            name=f"{icon.get(o['status'], '•')} {o['title']}",
            value=o["description"] or "—",
            inline=False,
        )
    return embed
