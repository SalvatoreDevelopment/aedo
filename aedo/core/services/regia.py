"""Regia narrativa: la coda di comandi fra il Banco del Master e il canale.

Il Banco (un processo) non è connesso a Discord; il bot sì. Il ponte è il
database: il Banco **accoda** un :class:`MasterCommand`, il bot lo **esegue** nel
canale della campagna e ne aggiorna lo stato. Qui vive tutta la logica di questo
scambio — accodamento (lato Banco) ed esecuzione (lato bot, che passa il proprio
narratore).

Tre tipi di ordine:

* ``inject_event``  — un testo del master, postato così com'è come voce del mondo;
* ``narrate_event`` — uno spunto che Aedo trasforma in una scena narrata;
* ``override_last`` — corregge l'esito dell'ultima prova e fa ri-narrare la scena.

Nota sull'override: cambia l'esito registrato e la narrazione, ma **non** storna
i cambiamenti di stato già applicati dal turno originale — quelli il master li
sistema a mano dal Controllo dello Stato (Tappa A). Così la correzione resta
prevedibile e non produce effetti collaterali a sorpresa.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from aedo.core.models import (
    Campaign,
    Character,
    CommandKind,
    CommandStatus,
    EventLog,
    MasterCommand,
    MasterNote,
    Outcome,
    utcnow,
)
from aedo.core.narrator.base import NarratorProvider

from .game_service import build_context

_OUTCOME_LABEL = {
    Outcome.SUCCESS: "successo pieno",
    Outcome.SUCCESS_WITH_COST: "successo con una complicazione",
    Outcome.FAILURE: "fallimento",
}


@dataclass
class RegiaJob:
    """Risultato di un comando eseguito, pronto da postare nel canale.

    Solo primitivi: sicuro da restituire a un thread del bot.
    """

    command_id: int
    channel_id: str
    kind: str
    narration: str
    outcome: str | None
    genre: str


# === Lato Banco: accodamento e note =======================================
def enqueue(session: Session, campaign_id: int, kind: CommandKind, payload: str) -> MasterCommand:
    cmd = MasterCommand(campaign_id=campaign_id, kind=kind, payload=payload)
    session.add(cmd)
    session.flush()
    return cmd


def recent_commands(session: Session, campaign_id: int, limit: int = 15) -> list[MasterCommand]:
    return list(
        session.scalars(
            select(MasterCommand)
            .where(MasterCommand.campaign_id == campaign_id)
            .order_by(MasterCommand.id.desc())
            .limit(limit)
        ).all()
    )


def last_resolved_event(session: Session, campaign_id: int) -> EventLog | None:
    """L'ultima prova con un esito (il candidato per l'override)."""
    return session.scalar(
        select(EventLog)
        .where(EventLog.campaign_id == campaign_id, EventLog.outcome.is_not(None))
        .order_by(EventLog.id.desc())
    )


def add_note(session: Session, campaign_id: int, text: str) -> MasterNote:
    note = MasterNote(campaign_id=campaign_id, text=text.strip())
    session.add(note)
    session.flush()
    return note


def list_notes(session: Session, campaign_id: int) -> list[MasterNote]:
    return list(
        session.scalars(
            select(MasterNote)
            .where(MasterNote.campaign_id == campaign_id)
            .order_by(MasterNote.id.desc())
        ).all()
    )


def delete_note(session: Session, campaign_id: int, note_id: int) -> bool:
    note = session.get(MasterNote, note_id)
    if note is None or note.campaign_id != campaign_id:
        return False
    session.delete(note)
    session.flush()
    return True


# === Lato bot: esecuzione ==================================================
def pending_commands(session: Session) -> list[MasterCommand]:
    return list(
        session.scalars(
            select(MasterCommand)
            .where(MasterCommand.status == CommandStatus.PENDING)
            .order_by(MasterCommand.id)
        ).all()
    )


def _player(session: Session, campaign: Campaign) -> Character | None:
    return session.scalar(
        select(Character).where(
            Character.campaign_id == campaign.id, Character.is_player.is_(True)
        )
    )


def _record_event(campaign: Campaign, narration: str, outcome: Outcome | None = None) -> None:
    campaign.events.append(
        EventLog(
            actor="Aedo",
            action_text="(regia del master)",
            narration=narration,
            outcome=outcome,
        )
    )


def _mark_done(cmd: MasterCommand, narration: str) -> None:
    cmd.status = CommandStatus.DONE
    cmd.processed_at = utcnow()
    cmd.result_narration = narration


def _mark_error(cmd: MasterCommand, message: str) -> None:
    cmd.status = CommandStatus.ERROR
    cmd.processed_at = utcnow()
    cmd.error = message


def _execute_one(session: Session, cmd: MasterCommand, narrator: NarratorProvider) -> RegiaJob | None:
    campaign = session.get(Campaign, cmd.campaign_id)
    if campaign is None or not campaign.discord_channel_id:
        _mark_error(cmd, "Campagna o canale Discord mancante.")
        return None

    try:
        outcome: str | None = None

        if cmd.kind == CommandKind.INJECT_EVENT:
            text = cmd.payload.strip()
            if not text:
                _mark_error(cmd, "Evento vuoto.")
                return None
            _record_event(campaign, text)

        elif cmd.kind == CommandKind.NARRATE_EVENT:
            pc = _player(session, campaign)
            if pc is None:
                _mark_error(cmd, "Nessun personaggio nella campagna.")
                return None
            ctx = build_context(session, campaign, pc, action=f"[EVENTO DEL MASTER] {cmd.payload}")
            narration = narrator.narrate(ctx, None)
            text = narration.text
            if narration.new_summary:
                campaign.current_summary = narration.new_summary
            _record_event(campaign, text)

        elif cmd.kind == CommandKind.OVERRIDE_LAST:
            event = last_resolved_event(session, campaign.id)
            if event is None:
                _mark_error(cmd, "Nessuna prova recente da correggere.")
                return None
            try:
                new_outcome = Outcome(cmd.payload)
            except ValueError:
                _mark_error(cmd, f"Esito non valido: {cmd.payload!r}.")
                return None
            pc = _player(session, campaign)
            if pc is None:
                _mark_error(cmd, "Nessun personaggio nella campagna.")
                return None
            label = _OUTCOME_LABEL[new_outcome]
            ctx = build_context(
                session, campaign, pc,
                action=(
                    f"[CORREZIONE DEL DESTINO] L'azione «{event.action_text}» ora ha come "
                    f"esito un {label}. Ri-racconta brevemente come si risolve quella scena."
                ),
            )
            narration = narrator.narrate(ctx, None)
            text = narration.text
            event.outcome = new_outcome          # correzione retroattiva dell'esito
            event.narration = text
            if narration.new_summary:
                campaign.current_summary = narration.new_summary
            outcome = new_outcome.value

        else:  # pragma: no cover - enum chiuso
            _mark_error(cmd, f"Tipo di comando sconosciuto: {cmd.kind!r}.")
            return None

    except Exception as exc:  # la chiamata AI può fallire: non bloccare la coda
        _mark_error(cmd, f"Errore nell'esecuzione: {exc}")
        return None

    _mark_done(cmd, text)
    return RegiaJob(
        command_id=cmd.id,
        channel_id=campaign.discord_channel_id,
        kind=cmd.kind.value,
        narration=text,
        outcome=outcome,
        genre=campaign.blueprint.genre,
    )


def run_pending(session: Session, narrator: NarratorProvider) -> list[RegiaJob]:
    """Esegue tutti i comandi in coda e restituisce cosa postare nei canali."""
    jobs: list[RegiaJob] = []
    for cmd in pending_commands(session):
        job = _execute_one(session, cmd, narrator)
        if job is not None:
            jobs.append(job)
    session.flush()
    return jobs
