"""Servizio di alto livello per creare e popolare una campagna.

Orchestra modelli, template e regole in operazioni significative usate dalle
interfacce (bot Discord, API). Niente logica di dado qui: solo "stato".
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from aedo.core.models import Blueprint, Campaign, CampaignMode, Character
from aedo.templates import get_template


def _clone_blueprint(template: Blueprint) -> Blueprint:
    """Crea una copia indipendente del template come blueprint di campagna.

    Il template resta intatto e riusabile; la campagna possiede la propria
    copia delle regole, così modificarle non tocca altre campagne.
    """
    return Blueprint(
        name=template.name,
        genre=template.genre,
        tone=template.tone,
        narrator_persona=template.narrator_persona,
        crunch_level=template.crunch_level,
        attributes=[dict(a) for a in template.attributes],
        conflict_types=list(template.conflict_types),
        default_resources=dict(template.default_resources),
        special_rules=template.special_rules,
        dice_formula=template.dice_formula,
        success_band=template.success_band,
        is_template=False,
    )


def create_campaign_from_template(
    session: Session,
    *,
    template_name: str,
    campaign_name: str,
    owner_discord_id: str = "",
    mode: CampaignMode = CampaignMode.SINGLE,
) -> Campaign:
    """Crea una campagna a partire da un template di genere."""
    blueprint = _clone_blueprint(get_template(template_name))
    campaign = Campaign(
        name=campaign_name,
        mode=mode,
        owner_discord_id=owner_discord_id,
        blueprint=blueprint,
    )
    session.add(campaign)
    session.flush()
    return campaign


def create_player_character(
    session: Session,
    campaign: Campaign,
    *,
    name: str,
    discord_id: str | None = None,
    description: str = "",
    attributes: dict[str, int] | None = None,
) -> Character:
    """Crea un personaggio giocante dentro una campagna.

    Gli attributi mancanti sono inizializzati a 0 seguendo quelli definiti dal
    Blueprint; le risorse partono dai valori di default del Blueprint.
    """
    blueprint = campaign.blueprint
    bp_attr_names = [a["name"] for a in blueprint.attributes]
    provided = attributes or {}
    resolved_attrs = {name_: provided.get(name_, 0) for name_ in bp_attr_names}

    character = Character(
        campaign=campaign,
        name=name,
        is_player=True,
        discord_id=discord_id,
        description=description,
        attributes=resolved_attrs,
        resources=dict(blueprint.default_resources),
    )
    session.add(character)
    session.flush()
    return character
