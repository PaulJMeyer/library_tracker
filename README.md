# Library Tracker

`library-tracker` is a private Python application that connects reading data from **READO** with the online catalog of **Stadtbibliothek Bremen**.

Once a day it reads the READO wishlist, finds German print editions of every wished-for book, searches them in the Bremen catalog, keeps the library *Merkliste* in sync (adds found books, removes books that were read or abandoned) and sends a short Telegram overview of what can be borrowed in the central library or ordered from another branch.

```text
READO lists ──► metadata (Open Library, Google Books, DNB) ──► German ISBN candidates
                                                                   │
Telegram ◄── availability overview ◄── library Merkliste ◄── Bremen catalog search
```

The project started as an authenticated scraper for the library's personal wish list and grew step by step into this pipeline. Personal data never touches the public repository: the daily run happens in a separate private repository (see [Automation](#automation)).

## Current capabilities

### Stadtbibliothek Bremen

- authenticated login with `requests.Session`, cookies and CSId
- read the personal library wish list across multiple pages
- parse titles, page counts (from the catalog's extent field), physical copies, branches, status and due dates
- distinguish Zentralbibliothek from branch libraries
- classify titles as `ausleihbar` (free copy in the Zentralbibliothek), `bestellbar` (free copy in another branch that can be ordered; prison library and reference-only copies excluded), `entliehen`, `bestellt` or `unbekannt`
- read current loans from the account page
- store copy metadata and availability snapshots in SQLite
- search the catalog by ISBN, incrementally across runs (every searched ISBN is stored)
- add wishlist books found in the catalog to the library Merkliste (free "in die Merkliste" link only)

### READO

Public READO lists can be synchronized independently:

- `wishlist`
- `tbr`
- `reading`
- `completed`
- `abandoned` (Abgebrochen)

List membership is stored separately from the bibliographic book cache, so moving a book between READO lists does not discard metadata that has already been resolved.

### Bibliographic resolution

- Open Library resolves READO ISBNs to works
- unresolved Open Library ISBNs can fall back to Google Books
- Open Library editions are cached for active wishlist works
- German and English editions are retained
- explicit ebook/audio formats are excluded from print candidates
- editions without a language tag count as German when their ISBN starts with 978-3
- ISBN-10-only editions get a derived ISBN-13
- Google-Books-only ISBNs are linked to an Open Library work by title/author search
- the Deutsche Nationalbibliothek (public SRU interface, no key) is searched by ISBN and by
  title/author for German print editions, which covers German titles and translations that
  Open Library and Google Books miss
- catalog ISBN candidates are prioritized as:
  1. original READO ISBN
  2. confirmed German print edition (Open Library)
  3. German print edition (DNB)
  4. German edition with unknown physical format
  5. English edition

A real end-to-end match is already verified where the original READO ISBN was not found in Bremen but an alternative German edition of the same work was.

## CLI

```bash
# Full pipeline: READO -> metadata -> catalog -> Merkliste -> overview
python -m library_tracker sync
python -m library_tracker sync --telegram

# Library wish-list scrape + availability history
python -m library_tracker
python -m library_tracker scrape
python -m library_tracker scrape --telegram   # also send the overview via Telegram
python -m library_tracker telegram-test

# Availability history for one physical copy
python -m library_tracker history <media_number>

# READO
python -m library_tracker reado-wishlist
python -m library_tracker reado-sync
python -m library_tracker reado-sync --headless

# Bibliographic metadata
python -m library_tracker openlibrary-resolve
python -m library_tracker googlebooks-resolve
python -m library_tracker openlibrary-link-titles     # title/author search for Google-Books-only ISBNs
python -m library_tracker openlibrary-editions
python -m library_tracker openlibrary-editions --refresh   # reload editions after parser improvements
python -m library_tracker dnb-editions          # German print editions from the Deutsche Nationalbibliothek

# Bremen catalog
python -m library_tracker library-search <isbn>
python -m library_tracker library-match <reado_isbn>
python -m library_tracker match-books        # search up to 15 new ISBNs per wishlist book
python -m library_tracker merkliste-add      # add found books to the library Merkliste
python -m library_tracker merkliste-cleanup  # remove books on finished READO lists from the Merkliste

# Diagnose: why do wishlist books (not) match? (reads stored state only)
python -m library_tracker match-report
```

`library-match` checks one active READO wishlist entry and stops at the first catalog hit among its prioritized ISBN candidates. `match-books` works through all active wishlist books, stores every searched ISBN in `catalog_searches` and continues with the next ISBNs on the following run, so books with many editions are covered over several runs. ISBNs without a hit are searched again after 30 days. `merkliste-add` skips titles that are already on the Merkliste and retries failed additions on the next run. If the hit is an alternative edition (not the exact READO ISBN) and a single volume of a multi-volume edition ("Band 3", "Bd. 2", "Vol. 1"), it is not added but reported for manual review. Fully loaned Merkliste entries are no longer removed automatically. `merkliste-cleanup` removes books that are on a finished READO list (TBR, reading, completed, abandoned) and not on a wishlist; each book is checked once (state in `merkliste_removals`).

## Architecture

The refactor separates external systems, parsing, persistence and orchestration:

```text
CLI
 ↓
services/
 ├── library_scrape
 ├── reado_sync
 ├── metadata
 ├── library_matching
 └── sync (full pipeline)
 ↓
clients/                    repositories/
 ├── library               ├── availability
 ├── reado                 ├── reado
 ├── openlibrary           ├── metadata
 ├── googlebooks           ├── matching
 ├── dnb                   └── library_matches
 └── telegram
        ↓                         ↓
external services               SQLite

parsers/library.py handles Bremen-specific HTML parsing.
```

Shared ISBN normalization lives in `isbn.py`; SQLite schema/migrations remain in `database.py`; `models.py` contains the typed structures passed between layers.

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for the detailed module map.

## Installation

```bash
python -m pip install -e ".[dev]"
```

For READO browser automation install the Playwright Chromium runtime once:

```bash
playwright install chromium
```

Local configuration belongs in `.env` and is ignored by Git:

```text
LIBRARY_USERNAME=...
LIBRARY_PASSWORD=...

READO_WISHLIST_URL=...
# optional: wishlist of a second READO account, shown in its own Telegram section
READO_SECOND_WISHLIST_URL=...
READO_SECOND_WISHLIST_NAME=...
READO_TBR_URL=...
READO_READING_URL=...
READO_COMPLETED_URL=...
READO_ABANDONED_URL=...

OPENLIBRARY_CONTACT_EMAIL=...
GOOGLE_BOOKS_API_KEY=...

TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

## Development checks

```bash
mypy
python -m pytest --cov=library_tracker --cov-report=term-missing -v
```

The refactored test suite favors focused behavioral tests over maintaining a specific coverage percentage.

## Automation

The public repository only runs CI (`mypy` and `pytest`) on pushes and pull requests.

Scheduled runs that use personal credentials or produce personal data (library scrape, SQLite database, results overview) run in a separate private repository, so logs and artifacts are never public. See [docs/private-runner](docs/private-runner/README.md) for the workflow template and setup.

The scheduled pipeline (`sync --telegram`) runs these steps once a day; every step is cached, so a normal run only does new work:

1. read the READO lists (each list separately, one failing list does not block the others)
2. resolve metadata and editions for new wishlist books only
3. search the catalog for up to 15 not yet searched ISBNs per wishlist book
4. read the library Merkliste
5. remove books that moved to a finished READO list
6. add newly found wishlist books
7. send the Telegram overview (available, orderable, added, removed, warnings; books only on the optional second wishlist get their own section)

Planned features are listed in the [roadmap](ROADMAP.md).

## Safety and scope

This is a private tool for a personal library account.

Paid reservations (`Vormerkung`) must **never** be triggered automatically. Free branch orders may be considered later, but only behind explicit user confirmation. Public deployment and high-volume scraping are not goals of the project.
