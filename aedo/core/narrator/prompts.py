"""Costruzione dei prompt per il narratore.

Il system prompt "veste" Aedo con la persona e le regole del Blueprint; i
messaggi utente forniscono lo stato e l'azione, e chiedono un output JSON
rigoroso che il game loop possa applicare in modo deterministico.
"""

from __future__ import annotations

import json

from .base import NarratorContext


def _persona_block(ctx: NarratorContext) -> str:
    parts = [
        "Sei Aedo, il narratore (Dungeon Master) di un gioco di ruolo testuale.",
        f"Genere: {ctx.genre}.",
        f"Tono: {ctx.tone}.",
    ]
    if ctx.narrator_persona:
        parts.append(ctx.narrator_persona)
    if ctx.special_rules:
        parts.append(f"Regole speciali: {ctx.special_rules}")
    parts.append("Scrivi sempre in italiano, in seconda persona, immerso nella scena.")
    return "\n".join(parts)


def _state_block(ctx: NarratorContext) -> str:
    lines = [
        f"Personaggio: {ctx.character_name}.",
    ]
    if ctx.character_description:
        lines.append(f"Descrizione: {ctx.character_description}")
    lines.append(f"Attributi: {json.dumps(ctx.character_attributes, ensure_ascii=False)}")
    lines.append(f"Risorse: {json.dumps(ctx.character_resources, ensure_ascii=False)}")
    if ctx.character_conditions:
        lines.append(f"Condizioni: {', '.join(ctx.character_conditions)}")
    if ctx.current_summary:
        lines.append(f"Scena attuale: {ctx.current_summary}")
    if ctx.relevant_memories:
        lines.append("Ricordi rilevanti:")
        lines.extend(f"  - {m}" for m in ctx.relevant_memories)
    if ctx.recent_events:
        lines.append("Eventi recenti:")
        lines.extend(f"  - {e}" for e in ctx.recent_events)
    return "\n".join(lines)


def build_opening_messages(ctx: NarratorContext, premise: str = "") -> list[dict[str, str]]:
    """Messaggi per la scena di apertura della campagna."""
    system = (
        _persona_block(ctx)
        + "\n\nStai APRENDO la campagna: non c'è ancora alcun evento precedente. "
        "Scrivi un incipit di 4-7 frasi che cali subito il giocatore nella scena: "
        "dove si trova, l'atmosfera, e un gancio concreto (un problema, un incontro, "
        "un mistero) che gli faccia capire cosa può fare. Termina lasciando aperta "
        "l'iniziativa al giocatore, senza agire al posto suo."
    )
    spunto = (
        f"Spunto del giocatore per la campagna: «{premise}». Costruisci l'incipit attorno a questo.\n\n"
        if premise.strip()
        else "Nessuno spunto fornito: inventa tu un incipit adatto al genere.\n\n"
    )
    user = (
        f"{_state_block(ctx)}\n\n"
        f"{spunto}"
        "Rispondi SOLO con un oggetto JSON:\n"
        "{\n"
        '  "narration": string,  // l\'incipit immersivo\n'
        '  "new_summary": string,  // 1 frase: dove si trova ora il personaggio\n'
        '  "changes": {\n'
        '    "new_objectives": [{"title": string, "description": string}],\n'
        '    "relationship_changes": [{"name": string, "kind": string, "affinity_delta": intero}],\n'
        '    "memory": string|null, "memory_importance": numero 0..1\n'
        "  }\n"
        "}\n"
        "Puoi introdurre un primo obiettivo e/o un PNG iniziale, ma niente tiri o danni qui."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_turn_messages(ctx: NarratorContext) -> list[dict[str, str]]:
    """Messaggi per il turno combinato: valuta e, se non rischioso, narra subito.

    Un'unica chiamata per le azioni libere (la maggioranza), dimezzandone la
    latenza. Le azioni rischiose vengono solo valutate qui: il dado e la
    narrazione dell'esito restano un secondo passo (serve l'esito prima).
    """
    system = (
        _persona_block(ctx)
        + "\n\nValuta l'azione del giocatore e, SOLO se non è rischiosa, narrane subito l'esito.\n"
        "Un tiro serve solo se l'azione è incerta E ha una posta in gioco con conseguenze. "
        "Nel dubbio, considerala rischiosa (is_risky=true) e NON narrare: meglio un tiro in più "
        "che saltarne uno dovuto.\n"
        "Le risorse hanno un significato: se narri, consuma energia/mana per sforzi e poteri, "
        "scala la vita/salute per ferite o cure (variazioni piccole, solo se giustificate)."
    )
    attrs = ", ".join(ctx.attribute_names)
    diffs = ", ".join(ctx.difficulty_options)
    user = (
        f"{_state_block(ctx)}\n\n"
        f"Azione del giocatore: «{ctx.player_action}»\n\n"
        "Rispondi SOLO con un oggetto JSON:\n"
        "{\n"
        '  "is_risky": bool,\n'
        f'  "attribute": string|null,   // se rischiosa, UNO fra: {attrs}\n'
        f'  "difficulty": string|null,  // se rischiosa, UNA fra: {diffs}\n'
        '  "reason": string,\n'
        '  "narration": string|null,   // SOLO se NON rischiosa: 2-5 frasi vivide\n'
        '  "new_summary": string|null, // SOLO se NON rischiosa\n'
        '  "changes": {                // SOLO se NON rischiosa (altrimenti ometti)\n'
        '    "resource_deltas": {nome: intero}, "conditions_add": [string], "conditions_remove": [string],\n'
        '    "relationship_changes": [{"name": string, "kind": string, "affinity_delta": intero}],\n'
        '    "new_items": [{"name": string, "description": string, "quantity": intero}],\n'
        '    "removed_items": [string],\n'
        '    "new_objectives": [{"title": string, "description": string}], "completed_objectives": [string],\n'
        '    "memory": string|null, "memory_importance": numero 0..1\n'
        "  }\n"
        "}\n"
        "Se is_risky è true: compila attribute e difficulty, e lascia narration/changes nulli."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_assess_messages(ctx: NarratorContext) -> list[dict[str, str]]:
    """Messaggi per la valutazione: serve un tiro? con quali parametri?"""
    system = (
        _persona_block(ctx)
        + "\n\nOra devi solo VALUTARE l'azione del giocatore, non narrarla.\n"
        "Un tiro serve SOLO se l'azione è incerta E ha una posta in gioco con conseguenze. "
        "Azioni banali (parlare, guardarsi intorno, spostarsi senza pericolo) NON richiedono tiro."
    )
    attrs = ", ".join(ctx.attribute_names)
    diffs = ", ".join(ctx.difficulty_options)
    user = (
        f"{_state_block(ctx)}\n\n"
        f"Azione del giocatore: «{ctx.player_action}»\n\n"
        "Rispondi SOLO con un oggetto JSON con questi campi:\n"
        '{"is_risky": bool, "attribute": string|null, "difficulty": string|null, "reason": string}\n'
        f"- attribute: se is_risky, scegli UNO fra: {attrs}\n"
        f"- difficulty: se is_risky, scegli UNA fra: {diffs}\n"
        "- se is_risky è false, attribute e difficulty siano null."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_narrate_messages(ctx: NarratorContext, outcome: str | None) -> list[dict[str, str]]:
    """Messaggi per la narrazione + proposta di cambiamenti di stato."""
    system = (
        _persona_block(ctx)
        + "\n\nNarra l'esito dell'azione in 2-5 frasi vivide. "
        "Poi proponi i cambiamenti di stato conseguenti, senza inventare numeri di gioco.\n"
        "Le risorse del personaggio hanno un significato e vanno fatte vivere: "
        "consuma le risorse di energia/sforzo (vigore, stamina, nervi) per azioni faticose "
        "o tensione; quelle di potere (mana) per abilità speciali; scala la vita/salute per "
        "ferite o cure. Usa variazioni piccole (di solito 1) e solo quando l'azione le giustifica."
    )
    if outcome is None:
        outcome_line = "L'azione era libera (nessun tiro): narra ciò che accade in modo naturale."
    else:
        outcome_line = (
            f"Esito del tiro: «{outcome}». "
            "Fai sì che la narrazione rispetti questo esito "
            "(successo = riesce; successo con complicazione = riesce ma con un costo; "
            "fallimento = non riesce, e qualcosa peggiora — ma la storia avanza)."
        )
    user = (
        f"{_state_block(ctx)}\n\n"
        f"Azione del giocatore: «{ctx.player_action}»\n"
        f"{outcome_line}\n\n"
        "Rispondi SOLO con un oggetto JSON con questa forma (ometti i campi non pertinenti):\n"
        "{\n"
        '  "narration": string,\n'
        '  "new_summary": string|null,\n'
        '  "changes": {\n'
        '    "resource_deltas": {nome_risorsa: intero},\n'
        '    "conditions_add": [string], "conditions_remove": [string],\n'
        '    "relationship_changes": [{"name": string, "kind": string, "affinity_delta": intero}],\n'
        '    "new_items": [{"name": string, "description": string, "quantity": intero}],\n'
        '    "removed_items": [string],\n'
        '    "new_objectives": [{"title": string, "description": string}],\n'
        '    "completed_objectives": [string],\n'
        '    "memory": string|null, "memory_importance": numero 0..1\n'
        "  }\n"
        "}\n"
        "Usa solo nomi di risorse già esistenti. Salva in 'memory' un ricordo solo se l'evento è saliente."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
