"""Costruzione degli embed Discord a partire dai DTO del service.

Solo presentazione: il colore segue il genere della campagna, l'esito del tiro
è messo in evidenza, e il narratore si "firma" con la lira di Aedo.
"""

from __future__ import annotations

import discord

from .service import NewCampaignDTO, SheetDTO, TurnDTO

# Icona del progetto, servita dal repo pubblico (per author/thumbnail).
ICON_URL = "https://raw.githubusercontent.com/SalvatoreDevelopment/aedo/main/assets/aedo_256.png"
AUTHOR_NAME = "Aedo · il cantastorie"

# Colore dell'esito del tiro (ha la precedenza quando c'è una prova).
_OUTCOME_COLOR = {
    "success": discord.Color.from_str("#3ba55d"),
    "success_cost": discord.Color.from_str("#e0a93f"),
    "failure": discord.Color.from_str("#d4537e"),
}
_OUTCOME_LABEL = {
    "success": "successo",
    "success_cost": "riesci, ma…",
    "failure": "fallimento",
}
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


def _attrs_line(attributes: dict[str, int]) -> str:
    return " · ".join(f"**{k}** {v}" for k, v in attributes.items()) or "—"


def _resources_line(resources: dict[str, int]) -> str:
    return "   ".join(f"{k} `{v}`" for k, v in resources.items()) or "—"


def opening_embed(dto: NewCampaignDTO) -> discord.Embed:
    embed = discord.Embed(
        title=dto.campaign_name, description=dto.opening, color=genre_color(dto.genre)
    )
    embed.set_author(name=AUTHOR_NAME, icon_url=ICON_URL)
    embed.set_thumbnail(url=ICON_URL)
    embed.add_field(name=f"👤 {dto.character_name}", value=_attrs_line(dto.attributes), inline=False)
    if dto.resources:
        embed.add_field(name="Risorse", value=_resources_line(dto.resources), inline=False)
    embed.set_footer(text=f"{dto.genre}  ·  scrivi cosa fai per giocare")
    return embed


def turn_embed(dto: TurnDTO) -> discord.Embed:
    color = _OUTCOME_COLOR.get(dto.outcome) or genre_color(dto.genre)
    embed = discord.Embed(description=dto.narration, color=color)
    if dto.roll_summary and dto.outcome:
        label = _OUTCOME_LABEL.get(dto.outcome, dto.outcome)
        embed.add_field(name="🎲 Prova", value=f"{dto.roll_summary} — **{label}**", inline=False)
    return embed


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
