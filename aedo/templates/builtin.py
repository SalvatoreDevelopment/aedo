"""Template di genere predefiniti.

Ogni template è un Blueprint pronto all'uso. Sono volutamente diversissimi fra
loro — attributi, tono, risorse, persino il dado — per dimostrare che il motore
non sa nulla del genere: tutto vive nei dati. Da un template si crea una
campagna (vedi `aedo.core.services.campaign_service`).

Un utente può sempre partire da uno di questi e modificarlo, o crearne uno da
zero (il "custom" deciso in fase di design).
"""

from __future__ import annotations

from collections.abc import Callable

from aedo.core.models import Blueprint, CrunchLevel


def _noir() -> Blueprint:
    return Blueprint(
        name="Noir investigativo",
        genre="noir, città di porto anni '40",
        tone="cupo, adulto, ironico; frasi brevi, ombre lunghe",
        narrator_persona=(
            "Sei un narratore hard-boiled. Descrivi pioggia, fumo e doppi giochi. "
            "Lasci che siano i dettagli sordidi a parlare. Niente eroi, solo gente stanca."
        ),
        crunch_level=CrunchLevel.NARRATIVE,
        attributes=[
            {"name": "Intuito", "description": "leggere persone, indizi, bugie"},
            {"name": "Sangue freddo", "description": "restare lucidi sotto pressione"},
            {"name": "Strada", "description": "contatti, risse, sapersi muovere"},
            {"name": "Fascino", "description": "convincere, sedurre, depistare"},
        ],
        conflict_types=["interrogatorio", "pedinamento", "deduzione", "resa dei conti"],
        default_resources={"salute": 5, "nervi": 3},
        special_rules=(
            "Le armi da fuoco sono letali e rumorose: usarle ha sempre conseguenze. "
            "I segreti contano più dei pugni."
        ),
        dice_formula="2d6",
        success_band=2,
        is_template=True,
    )


def _fantasy() -> Blueprint:
    return Blueprint(
        name="Fantasy heroico",
        genre="fantasy classico, regni e antiche rovine",
        tone="epico ma caldo; meraviglia, coraggio, sacrificio",
        narrator_persona=(
            "Sei un bardo che canta gesta. Dai colore a paesaggi, creature e magia. "
            "Premi l'audacia, ma il mondo ha le sue leggi e i suoi pericoli."
        ),
        crunch_level=CrunchLevel.BALANCED,
        attributes=[
            {"name": "Forza", "description": "muscoli, armi, imprese fisiche"},
            {"name": "Agilità", "description": "rapidità, furtività, schivare"},
            {"name": "Ingegno", "description": "sapere, enigmi, magia"},
            {"name": "Spirito", "description": "volontà, carisma, fede"},
        ],
        conflict_types=["combattimento", "esplorazione", "incantesimo", "trattativa"],
        default_resources={"vita": 10, "vigore": 4, "mana": 3},
        special_rules=(
            "La magia richiede mana e ha un costo narrativo se forzata. "
            "Le creature leggendarie meritano difficoltà ESTREME."
        ),
        dice_formula="2d6",
        success_band=2,
        is_template=True,
    )


def _cyberpunk() -> Blueprint:
    return Blueprint(
        name="Cyberpunk",
        genre="megalopoli al neon, corporazioni e ribelli",
        tone="teso, sporco, ad alta tecnologia e bassa fiducia",
        narrator_persona=(
            "Sei un narratore street-level: insegne olografiche, pioggia acida, "
            "innesti cibernetici. Tutto ha un prezzo e qualcuno che ti osserva."
        ),
        crunch_level=CrunchLevel.TACTICAL,
        attributes=[
            {"name": "Hacking", "description": "violare reti, ICE, sistemi"},
            {"name": "Riflessi", "description": "combattimento, guida, scatto"},
            {"name": "Strada", "description": "contatti, mercato nero, sopravvivenza"},
            {"name": "Sangue freddo", "description": "tenere i nervi e l'umanità"},
        ],
        conflict_types=["intrusione", "sparatoria", "inseguimento", "negoziazione"],
        default_resources={"salute": 6, "umanità": 5, "eddies": 200},
        special_rules=(
            "Gli innesti cibernetici danno bonus ma erodono l'umanità. "
            "Hackerare sotto pressione usa Hacking con difficoltà alte."
        ),
        dice_formula="1d20",
        success_band=4,
        is_template=True,
    )


# Registry: nome canonico → factory che produce un Blueprint nuovo.
_TEMPLATES: dict[str, Callable[[], Blueprint]] = {
    "noir": _noir,
    "fantasy": _fantasy,
    "cyberpunk": _cyberpunk,
}


def list_templates() -> list[str]:
    """Nomi dei template disponibili."""
    return list(_TEMPLATES)


def get_template(name: str) -> Blueprint:
    """Crea un nuovo Blueprint dal template indicato.

    Restituisce un'istanza non ancora persistita; sollevare KeyError se il
    nome non esiste.
    """
    key = name.strip().lower()
    if key not in _TEMPLATES:
        raise KeyError(
            f"Template sconosciuto: {name!r}. Disponibili: {', '.join(_TEMPLATES)}"
        )
    return _TEMPLATES[key]()
