# AI_CONTEXT

## Purpose

`library-tracker` is a private Python integration project connecting READO reading lists with the Stadtbibliothek Bremen catalog.

READO is intended to become the source of truth for reading state. The application caches bibliographic metadata, maps works to German print editions, matches those ISBNs against the Bremen catalog, tracks availability and will later send change notifications (initially likely e-mail).

## Current architecture

- `clients/` — external systems (Bremen library, READO, Open Library, Google Books)
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

List membership is stored separately from bibliographic cache data. Moving a book between lists must not delete resolved work/edition metadata.

## Current metadata workflow

1. unresolved READO ISBNs → Open Library
2. Open Library `not_found` → Google Books fallback
3. active wishlist works → Open Library editions
4. store German and English editions
5. exclude explicit ebook/audio formats
6. Bremen matching priority:
   - original READO ISBN
   - German confirmed print ISBN-13
   - German unknown-format ISBN-13

A real alternative-edition Bremen match has been verified end to end.

## Intended end state

```text
READO sync
→ cached metadata/work/editions
→ Bremen catalog matching
→ library-wishlist/availability reconciliation
→ change detection
→ user update (e.g. daily or changed-only e-mail)
```

Books in TBR, reading or completed should no longer be treated as active library-wishlist candidates, but their bibliographic metadata remains cached.

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
