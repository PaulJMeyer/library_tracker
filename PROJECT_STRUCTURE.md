# Project Structure – Library Tracker

This document describes the refactored architecture and the responsibility of each module.

## Directory tree

```text
library_tracker/
├── library_tracker/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py
│   ├── database.py
│   ├── isbn.py
│   ├── models.py
│   ├── output.py
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── library.py
│   │   ├── reado.py
│   │   ├── openlibrary.py
│   │   └── googlebooks.py
│   ├── parsers/
│   │   ├── __init__.py
│   │   └── library.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── availability.py
│   │   ├── reado.py
│   │   ├── metadata.py
│   │   └── matching.py
│   └── services/
│       ├── __init__.py
│       ├── library_scrape.py
│       ├── reado_sync.py
│       ├── metadata.py
│       └── library_matching.py
├── tests/
│   ├── conftest.py
│   ├── test_cli.py
│   ├── test_database.py
│   ├── test_entrypoint.py
│   ├── test_googlebooks.py
│   ├── test_isbn.py
│   ├── test_library_client.py
│   ├── test_library_parsers.py
│   ├── test_openlibrary.py
│   ├── test_output.py
│   ├── test_reado.py
│   ├── test_repositories.py
│   └── test_services.py
├── .github/
│   ├── AI_CONTEXT.md
│   └── workflows/
│       ├── ci.yml
│       └── scrape.yml
├── data/
│   └── library_tracker.db
├── .env
├── .gitignore
├── pyproject.toml
├── README.md
├── PROJECT_STRUCTURE.md
└── ROADMAP.md
```

`data/`, `.env`, coverage artifacts and local IDE files are ignored by Git.

## Dependency direction

```text
cli.py
  ↓
services/
  ↓              ↓
clients/     repositories/
  ↓              ↓
parsers/        SQLite

shared: config.py, isbn.py, models.py, database.py, output.py
```

The important rule is that the CLI routes commands but does not contain the business workflows. External HTTP details live in clients; SQL lives in repositories; multi-step operations live in services.

## Core modules

### `cli.py`

The public command-line router. It defines commands, delegates to services/repositories and prints compact summaries. The previous large command implementation was split so the CLI no longer owns metadata resolution, READO synchronization or library matching logic.

### `config.py`

Central configuration boundary:

- loads `.env`
- defines READO list types and their environment variables
- provides `require_env()` and `get_reado_list_url()`
- stores external base URLs

### `isbn.py`

One shared `normalize_isbn()` implementation used by the library catalog, Open Library and Google Books clients.

### `models.py`

Typed contracts shared between layers. Important groups:

- library: `Copy`, `Item`, `Loan`, `AvailabilitySnapshot`
- library wish list: `MemorizeEntry`, `MemorizePage`
- READO: `ReadoListEntry`, `ReadoListSyncResult`, `ReadoListType`
- metadata: Open Library and Google Books resolution/edition structures
- matching: `LibraryIsbnCandidate`, `LibraryMatchAttempt`, `LibraryMatchResult`

### `database.py`

Owns SQLite infrastructure only:

- connection creation
- foreign-key activation
- complete schema initialization
- migration from the legacy `reado_books.on_wishlist` column to list memberships

The schema is created with one `executescript()` block rather than many repeated setup calls.

## Clients

### `clients/library.py`

One authenticated boundary for Stadtbibliothek Bremen. A `LibraryClient` contains the active `requests.Session` and CSId.

Responsibilities:

- login
- throttled GET/POST requests
- library wish-list pagination
- wish-list removal requests
- availability-page loading
- account-page loading
- ISBN catalog search

The client does not parse domain data itself; it delegates HTML interpretation to `parsers/library.py`.

### `clients/reado.py`

Playwright integration for public READO lists:

- validates READO list URLs
- scrolls dynamically loaded lists
- extracts ISBN-bearing book links
- deduplicates entries

### `clients/openlibrary.py`

Open Library integration:

- batch work resolution by ISBN
- exact ISBN fallback for missing/ambiguous batch results
- edition pagination
- language filtering (`de`, `en`)
- print/e-book/audio classification
- edition ISBN extraction

### `clients/googlebooks.py`

Fallback metadata lookup:

- API-key header authentication
- exact ISBN verification against returned identifiers
- retry/backoff for transient HTTP status codes
- normalized metadata result structures

## Parser

### `parsers/library.py`

All Bremen-specific HTML parsing lives in one place:

- CSId extraction
- wish-list form/entry parsing
- copy/status parsing
- title parsing
- account/loan parsing
- catalog-hit URL detection

Parsing functions are deterministic and do not issue network requests.

## Repositories

### `repositories/availability.py`

- upsert copy metadata
- store availability snapshots
- query complete copy history
- query latest snapshot

### `repositories/reado.py`

- persist READO books
- maintain independent active memberships for wishlist/TBR/reading/completed
- return newly discovered books and removed memberships

### `repositories/metadata.py`

- query unresolved READO ISBNs
- persist Open Library work resolutions
- select Google Books fallbacks
- persist Google Books metadata
- select unsynced wishlist works
- persist Open Library editions and sync markers

### `repositories/matching.py`

Builds the prioritized ISBN list for one active READO wishlist book:

1. original READO ISBN
2. German `confirmed` print ISBN-13
3. German `unknown`-format ISBN-13

Duplicates are removed and English editions remain cached but are not used for Bremen matching yet.

## Services

### `services/library_scrape.py`

Orchestrates the legacy library-wishlist workflow:

1. log in
2. read all library wish-list pages
3. load and parse availability
4. remove fully checked-out library-wishlist entries
5. persist all scraped copies/snapshots
6. sort visible items
7. load current loans

### `services/reado_sync.py`

Reads all requested READO lists **before** modifying SQLite, preventing a transient list-loading failure from being mistaken for an empty list. Then it synchronizes memberships in one local database session.

### `services/metadata.py`

Orchestrates cached external metadata work:

- Open Library resolution for unresolved READO ISBNs only
- Google Books fallback for Open Library `not_found` results only
- Open Library edition sync for active wishlist works only

### `services/library_matching.py`

- direct catalog search for one ISBN
- prioritized matching for one active READO wishlist book
- stop after the first Bremen catalog hit

This is the current verified end-to-end bridge between READO and the library.

## SQLite data model

Important tables:

- `copies`
- `availability_snapshots`
- `reado_books`
- `reado_list_memberships`
- `openlibrary_works`
- `bibliographic_resolutions`
- `openlibrary_editions`
- `openlibrary_edition_languages`
- `openlibrary_edition_isbns`
- `openlibrary_edition_syncs`
- `google_books_volumes`
- `google_books_identifiers`
- `google_books_resolutions`

Bibliographic cache and READO list membership are deliberately separate. A book may leave one READO list or move to another without losing resolved work/edition metadata.

## Tests

The refactored suite is smaller and more focused. It covers:

- ISBN normalization
- library parsers
- authenticated library client behavior
- READO link/list logic
- Open Library resolution and editions
- Google Books resolution
- schema creation/migration
- all repository areas
- service orchestration
- CLI routing and entry point
- console/Markdown output

SQLite tests use temporary databases. External requests are mocked; pytest does not make live API/catalog calls.

## Automation

`ci.yml` runs type checking and tests on pushes/PRs to `master`.

`scrape.yml` runs the existing authenticated library scrape on a schedule, restores the most recent SQLite artifact where possible, uploads the updated database and commits `results.md` when it changed.

The planned full automation pipeline is documented in `ROADMAP.md`.
