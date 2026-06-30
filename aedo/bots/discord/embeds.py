"""Costruzione degli embed Discord a partire dai DTO del service."""

from __future__ import annotations

import discord

from .service import NewCampaignDTO, SheetDTO, TurnDTO

# Colore dell'esito del tiro.
_OUTCOME_COLOR = {
    "success": discord.Color.green(),
    "success_cost": discord.Color.gold(),
    "failure": discord.Color.red(),
}
_OUTCOME_LABEL = {
    "success": "successo",
    "success_cost": "riesci, ma…",
    "failure": "fallimento",
}
_AEDO_COLOR = discord.Color.dark_purple()


def opening_embed(dto: NewCampaignDTO) -> discord.Embed:
    embed = discord.Embed(
        title=f"🎭 {dto.campaign_name}",
        description=dto.opening,
        color=_AEDO_COLOR,
    )
    attrs = " · ".join(f"{k} {v}" for k, v in dto.attributes.items())
    embed.add_field(name=dto.character_name, value=attrs or "—", inline=False)
    embed.set_footer(text=f"{dto.genre} · scrivi cosa fai per giocare")
    return embed


def turn_embed(dto: TurnDTO) -> discord.Embed:
    color = _OUTCOME_COLOR.get(dto.outcome, _AEDO_COLOR)
    embed = discord.Embed(description=dto.narration, color=color)
    if dto.roll_summary and dto.outcome:
        label = _OUTCOME_LABEL.get(dto.outcome, dto.outcome)
        embed.set_footer(text=f"🎲 {dto.roll_summary} — {label}")
    return embed


def sheet_embed(dto: SheetDTO) -> discord.Embed:
    embed = discord.Embed(title=f"📋 {dto.name}", color=_AEDO_COLOR)
    embed.add_field(
        name="Attributi",
        value="\n".join(f"{k}: {v}" for k, v in dto.attributes.items()) or "—",
        inline=True,
    )
    embed.add_field(
        name="Risorse",
        value="\n".join(f"{k}: {v}" for k, v in dto.resources.items()) or "—",
        inline=True,
    )
    if dto.conditions:
        embed.add_field(name="Condizioni", value=", ".join(dto.conditions), inline=False)
    embed.set_footer(text=dto.genre)
    return embed


def inventory_embed(items: list[dict]) -> discord.Embed:
    embed = discord.Embed(title="🎒 Inventario", color=_AEDO_COLOR)
    if not items:
        embed.description = "Le tue tasche sono vuote."
        return embed
    for it in items:
        qty = f" ×{it['quantity']}" if it["quantity"] != 1 else ""
        embed.add_field(
            name=f"{it['name']}{qty}",
            value=it["description"] or "—",
            inline=False,
        )
    return embed


def objectives_embed(objs: list[dict]) -> discord.Embed:
    embed = discord.Embed(title="🎯 Obiettivi", color=_AEDO_COLOR)
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
