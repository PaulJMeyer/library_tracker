# Project Structure

```
library_tracker/
├── library_tracker/
│   ├── __init__.py
│   ├── __main__.py
│   ├── client.py
│   ├── library_parser.py
│   ├── login.py
│   ├── main.py
│   ├── models.py
│   └── wishlist.py
├── tests/
│   ├── __init__.py
│   ├── test_library_parser.py
│   └── test_wishlist.py
├── .github/
|   ├── AI_CONTEXT.md
│   └── workflows/
│       ├── ci.yml
│       └── scrape.yml
├── .env
├── pyproject.toml
├── README.md
└── ROADMAP.md
```

---

## client.py

Central HTTP helper functions.

Responsibilities:

* URL construction
* GET requests
* POST requests
* Timeout
* Request delays

---

## login.py

Manages the login process.

Responsibilities:

* Fetch the login page
* Extract the CSId
* Perform the login
* Return the session

---

## wishlist.py

Handles the personal wish list.

Responsibilities:

* Load wish list pages
* Handle pagination
* Extract availability links

---

## library_parser.py

Extracts information from the HTML pages.

Responsibilities:

* Extract title
* Detect multiple copies per title (`parse_copies`)
* Distinguish branch vs. central library (`is_central`)
* Normalize per-copy status (`normalize_copy_status`) and derive overall status (`classify_item`)
* Extract due date from the status text (`extract_due_date`) — value is available but not yet shown in the output
* Future:

  * Show due dates in the output
  * Order options (automatic ordering)

---

## models.py

`TypedDict` definitions for the data structures shared across the project (`Copy`, `Item`), used for precise type checking with `mypy` instead of generic `dict`.

---

## main.py

Entry point of the program.

Current flow:

1. Login
2. Load wish list
3. Iterate over all titles
4. Determine status
5. Produce sorted output (console + `results.md`)

Also contains `format_results_markdown()` / `write_results_markdown()`, used both by the interactive run and by the scheduled GitHub Actions scrape.

---

## __main__.py

Enables running the package directly via `python -m library_tracker`; simply calls `main()` from `main.py`.

---

## tests/

`pytest` suite covering the pure parsing/business logic:

* `test_library_parser.py` — `clean_text`, `extract_due_date`, `normalize_copy_status`, `classify_item`, `parse_title`
* `test_wishlist.py` — `extract_availability_links`

`client.py` and `login.py` (real HTTP calls) are not yet covered — this would require mocking `requests.Session` and is planned for a later step.

---

## .github/workflows/

* `ci.yml` — runs `mypy` and `pytest` (with coverage) on every push/PR to `master`
* `scrape.yml` — scheduled daily scrape (cron) plus manual trigger; reads `LIBRARY_USERNAME`/`LIBRARY_PASSWORD` from GitHub Secrets and commits the updated `results.md` back to the repo

---

## .env

Used for local development only. Contains exclusively:

* LIBRARY_USERNAME
* LIBRARY_PASSWORD

Never committed to git. In CI/scheduled runs, the equivalent values come from GitHub Secrets instead.

---

## pyproject.toml

Package definition and dependencies (replaces `requirements.txt`). Installed locally via:

```
pip install -e ".[dev]"
```
