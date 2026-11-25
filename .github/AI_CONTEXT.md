# AI_CONTEXT

## Purpose

`library-tracker` is a private Python integration project connecting READO reading lists with the Stadtbibliothek Bremen catalog.

READO is the source of truth for reading state. The daily `sync` command caches bibliographic metadata, maps wishlist works to German print editions, searches those ISBNs in the Bremen catalog, keeps the library Merkliste in sync and sends a Telegram overview. Personal runs happen in a separate private runner repository; the public repository must never contain personal data.

## Current architecture

- `clients/` — external systems (Bremen library, READO, Open Library, Google Books, DNB, Telegram)
- `parsers/` — deterministic Bremen HTML parsing
- `repositories/` — SQLite reads/writes grouped by responsibility
- `services/` — multi-step workflows
- `cli.py` — command routing and compact output only
- `database.py` — schema and migrations
- `models.py` — typed contracts
- `isbn.py` — shared ISBN normalization

## Current READO workflow

Configured list types:

- wishlist
- tbr
- reading
- completed
- abandoned

Books on tbr/reading/completed/abandoned (and not on the wishlist) are removed from the library Merkliste. List membership is stored separately from bibliographic cache data. Moving a book between lists must not delete resolved work/edition metadata.

## Current metadata workflow

Only active wishlist books get metadata.

1. unresolved wishlist ISBNs → Open Library
2. Open Library `not_found` → Google Books fallback
3. active wishlist works → Open Library editions
4. store German and English editions
5. exclude explicit ebook/audio formats
6. Deutsche Nationalbibliothek for German editions and translations
7. Bremen matching priority:
   - original READO ISBN
   - German confirmed print ISBN-13 (Open Library)
   - German print ISBN-13 (DNB)
   - German unknown-format ISBN-13
   - English edition
8. catalog search is incremental (`catalog_searches`), hits are stored in `library_matches`

## Daily pipeline (`services/sync.py`)

```text
READO lists (one step per list)
→ metadata for new wishlist books
→ incremental catalog search
→ read Merkliste
→ remove finished books
→ add found wishlist books (only "in die Merkliste")
→ fresh-session re-read
→ Telegram overview
```

Failing steps become warnings; the remaining steps still run. See `ROADMAP.md` for planned features.

## Hard safety constraint

Never automatically create a paid reservation (`Vormerkung`). Paid reservations cost money.

If the interface contains terms such as `Vormerkung`, `Gebühren`, or `1,- Euro`, no automated paid action may be triggered.

Free branch orders may be implemented only in a later phase and only behind explicit user confirmation.

## Coding principles

- simple readable functions
- no unnecessary class hierarchy
- one client class per stateful external session is acceptable
- keep HTTP, parsing, persistence and orchestration separated
- cache external metadata; do not repeatedly bulk-query resolved data
- low request volume and deliberate delays
- full type hints and `mypy`
- behavioral `pytest` tests with mocked external requests
- temporary SQLite databases in tests
- never commit credentials, API keys or the local database
