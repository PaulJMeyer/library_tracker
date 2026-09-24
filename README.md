# Library Tracker

A Python application that analyzes a personal wish list from the Stadtbibliothek Bremen online catalog, tracks the availability of individual library copies, and stores availability history in SQLite.

The project combines authenticated web requests, HTML parsing, typed domain models, automated tests, scheduled GitHub Actions workflows, and relational persistence.

---

## Features

### Library account and wish list

- Login to the online catalog with session handling, cookies, and CSId
- Read the personal wish list across multiple pages
- Fetch detail pages for every saved title
- Detect multiple copies per title
- Distinguish the central library from branch libraries
- Parse the current status of each copy
- Extract due dates from status text
- Read currently borrowed items from the account overview
- Remove fully checked-out titles from the wish list after processing

Supported status categories:

- `ausleihbar` — available at the central library
- `bestellbar` — available for free transfer from a branch
- `entliehen` — checked out
- `bestellt` — already ordered
- `unbekannt` — no known status classification

### SQLite availability history

Each detected copy is identified by its `media_number` and stored in SQLite.

The database currently contains two core tables:

- `copies` — current metadata for each known library copy
- `availability_snapshots` — timestamped historical availability records

Every scrape can therefore add a new historical state for a copy while keeping the current copy metadata up to date.

The default local database path is:

```text
data/library_tracker.db
```

The database is intentionally excluded from Git.

### Command-line interface

Run the normal scrape:

```bash
python -m library_tracker
```

or explicitly:

```bash
python -m library_tracker scrape
```

Show the stored history for one library copy:

```bash
python -m library_tracker history <media_number>
```

Example:

```bash
python -m library_tracker history 123456789
```

The installed package also exposes the `library-tracker` console command.

---

## Architecture

```text
Library catalog
      ↓
HTTP client / login
      ↓
Wishlist and account handling
      ↓
HTML parser
      ↓
Typed Python models
      ↓
Repository layer
      ↓
SQLite
      ↓
CLI / results.md
```

Main responsibilities are separated into dedicated modules:

- HTTP communication
- authentication
- wish-list handling
- HTML parsing
- domain models
- output formatting
- database setup
- repository queries and persistence
- CLI routing
- application orchestration

---

## Engineering and quality

- Installable Python package via `pyproject.toml`
- Full type hints checked with `mypy`
- Tests written with `pytest`
- Test coverage currently around **99%**
- HTTP and login behavior tested with mocked external requests
- SQLite tests use temporary databases instead of the real local database
- Continuous Integration with GitHub Actions
- CI runs `mypy` and `pytest` with coverage
- Feature/fix development via branches and pull requests
- Scheduled scrape workflow using GitHub Actions
- Credentials stored in GitHub Secrets rather than source control

---

## Installation

Create and activate a virtual environment, then install the package including development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Create a local `.env` file:

```text
LIBRARY_USERNAME=...
LIBRARY_PASSWORD=...
```

The `.env` file is ignored by Git.

---

## Development checks

Run static type checking:

```bash
mypy
```

Run the test suite with coverage:

```bash
python -m pytest --cov=library_tracker --cov-report=term-missing -v
```

---

## GitHub Actions

### CI

The CI workflow checks the codebase on pushes and pull requests with:

- `mypy`
- `pytest`
- coverage reporting

### Scheduled scrape

The scheduled workflow runs the tracker automatically and updates `results.md`.

Persistent SQLite history across independent GitHub Actions runners is the next infrastructure step. The local SQLite database already supports historical snapshots, but a fresh Actions runner does not retain local files automatically.

---

## Current development focus

- Persist SQLite history across scheduled GitHub Actions runs
- Store a new snapshot only when relevant availability data changes
- Add database summary/statistics queries
- Continue improving CLI access to stored history

Later possibilities include:

- filtering by authors or genres
- support for multiple accounts
- a Streamlit dashboard for historical availability data

---

## Scope

This project is intended for private use with a personal library account.

Not planned:

- automatic paid reservations
- bulk or mass requests
- public deployment as a hosted scraping service
