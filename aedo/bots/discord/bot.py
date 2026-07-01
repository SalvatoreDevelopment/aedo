"""Bot Discord di Aedo.

Modello d'uso (deciso in design): ogni campagna vive in un **canale dedicato**.
Si gioca scrivendo liberamente nel canale (niente comando per giocare); gli
slash command servono solo per le utility (/scheda, /inventario, /quest).

Avvio:  python -m aedo.bots.discord
Richiede DISCORD_TOKEN nel .env e il "Message Content Intent" abilitato.
"""

from __future__ import annotations

import asyncio
import logging
import re

import discord
from discord import app_commands
from discord.ext import tasks

from aedo.config import settings
from aedo.core.narrator import get_narrator
from aedo.storage import init_db
from aedo.templates import list_templates
from . import embeds, messages, service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aedo.bot")

CATEGORY_NAME = "Aedo"


def _make_narrator():
    """OpenRouter se c'è la chiave, altrimenti narratore finto con avviso."""
    if settings.openrouter_api_key:
        logger.info("Narratore: OpenRouter (%s)", settings.aedo_model)
        return get_narrator("openrouter")
    logger.warning("Nessuna chiave OpenRouter: uso il narratore finto.")
    return get_narrator("fake")


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\s-]", "", name.lower()).strip()
    s = re.sub(r"[\s_]+", "-", s)
    return (s or "campagna")[:90]


class AedoBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True  # privilegiato: leggere i messaggi nei canali
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.narrator = _make_narrator()

    async def setup_hook(self) -> None:
        init_db()
        await self.tree.sync()

    async def on_ready(self) -> None:
        logger.info("Aedo è online come %s", self.user)
        if not regia_loop.is_running():
            regia_loop.start()


bot = AedoBot()


async def _send_narration(channel, text: str) -> None:
    """Invia una narrazione come testo normale, spezzandola se troppo lunga."""
    for part in messages.chunks(text):
        await channel.send(part)


# --- Ponte con il Banco del Master: coda di regia -------------------------

@tasks.loop(seconds=4.0)
async def regia_loop() -> None:
    """Esegue periodicamente gli ordini di regia accodati dal Banco.

    Il lavoro sul DB (incluse le chiamate al narratore) gira in un thread; qui
    restano solo gli invii nel canale.
    """
    try:
        jobs = await asyncio.to_thread(service.take_regia_jobs, bot.narrator)
    except Exception:
        logger.exception("Errore nel leggere la coda di regia")
        return
    for job in jobs:
        channel = bot.get_channel(int(job.channel_id))
        if channel is None:
            try:
                channel = await bot.fetch_channel(int(job.channel_id))
            except discord.HTTPException:
                logger.warning("Canale %s non trovato per la regia", job.channel_id)
                continue
        try:
            await _send_narration(channel, messages.master_event_text(job))
        except discord.HTTPException:
            logger.exception("Invio dell'evento di regia fallito")


@regia_loop.before_loop
async def _before_regia_loop() -> None:
    await bot.wait_until_ready()


# --- Slash commands -------------------------------------------------------

_TEMPLATE_CHOICES = [
    app_commands.Choice(name=t.capitalize(), value=t) for t in list_templates()
]


@bot.tree.command(name="nuova-campagna", description="Crea una campagna nel suo canale dedicato")
@app_commands.describe(
    template="Il genere di partenza",
    personaggio="Nome del tuo personaggio",
    nome="(facoltativo) nome della campagna; se lo lasci vuoto lo sceglie Aedo",
    spunto="(facoltativo) un'idea o tema per l'incipit",
)
@app_commands.choices(template=_TEMPLATE_CHOICES)
async def nuova_campagna(
    interaction: discord.Interaction,
    template: app_commands.Choice[str],
    personaggio: str,
    nome: str = "",
    spunto: str = "",
) -> None:
    if interaction.guild is None:
        await interaction.response.send_message(
            "Usa questo comando in un server, non in DM.", ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True, ephemeral=True)
    guild = interaction.guild

    # Canale dedicato e privato all'autore.
    category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
    if category is None:
        category = await guild.create_category(CATEGORY_NAME)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True),
    }
    provisional = _slug(nome) if nome.strip() else "nuova-campagna"
    channel = await guild.create_text_channel(
        name=provisional, category=category, overwrites=overwrites
    )

    try:
        dto = await asyncio.to_thread(
            service.create_campaign_in_channel,
            bot.narrator,
            channel_id=str(channel.id),
            guild_id=str(guild.id),
            owner_discord_id=str(interaction.user.id),
            template=template.value,
            campaign_name=nome,
            character_name=personaggio,
            premise=spunto,
        )
    except Exception:
        logger.exception("Errore nella creazione della campagna")
        await channel.delete()
        await interaction.followup.send(
            "Qualcosa è andato storto nel creare la campagna. Riprova.", ephemeral=True
        )
        return

    # Se il nome è stato proposto dal narratore, rinomina il canale di conseguenza.
    if _slug(dto.campaign_name) != provisional:
        try:
            await channel.edit(name=_slug(dto.campaign_name))
        except discord.HTTPException:
            pass

    await _send_narration(channel, messages.opening_text(dto))
    await interaction.followup.send(
        f"Campagna «{dto.campaign_name}» creata in {channel.mention} — scrivi lì per giocare.",
        ephemeral=True,
    )


async def _send_channel_info(interaction: discord.Interaction, builder, fetcher) -> None:
    """Helper per i comandi di sola lettura legati al canale."""
    data = await asyncio.to_thread(fetcher, str(interaction.channel_id))
    if data is None:
        await interaction.response.send_message(
            "Questo canale non ospita una campagna.", ephemeral=True
        )
        return
    await interaction.response.send_message(embed=builder(data), ephemeral=True)


@bot.tree.command(name="scheda", description="Mostra la scheda del tuo personaggio")
async def scheda(interaction: discord.Interaction) -> None:
    await _send_channel_info(interaction, embeds.sheet_embed, service.get_sheet)


@bot.tree.command(name="inventario", description="Mostra il tuo inventario")
async def inventario(interaction: discord.Interaction) -> None:
    await _send_channel_info(interaction, embeds.inventory_embed, service.get_inventory)


@bot.tree.command(name="quest", description="Mostra gli obiettivi della campagna")
async def quest(interaction: discord.Interaction) -> None:
    await _send_channel_info(interaction, embeds.objectives_embed, service.get_objectives)


# --- Gioco nel canale -----------------------------------------------------

@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot or message.guild is None:
        return
    action = message.content.strip()
    if not action:
        return
    channel_id = str(message.channel.id)

    # Solo nei canali-campagna: evita di scomodare l'AI altrove.
    if not await asyncio.to_thread(service.is_campaign_channel, channel_id):
        return

    async with message.channel.typing():
        dto = await asyncio.to_thread(
            service.run_player_turn,
            bot.narrator,
            channel_id=channel_id,
            discord_id=str(message.author.id),
            action=action,
        )
    if dto is not None:
        await _send_narration(message.channel, messages.turn_text(dto))


def main() -> None:
    if not settings.discord_token:
        raise SystemExit("Manca DISCORD_TOKEN nel file .env")
    bot.run(settings.discord_token)


if __name__ == "__main__":
    main()
