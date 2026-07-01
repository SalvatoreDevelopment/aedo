"""Strumenti del master: oracolo, generatori, statistiche.

Filosofia (decisa in design): il master NON è un giocatore di ruolo esperto.
Niente dadi grezzi da scegliere: fa una **domanda in italiano** e sceglie quanto
è probabile; il caso resta invisibile. I generatori danno spunti pronti (nomi,
NPC, ganci di trama) da liste curate — nessuna chiamata AI, nessun costo, tutto
deterministico e testabile. Le statistiche si ricavano da ciò che è già nel
database (turni, esiti, relazioni…): niente conteggi di token, che il progetto
non traccia ancora.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aedo.core.models import (
    Character,
    EventLog,
    Memory,
    Objective,
    ObjectiveStatus,
    Outcome,
    Relationship,
)

# === Oracolo a domande =====================================================
# Sposta la soglia del "sì" in base a quanto il master ritiene probabile l'esito.
_LIKELIHOOD_BIAS = {"unlikely": -0.22, "even": 0.0, "likely": 0.22}
_LIKELIHOOD_LABEL = {"unlikely": "improbabile", "even": "50 e 50", "likely": "probabile"}


@dataclass
class OracleAnswer:
    question: str
    likelihood: str
    answer: str      # "Sì" | "Sì, ma…" | "No, ma…" | "No"
    grade: str       # "yes" | "yes_but" | "no_but" | "no"


def ask_oracle(question: str, likelihood: str = "even", rng: random.Random | None = None) -> OracleAnswer:
    """Risponde a una domanda sì/no a quattro gradi, col caso invisibile.

    Riusa la filosofia dell'esito a gradi del gioco: non solo sì/no, ma anche i
    due "ma…" che aprono complicazioni o spiragli.
    """
    if likelihood not in _LIKELIHOOD_BIAS:
        likelihood = "even"
    rng = rng or random.Random()
    score = min(0.999, max(0.0, rng.random() + _LIKELIHOOD_BIAS[likelihood]))
    if score >= 0.75:
        grade, answer = "yes", "Sì"
    elif score >= 0.5:
        grade, answer = "yes_but", "Sì, ma…"
    elif score >= 0.25:
        grade, answer = "no_but", "No, ma…"
    else:
        grade, answer = "no", "No"
    return OracleAnswer(question=question.strip(), likelihood=likelihood, answer=answer, grade=grade)


# === Generatori (liste curate per categoria di genere) =====================
_NAMES = {
    "fantasy": ["Aldric", "Bryn", "Cael", "Dara", "Eldric", "Fenn", "Gwen", "Isolde",
                "Kael", "Lyra", "Mira", "Oren", "Rowan", "Sable", "Thane", "Vesper"],
    "noir": ["Sam", "Lou", "Vince", "Marla", "Eddie", "Gloria", "Rocco", "Dinah",
             "Carl", "Vera", "Nick", "Rita", "Hank", "Sal"],
    "cyber": ["Rei", "Kade", "Nyx", "Zeta", "Vex", "Mara", "Dex", "Corvo",
              "Lux", "Onyx", "Riko", "Neon", "Ash", "Wren"],
    "generic": ["Alex", "Robin", "Kai", "Noa", "Ivo", "Lena", "Dario", "Sofia",
                "Marco", "Elis", "Tara", "Bruno"],
}
_EPITHETS = {
    "fantasy": ["il Silenzioso", "dei Boschi", "Occhio di Falco", "il Ramingo", "Mano di Ferro", "la Saggia"],
    "noir": ["detto 'il Contabile'", "dalle mani pulite", "la Vedova", "occhi tristi", "senza fissa dimora"],
    "cyber": ["/root", "ex-corp", "dei Bassifondi", "protocollo-9", "senza-volto", "ICE-breaker"],
    "generic": ["il forestiero", "dal passato oscuro", "di poche parole", "con un segreto"],
}
_ROLES = {
    "fantasy": ["locandiere", "mercenario", "chierico caduto", "erborista", "cavaliere errante", "mercante"],
    "noir": ["informatore", "poliziotto corrotto", "cantante di locale", "strozzino", "tassista", "giornalista"],
    "cyber": ["fixer", "netrunner", "guardia corporativa", "hacker ribelle", "corriere", "barista sintetico"],
    "generic": ["vicino di casa", "commerciante", "funzionario", "viaggiatore", "guardiano", "guida locale"],
}
_TRAITS = [
    "nasconde qualcosa", "fin troppo gentile", "cinico ma leale", "in debito con la persona sbagliata",
    "cerca vendetta", "spaventato a morte", "ambizioso senza scrupoli", "fedele fino alla fine",
    "parla troppo", "non si fida di nessuno",
]
_THINGS = {
    "fantasy": ["un artefatto perduto", "l'erede scomparso", "una reliquia maledetta", "la mappa del passaggio"],
    "noir": ["un carico di contrabbando", "una lettera compromettente", "il testimone chiave", "una valigetta"],
    "cyber": ["dati rubati alla corp", "un impianto proibito", "le coordinate di un rifugio", "una chiave crittografica"],
    "generic": ["un oggetto di famiglia", "un messaggio urgente", "una persona scomparsa", "un segreto sepolto"],
}
_HOOKS = [
    "{name} chiede aiuto per ritrovare {thing}, ma mente sul vero motivo.",
    "Gira voce che {thing} sia nascosto dove nessuno oserebbe cercare.",
    "{name} viene trovato senza vita; l'ultima parola era un nome familiare.",
    "Qualcuno offre {thing} in cambio di un favore che non si può rifiutare.",
    "Un vecchio debito torna a bussare: {name} vuole essere ripagato entro l'alba.",
    "{thing} sparisce nel nulla, e ogni indizio punta a un innocente.",
]


def category_of(genre: str) -> str:
    """Riconduce un genere libero a una delle categorie con liste dedicate."""
    g = (genre or "").lower()
    if any(k in g for k in ("cyber", "neon", "corpo", "sci-fi", "fantascienza", "spazi", "futur")):
        return "cyber"
    if any(k in g for k in ("noir", "giallo", "investig", "detective", "anni '40")):
        return "noir"
    if any(k in g for k in ("fantasy", "regn", "magia", "draghi", "medioev", "epic")):
        return "fantasy"
    return "generic"


def generate_names(genre: str, n: int = 5, rng: random.Random | None = None) -> list[str]:
    rng = rng or random.Random()
    cat = category_of(genre)
    firsts = _NAMES[cat]
    epithets = _EPITHETS[cat]
    out: list[str] = []
    for _ in range(max(1, min(n, 12))):
        name = rng.choice(firsts)
        if rng.random() < 0.4:
            name = f"{name} {rng.choice(epithets)}"
        out.append(name)
    return out


def generate_npc(genre: str, rng: random.Random | None = None) -> dict[str, str]:
    rng = rng or random.Random()
    cat = category_of(genre)
    return {
        "name": rng.choice(_NAMES[cat]),
        "role": rng.choice(_ROLES[cat]),
        "trait": rng.choice(_TRAITS),
    }


def generate_hook(genre: str, rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    cat = category_of(genre)
    template = rng.choice(_HOOKS)
    return template.format(name=rng.choice(_NAMES[cat]), thing=rng.choice(_THINGS[cat]))


# === Statistiche della campagna ===========================================
@dataclass
class CampaignStats:
    turns: int = 0                       # azioni del giocatore registrate
    events_total: int = 0
    outcomes: dict[str, int] = field(default_factory=dict)  # per grado di esito
    npc_count: int = 0
    memory_count: int = 0
    objectives: dict[str, int] = field(default_factory=dict)
    relationships: list[dict] = field(default_factory=list)  # {name, affinity, kind}


def campaign_stats(session: Session, campaign_id: int) -> CampaignStats:
    events = session.scalars(
        select(EventLog).where(EventLog.campaign_id == campaign_id)
    ).all()
    outcomes = {o.value: 0 for o in Outcome}
    turns = 0
    for e in events:
        if e.outcome is not None:
            outcomes[e.outcome.value] += 1
        if e.action_text and e.action_text not in ("(apertura)", "(regia del master)"):
            turns += 1

    npc_count = session.scalar(
        select(func.count()).select_from(Character).where(
            Character.campaign_id == campaign_id, Character.is_player.is_(False)
        )
    ) or 0
    memory_count = session.scalar(
        select(func.count()).select_from(Memory).where(Memory.campaign_id == campaign_id)
    ) or 0

    objs = session.scalars(
        select(Objective).where(Objective.campaign_id == campaign_id)
    ).all()
    obj_counts = {s.value: 0 for s in ObjectiveStatus}
    for o in objs:
        obj_counts[o.status.value] += 1

    rels = session.scalars(
        select(Relationship).where(Relationship.campaign_id == campaign_id)
    ).all()
    rel_list = [
        {"name": r.to_character.name, "kind": r.kind, "affinity": r.affinity}
        for r in rels
    ]

    return CampaignStats(
        turns=turns, events_total=len(events), outcomes=outcomes,
        npc_count=npc_count, memory_count=memory_count,
        objectives=obj_counts, relationships=rel_list,
    )
