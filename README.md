<p align="center">
  <img src="assets/aedo_256.png" width="140" alt="Aedo" />
</p>

<h1 align="center">Aedo 🎭</h1>

> Un cantastorie AI per avventure di ruolo narrative — su **qualsiasi** genere.

Aedo non è legato al fantasy o a D&D. Crei una campagna su quello che vuoi —
noir investigativo, cyberpunk, horror psicologico, fantascienza, romance
contemporaneo — e un'intelligenza artificiale fa da **Dungeon Master**: narra
la storia, la fa evolvere in base alle tue scelte e tiene traccia di tutto.

Si gioca da **Discord** (ogni campagna nel suo canale dedicato) e si consulta
lo stato della campagna da una **dashboard web**.

## Idea in tre strati

1. **Motore universale** — uguale per ogni campagna: entità, relazioni, obiettivi,
   memoria e un meccanismo unico di risoluzione delle azioni
   (azione rischiosa → tiro → esito a 3 gradi: successo / successo con
   complicazione / fallimento). Non un "combat system": un meccanismo che vale
   per un colpo di spada come per un interrogatorio o una dichiarazione d'amore.
2. **Campaign Blueprint** — il "ruleset" di *quella* campagna: genere, tono,
   quali attributi contano, quanto mostrare le meccaniche, persino il dado. Il
   genere è un **dato**, non codice. Si parte da un template (noir, fantasy,
   cyberpunk) o si crea da zero.
3. **Il Narratore (Aedo)** — interpreta cosa scrivi, decide se l'azione richiede
   un tiro, narra l'esito e propone i cambiamenti di stato; il codice li applica
   in modo controllato (lo stato non lo scrive mai l'AI).

## Come funziona un turno

```
Scrivi un'azione in linguaggio naturale
        │
        ▼
Il narratore valuta: è rischiosa?  ──no──▶  narra subito (1 chiamata)
        │ sì
        ▼
Il motore tira (attributo + dado vs difficoltà) → esito a 3 gradi
        ▼
Il narratore racconta l'esito e propone i cambiamenti
        ▼
Il codice applica stato + salva il ricordo + indicizza per la memoria
```

## Memoria a due livelli (RAG)

- **Strutturata** (database): inventario, relazioni/affinità, quest, condizioni.
  Fatti certi, mai dimenticati.
- **Narrativa** (semantica): i ricordi vissuti, richiamati quando rilevanti — così
  la storia resta coerente anche dopo molte sessioni. Recupero **ibrido**:
  similarità semantica (embedding locali) + nomi propri + priorità ai personaggi
  in scena. La similarità è calcolata in Python (a volumi di una campagna è
  istantanea); niente estensioni native.

## Struttura del progetto

```
aedo/
├── config.py          # configurazione da .env
├── play.py            # playground da terminale
├── core/
│   ├── models/        # entità (Campaign, Blueprint, Character, Item, …)
│   ├── resolution/    # motore: dadi + esito a 3 gradi
│   ├── narrator/      # interfaccia AI + provider OpenRouter + finto
│   ├── memory/        # embedding locali + recupero ibrido
│   └── services/      # game loop, creazione campagna, applicazione stato
├── templates/         # blueprint di genere predefiniti
├── storage/           # SQLAlchemy + SQLite
├── bots/discord/      # bot discord.py
├── api/               # API FastAPI (sola lettura)
└── web/               # dashboard React + Vite
tests/                 # 70 test (pytest)
```

## Stack

| Parte | Tecnologia |
|---|---|
| Core / engine | Python 3.11+ |
| Database | SQLite (via SQLAlchemy) → migrabile a PostgreSQL |
| Narratore AI | OpenRouter (API OpenAI-compatibile), modello configurabile |
| Memoria narrativa | embedding locali (`sentence-transformers`), cosine in Python |
| Bot | `discord.py` |
| API | FastAPI |
| Web | React + Vite |

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate                    # Windows (POSIX: source .venv/bin/activate)
pip install -e ".[dev,narrator,memory,discord,api]"
copy .env.example .env                     # poi compila le chiavi
```

Le dipendenze sono divise in gruppi (`narrator`, `memory`, `discord`, `api`):
puoi installare solo ciò che ti serve. Il narratore **finto** non richiede nulla
di tutto questo e permette di provare il gioco senza chiavi.

### Variabili d'ambiente (`.env`)

| Variabile | A cosa serve |
|---|---|
| `OPENROUTER_API_KEY` | chiave OpenRouter (narratore reale) |
| `AEDO_MODEL` | modello DM (default `deepseek/deepseek-v4-flash`) |
| `DISCORD_TOKEN` | token del bot Discord |
| `AEDO_DB_PATH` | percorso del database (default `data/aedo.db`) |
| `AEDO_EMBEDDING_MODEL` | modello di embedding locale per la memoria |

## Avvio

**Playground da terminale** (anche senza chiavi, col narratore finto):

```bash
python -m aedo.play --template noir --name Sam --narrator fake
```

**Bot Discord:**

1. Crea un'app su https://discord.com/developers/applications
2. Sezione **Bot** → copia il token → in `.env` come `DISCORD_TOKEN`
3. Abilita il **Message Content Intent**
4. Invita il bot (OAuth2 → scopes `bot` + `applications.commands`)
5. Avvia: `python -m aedo.bots.discord`
6. Nel server: `/nuova-campagna`, poi scrivi nel canale creato per giocare.

**Dashboard web** (due processi):

```bash
python -m aedo.api                          # API su http://127.0.0.1:8000
cd aedo/web && npm install && npm run dev   # dashboard su http://localhost:5173
```

## Test

```bash
pytest
```

I test girano col narratore e l'embedder **finti** (deterministici): nessuna
chiave né rete, nessun modello pesante da caricare.

## Note

- Lo schema del database evolve senza migrazioni (ancora niente Alembic): durante
  lo sviluppo, dopo un cambio di schema, rigenera il db con `del data\aedo.db`.
- L'architettura del narratore è provider-agnostic: aggiungere un modello locale
  (es. Ollama) è solo un nuovo provider.

## Licenza

MIT — vedi [LICENSE](LICENSE).
