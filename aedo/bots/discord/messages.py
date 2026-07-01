"""Messaggi testuali del bot — quando Aedo *racconta*, scrive in chat normale.

La narrazione (apertura, turni, eventi di regia) esce come semplice testo, non
dentro un embed: si legge come un messaggio qualsiasi, com'è naturale per un
cantastorie. Gli embed restano solo per le *schede* di consultazione (scheda,
inventario, obiettivi), che sono tabelle di dati e non "Aedo che parla".
"""

from __future__ import annotations

from aedo.core.services.regia import RegiaJob

from .service import NewCampaignDTO, TurnDTO

_OUTCOME_LABEL = {
    "success": "successo",
    "success_cost": "riesci, ma…",
    "failure": "fallimento",
}

# Limite di un messaggio Discord (2000): stiamo un po' sotto per sicurezza.
_MAX = 1900


def chunks(text: str) -> list[str]:
    """Spezza un testo lungo in più messaggi, senza tagliare a metà parola."""
    text = text.strip() or "…"
    if len(text) <= _MAX:
        return [text]
    out: list[str] = []
    remaining = text
    while len(remaining) > _MAX:
        cut = remaining.rfind("\n", 0, _MAX)
        if cut <= 0:
            cut = remaining.rfind(" ", 0, _MAX)
        if cut <= 0:
            cut = _MAX
        out.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        out.append(remaining)
    return out


def turn_text(dto: TurnDTO) -> str:
    text = dto.narration.strip()
    if dto.roll_summary and dto.outcome:
        label = _OUTCOME_LABEL.get(dto.outcome, dto.outcome)
        text += f"\n\n🎲 *{dto.roll_summary} — {label}*"
    return text


def opening_text(dto: NewCampaignDTO) -> str:
    attrs = " · ".join(f"**{k}** {v}" for k, v in dto.attributes.items())
    lines = [f"**{dto.campaign_name}**", "", dto.opening.strip(), "", f"👤 **{dto.character_name}** — {attrs}"]
    if dto.resources:
        res = " · ".join(f"{k} {v}" for k, v in dto.resources.items())
        lines.append(f"Risorse: {res}")
    lines.append("")
    lines.append(f"_{dto.genre} · scrivi cosa fai per giocare_")
    return "\n".join(lines)


def master_event_text(job: RegiaJob) -> str:
    prefix = "🎭 *Il destino si riscrive.*\n\n" if job.kind == "override_last" else ""
    text = prefix + job.narration.strip()
    if job.outcome:
        text += f"\n\n🎲 *nuovo esito: {_OUTCOME_LABEL.get(job.outcome, job.outcome)}*"
    return text
