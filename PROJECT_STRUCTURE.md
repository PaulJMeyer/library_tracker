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
│   ├── progress.py
│   ├── titles.py
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── dnb.py
│   │   ├── library.py
│   │   ├── reado.py
│   │   ├── openlibrary.py
│   │   ├── googlebooks.py
│   │   └── telegram.py
│   ├── parsers/
│   │   ├── __init__.py
│   │   └── library.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── availability.py
│   │   ├── reado.py
│   │   ├── metadata.py
│   │   ├── matching.py
│   │   ├── library_matches.py
│   │   ├── merkliste_removals.py
│   │   └── telegram_overviews.py
│   └── services/
│       ├── __init__.py
│       ├── library_scrape.py
│       ├── reado_sync.py
│       ├── metadata.py
│       ├── library_matching.py
│       ├── merkliste_cleanup.py
│       └── sync.py
├── tests/
│   ├── conftest.py
│   ├── test_cli.py
│   ├── test_database.py
│   ├── test_dnb.py
│   ├── test_entrypoint.py
│   ├── test_googlebooks.py
│   ├── test_telegram.py
│   ├── test_telegram_overviews.py
│   ├── test_isbn.py
│   ├── test_library_client.py
│   ├── test_merkliste_cleanup.py
│   ├── test_merkliste_sync.py
│   ├── test_library_parsers.py
│   ├── test_openlibrary.py
│   ├── test_output.py
│   ├── test_reado.py
│   ├── test_repositories.py
│   └── test_services.py
├── .github/
│   ├── AI_CONTEXT.md
│   └── workflows/
│       └── ci.yml
├── docs/
│   └── private-runner/
│       ├── README.md
│       └── daily.yml
├── data/
│   └── library_tracker.db
├── .env
├── .gitignore
├── pyproject.toml
├── README.md
├── PROJECT_STRUCTURE.md
└── ROADMAP.md
```

`data/`, `.env`, `results.md`, coverage artifacts and local IDE files are ignored by Git.

## Dependency direction

```text
cli.py
  ↓
services/
  ↓              ↓
clients/     repositories/
  ↓              ↓
parsers/        SQLite

shared: config.py, isbn.py, models.py, database.py, output.py, progress.py, titles.py
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

### `progress.py`

`log()`: progress messages of long-running steps go to stderr, so stdout stays for results. Services take it as the default `progress`/`log` callback; tests pass their own.

### `titles.py`

Title helpers shared by the catalog, Open Library and DNB code:

- `strip_sort_markers()`: removes the catalog's non-sorting markers ("¬Der¬ Fremde")
- `normalize_title()`: loose comparison for metadata matching (drops subtitles after ':' or ' - ')
- `merkliste_title_key()`: when two catalog titles count as the same book (overview merging, second-wishlist section, Merkliste add and cleanup). Keeps series titles like "Reihe - Teil 1" apart, drops subtitles after ':' and a leading article. Copy numbers are compared first wherever they are known.

### `models.py`

Typed contracts shared between layers. Important groups:

- library: `Copy`, `Item`, `Loan`, `AvailabilitySnapshot`
- library wish list: `MemorizeEntry`, `MemorizePage`
- READO: `ReadoListEntry`, `ReadoListSyncResult`, `ReadoListType`
- metadata: Open Library and Google Books resolution/edition structures
- matching: `LibraryIsbnCandidate`, `LibraryMatchAttempt`, `LibraryMatchResult`

### `database.py`

Owns SQLite infrastructure only:

- connection creation (`get_connection()`, path `data/library_tracker.db` unless given)
- `open_database()`: context manager used by services and the CLI; opens, initializes and closes the database
- foreign-key activation
- complete schema initialization
- migration from the legacy `reado_books.on_wishlist` column to list memberships
- rebuild of `library_matches`/`catalog_editions` when their status CHECK constraint is older than the newest status

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

### `clients/dnb.py`

Deutsche Nationalbibliothek catalog via SRU (MARC21-xml):

- ISBN lookup (`num=`) for title and authors
- title/author search for German print editions, filtering out e-books, audio and other languages
- ISBN-10 values are converted to ISBN-13

### `clients/telegram.py`

Sends the daily overview to a Telegram chat:

- HTML-formatted `sendMessage` calls
- splits long overviews at line breaks to respect Telegram's 4096-character limit
- error messages never include the bot token

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

- query unresolved ISBNs of active wishlist books (other lists need no metadata)
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

### `repositories/library_matches.py`

Stores the incremental catalog state:

- `catalog_searches`: every ISBN searched in the Bremen catalog, with hit URL and time
- `library_matches`: the first catalog hit per READO wishlist book and its Merkliste status (`added`, `already_listed`, `failed`, `needs_review`, `ebook`: only e-books of the online branch, never added; such Merkliste entries are removed)
- `catalog_editions`: every catalog edition found per wishlist book, with catalog title, copy numbers (identify the catalog record on the Merkliste) and Merkliste status

## Services

### `services/library_scrape.py`

Orchestrates the legacy library-wishlist workflow:

1. log in
2. read all library wish-list pages
3. load and parse availability
4. persist all scraped copies/snapshots
5. sort visible items (fully loaned titles are hidden, not removed)
6. load current loans

### `services/reado_sync.py`

Reads all requested READO lists **before** modifying SQLite, preventing a transient list-loading failure from being mistaken for an empty list. Then it synchronizes memberships in one local database session.

### `services/metadata.py`

Orchestrates cached external metadata work:

- Open Library resolution for unresolved wishlist ISBNs only
- Google Books fallback for Open Library `not_found` results only
- Open Library edition sync for active wishlist works only

### `services/library_matching.py`

- direct catalog search for one ISBN
- prioritized matching for one active READO wishlist book
- `match_wishlist_books`: incremental search for all editions of all wishlist books (15 new ISBNs per book and run, books without a hit first, at most 150 ISBNs per run for further editions, recheck misses after 30 days)
- `add_matches_to_merkliste`: open each found edition's catalog hit and follow only its "in die Merkliste" link; skips catalog records already on the Merkliste (copy numbers, title as fallback) and e-book-only records (status `ebook`)
- `build_match_report`: diagnostic report from stored state

### `services/merkliste_cleanup.py`

Removes e-book-only entries (online branch) from the Merkliste, and books that are on a finished READO list (TBR, reading, completed, abandoned) and not on the wishlist from the Merkliste. It removes every edition: Merkliste entries matching a stored catalog title or copy number of any found edition, otherwise it uses one catalog search per book (30 per run). Each book is checked once (`merkliste_removals`); failed removals are retried, and a book that returns to a wishlist is put on the Merkliste again and can be removed again later. Entries that belong to a book still on a wishlist are never removed.

### `services/sync.py`

Runs the full pipeline step by step (READO, metadata, catalog search, Merkliste read/clean up/add). A failing step is recorded as a warning and the remaining steps still run.

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

Scheduled, authenticated runs live in a separate private repository. `docs/private-runner/daily.yml` is the workflow template: it installs the package from this repository, restores and uploads the SQLite artifact privately and keeps `results.md` out of Git.

The planned full automation pipeline is documented in `ROADMAP.md`.
