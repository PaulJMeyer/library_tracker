# Project Structure – Library Tracker

Overview of the current layout, module responsibilities, data flow, and testing strategy.

## Directory tree

```text
library_tracker/
├── library_tracker/
│   ├── __init__.py
│   ├── __main__.py
│   ├── account.py
│   ├── cli.py
│   ├── client.py
│   ├── database.py
│   ├── library_parser.py
│   ├── login.py
│   ├── main.py
│   ├── models.py
│   ├── output.py
│   ├── repository.py
│   └── wishlist.py
├── tests/
│   ├── __init__.py
│   ├── test_account.py
│   ├── test_cli.py
│   ├── test_client.py
│   ├── test_database.py
│   ├── test_entrypoint.py
│   ├── test_library_parser.py
│   ├── test_login.py
│   ├── test_main.py
│   ├── test_output.py
│   ├── test_repository.py
│   └── test_wishlist.py
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
└── ROADMAP.md
```

`data/` and SQLite database files are local runtime data and are ignored by Git.

---

## Architecture

The project separates external communication, parsing, orchestration, persistence, and presentation.

```text
cli / main
   ├── client / login
   ├── wishlist / account
   ├── library_parser
   ├── output
   └── database
          ↓
      repository
          ↓
        SQLite
```

More specifically:

- `client.py` handles reusable HTTP operations.
- `login.py` handles authentication.
- `wishlist.py` and `account.py` load account-specific pages.
- `library_parser.py` converts HTML into typed application data.
- `models.py` defines shared `TypedDict` structures.
- `database.py` owns SQLite connection and schema setup.
- `repository.py` owns persistence and queries.
- `main.py` orchestrates a scrape.
- `cli.py` routes user commands.
- `output.py` formats console and Markdown output.

---

## `client.py`

Central HTTP helper functions.

Responsibilities:

- URL construction
- GET requests
- POST requests
- request timeout
- request delay
- HTTP error propagation

External requests are mocked in the test suite.

---

## `login.py`

Handles the login process.

Responsibilities:

- create a requests session
- fetch the login page
- extract the CSId
- build the login payload
- submit credentials
- validate the resulting session

Credentials are read from environment variables.

---

## `wishlist.py`

Handles the personal wish list.

Responsibilities:

- load wish-list pages
- handle pagination
- extract entry UUIDs
- extract availability links
- remove selected entries from the wish list

---

## `account.py`

Handles the account overview.

Responsibilities:

- load the account page
- parse currently borrowed items
- extract borrowing and due dates
- extract branch information
- extract renewal notes

---

## `library_parser.py`

Converts availability HTML into typed application data.

Responsibilities:

- clean text
- extract title
- detect multiple copies per title
- extract media number, signature, and branch
- distinguish central library from branch libraries
- normalize per-copy status
- derive overall item status
- extract due dates
- create `Item` and `Copy` structures

---

## `models.py`

Defines the shared typed structures used throughout the application.

Current models include:

- `Copy`
- `Item`
- `Loan`
- `MemorizeEntry`
- `MemorizePage`
- `AvailabilitySnapshot`

The project uses `TypedDict` instead of generic dictionaries so that `mypy` can validate data passed between modules.

---

## `database.py`

Owns SQLite infrastructure rather than application-specific persistence logic.

Responsibilities:

- define the default database path
- create the database directory when needed
- open SQLite connections
- enable foreign-key enforcement
- initialize tables and indexes

Current schema:

### `copies`

Stores current metadata for each known physical copy.

Important fields:

- `media_number` — primary key
- `title`
- `signature`
- `branch`
- `is_central`
- `last_seen_at`

### `availability_snapshots`

Stores historical availability states.

Important fields:

- `id` — primary key
- `media_number` — foreign key to `copies`
- `checked_at`
- `status`
- `status_text`
- `due_date`

An index on `(media_number, checked_at)` supports history queries.

---

## `repository.py`

Owns application-specific persistence and read queries.

Responsibilities:

- upsert current copy metadata
- store availability snapshots
- retrieve the full history of one copy
- retrieve the newest snapshot of one copy

Current public functions:

```text
persist_items()
get_copy_history()
get_latest_snapshot()
```

This separation keeps database setup independent from business-oriented data access.

---

## `output.py`

Contains output and formatting logic.

Responsibilities:

- format individual copy lines
- create status summaries
- build the Markdown report
- write `results.md`
- print wish-list results to the console
- print borrowed items to the console

---

## `main.py`

Orchestrates one complete scrape.

Current flow:

1. Log in.
2. Load all wish-list pages.
3. Fetch availability details for every entry.
4. Parse title and copy information.
5. Collect all scraped items for persistence.
6. Remove fully checked-out titles from the wish list where applicable.
7. Initialize SQLite.
8. Persist copy metadata and availability snapshots.
9. Sort remaining wish-list items by status.
10. Print results and write `results.md`.
11. Load and print currently borrowed items.

`main.py` does not contain SQL directly.

---

## `cli.py`

Command-line interface built with the Python standard library.

Commands:

```bash
python -m library_tracker
python -m library_tracker scrape
python -m library_tracker history <media_number>
```

Responsibilities:

- argument parsing
- route the default/scrape command to `main.py`
- query SQLite history by media number
- format history output
- return meaningful exit codes

---

## `__main__.py`

Package entry point.

Running:

```bash
python -m library_tracker
```

delegates to the CLI.

---

## Tests

The test suite covers parsing, application logic, HTTP wrappers, login behavior, output, SQLite infrastructure, repository operations, CLI routing, and orchestration.

Important groups:

- `test_client.py` — HTTP helper behavior
- `test_login.py` — login parsing and mocked login flow
- `test_wishlist.py` — wish-list parsing, pagination, and removal
- `test_library_parser.py` — availability parsing and status logic
- `test_account.py` — account/loan parsing
- `test_output.py` — console and Markdown formatting
- `test_database.py` — SQLite connection and schema initialization
- `test_repository.py` — persistence and history queries
- `test_cli.py` — scrape/history command routing and output
- `test_main.py` — end-to-end orchestration with mocked boundaries
- `test_entrypoint.py` — package entry point

SQLite tests use temporary databases created by pytest.

The project currently reaches approximately 99% test coverage. Coverage is useful as a quality signal, but future development prioritizes meaningful behavioral tests rather than maintaining an arbitrary percentage.

---

## GitHub Actions

### `ci.yml`

Runs automated quality checks on pushes and pull requests.

Current checks:

- `mypy`
- `pytest`
- coverage

### `scrape.yml`

Runs the tracker on a schedule and can also be triggered manually.

Responsibilities:

- install the package
- read credentials from GitHub Secrets
- run the scraper
- update `results.md`

A future step is to persist the SQLite database between independent workflow runs so that the scheduled job also builds long-term history.

---

## Local configuration

### `.env`

Local credentials only:

```text
LIBRARY_USERNAME=...
LIBRARY_PASSWORD=...
```

Never committed to Git.

### `pyproject.toml`

Defines:

- package metadata
- runtime dependencies
- development dependencies
- console script
- pytest configuration
- mypy configuration

Install locally with:

```bash
python -m pip install -e ".[dev]"
```
