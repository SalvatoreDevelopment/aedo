"""Playground da terminale: gioca una campagna senza Discord.

    python -m aedo.play --template noir --name Sam

Usa OpenRouter se è configurata la chiave (.env), altrimenti ricade sul
narratore finto con un avviso. Utile per provare il loop prima del bot.
"""

from __future__ import annotations

import argparse
import sys

# La console di Windows usa cp1252: forziamo UTF-8 per accenti e simboli.
for _stream in (sys.stdout, sys.stdin, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

from aedo.config import settings
from aedo.core.narrator import get_narrator
from aedo.core.services.campaign_service import (
    create_campaign_from_template,
    create_player_character,
)
from aedo.core.services.game_service import play_turn, start_campaign
from aedo.storage import SessionLocal, init_db
from aedo.templates import list_templates


def _pick_narrator(choice: str):
    if choice == "fake":
        return get_narrator("fake"), "fake"
    if choice in ("auto", "openrouter"):
        if settings.openrouter_api_key:
            return get_narrator("openrouter"), f"openrouter:{settings.aedo_model}"
        if choice == "openrouter":
            raise SystemExit("Manca OPENROUTER_API_KEY nel file .env")
        print("[avviso] nessuna chiave OpenRouter: uso il narratore finto.\n")
    return get_narrator("fake"), "fake"


def main() -> None:
    parser = argparse.ArgumentParser(description="Aedo — playground da terminale")
    parser.add_argument("--template", default="noir", choices=list_templates())
    parser.add_argument("--name", default="Eroe", help="nome del personaggio")
    parser.add_argument("--narrator", default="auto", choices=["auto", "fake", "openrouter"])
    parser.add_argument("--spunto", default="", help="idea/tema facoltativo per l'incipit")
    args = parser.parse_args()

    init_db()
    narrator, label = _pick_narrator(args.narrator)

    with SessionLocal() as session:
        campaign = create_campaign_from_template(
            session, template_name=args.template,
            campaign_name=f"Partita di {args.name}",
        )
        # Attributi di partenza giocabili (prima creazione vera nella fase Discord):
        # tutti a 2, il primo a 3.
        attr_names = [a["name"] for a in campaign.blueprint.attributes]
        starting = {name: 2 for name in attr_names}
        if attr_names:
            starting[attr_names[0]] = 3
        pc = create_player_character(
            session, campaign, name=args.name, attributes=starting
        )
        session.commit()

        print(f"\n=== {campaign.name} · {campaign.blueprint.genre} ===")
        print(f"Narratore: {label}")
        print(f"{pc.name} — attributi {pc.attributes} — risorse {pc.resources}")
        print("Scrivi cosa fai in linguaggio naturale. Comandi: /scheda  /esci\n")

        # Scena di apertura: cala il giocatore nella storia prima del primo turno.
        print("…Aedo prepara la scena…\n")
        opening = start_campaign(session, campaign, pc, narrator, premise=args.spunto)
        session.commit()
        print(f"{opening}\n")

        while True:
            try:
                action = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not action:
                continue
            if action == "/esci":
                break
            if action == "/scheda":
                session.refresh(pc)
                print(f"  {pc.name} — attributi {pc.attributes} — risorse {pc.resources}")
                if pc.conditions:
                    print(f"  condizioni: {', '.join(pc.conditions)}")
                continue

            result = play_turn(session, campaign, pc, action, narrator)
            session.commit()
            if result.resolution:
                print(f"  [{result.resolution.summary} → {result.resolution.outcome.value}]")
            print(f"\n{result.narration}\n")


if __name__ == "__main__":
    main()
