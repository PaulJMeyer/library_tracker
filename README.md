# Library Tracker

`library-tracker` is a private Python application that connects reading data from **READO** with the online catalog of **Stadtbibliothek Bremen**.

The project started as an authenticated scraper for the library's personal wish list and has grown into a small integration pipeline: READO lists are synchronized to SQLite, ISBNs are resolved to works and editions, German print ISBNs can be matched against the Bremen catalog, and library availability history is stored locally.

## Current capabilities

### Stadtbibliothek Bremen

- authenticated login with `requests.Session`, cookies and CSId
- read the personal library wish list across multiple pages
- parse titles, physical copies, branches, status and due dates
- distinguish Zentralbibliothek from branch libraries
- classify titles as `ausleihbar`, `bestellbar`, `entliehen`, `bestellt` or `unbekannt`
- read current loans from the account page
- store copy metadata and availability snapshots in SQLite
- search the catalog by ISBN

### READO

Public READO lists can be synchronized independently:

- `wishlist`
- `tbr`
- `reading`
- `completed`

List membership is stored separately from the bibliographic book cache, so moving a book between READO lists does not discard metadata that has already been resolved.

### Bibliographic resolution

- Open Library resolves READO ISBNs to works
- unresolved Open Library ISBNs can fall back to Google Books
- Open Library editions are cached for active wishlist works
- German and English editions are retained
- explicit ebook/audio formats are excluded from print candidates
- German ISBN-13 candidates are prioritized as:
  1. original READO ISBN
  2. confirmed German print edition
  3. German edition with unknown physical format

A real end-to-end match is already verified where the original READO ISBN was not found in Bremen but an alternative German edition of the same work was.

## CLI

```bash
# Existing library wish-list scrape + availability history
python -m library_tracker
python -m library_tracker scrape

# Availability history for one physical copy
python -m library_tracker history <media_number>

# READO
python -m library_tracker reado-wishlist
python -m library_tracker reado-sync
python -m library_tracker reado-sync --headless

# Bibliographic metadata
python -m library_tracker openlibrary-resolve
python -m library_tracker googlebooks-resolve
python -m library_tracker openlibrary-editions

# Bremen catalog
python -m library_tracker library-search <isbn>
python -m library_tracker library-match <reado_isbn>
```

`library-match` checks one active READO wishlist entry and stops at the first catalog hit among its prioritized ISBN candidates.

## Architecture

The refactor separates external systems, parsing, persistence and orchestration:

```text
CLI
 ↓
services/
 ├── library_scrape
 ├── reado_sync
 ├── metadata
 └── library_matching
 ↓
clients/                    repositories/
 ├── library               ├── availability
 ├── reado                 ├── reado
 ├── openlibrary           ├── metadata
 └── googlebooks           └── matching
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
READO_TBR_URL=...
READO_READING_URL=...
READO_COMPLETED_URL=...

OPENLIBRARY_CONTACT_EMAIL=...
GOOGLE_BOOKS_API_KEY=...
```

## Development checks

```bash
mypy
python -m pytest --cov=library_tracker --cov-report=term-missing -v
```

The refactored test suite favors focused behavioral tests over maintaining a specific coverage percentage.

## Automation

GitHub Actions currently provides:

- CI with `mypy` and `pytest`
- a scheduled authenticated library scrape
- restoration/upload of the SQLite database as a workflow artifact
- automated `results.md` updates

The next automation milestone is a single scheduled pipeline that synchronizes READO, resolves only new metadata, matches wishlist books against the library, compares the result with the previous state and sends a concise update when something relevant changes.

## Project goal

The intended end state is:

```text
READO
  ↓
wishlist / tbr / reading / completed
  ↓
work + edition cache
  ↓
German print ISBN candidates
  ↓
Stadtbibliothek Bremen catalog
  ↓
library wishlist / availability state
  ↓
change detection
  ↓
mobile-friendly update (for example e-mail)
```

Books that move from the READO wishlist into TBR, reading or completed should no longer be treated as library-wishlist candidates. Bibliographic data should remain cached so it does not need to be fetched again.

## Safety and scope

This is a private tool for a personal library account.

Paid reservations (`Vormerkung`) must **never** be triggered automatically. Free branch orders may be considered later, but only behind explicit user confirmation. Public deployment and high-volume scraping are not goals of the project.
