# Project Structure

```
library_tracker/
├── library_tracker/
│   ├── __init__.py
│   ├── __main__.py
│   ├── account.py
│   ├── client.py
│   ├── library_parser.py
│   ├── login.py
│   ├── main.py
│   ├── models.py
│   ├── output.py
│   └── wishlist.py
├── tests/
│   ├── __init__.py
│   ├── test_account.py
│   ├── test_library_parser.py
│   ├── test_output.py
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
* GET requests (with optional query parameters, safely URL-encoded by `requests`)
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
* Extract per-page wish-list entries (checkbox UUID + availability link) plus the page's hidden form fields (`CSId`, `curPos`, `displayType`, `selectedMemorizeList`) via `extract_memorize_page()` / `get_all_memorize_pages()`
* Remove selected entries from the wish list on the library website via `remove_entries()` (GET request against `memorizelist.do?methodToCall=deleteSelectedEntries`)

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

`TypedDict` definitions for the data structures shared across the project (`Copy`, `Item`, `Loan`, `MemorizeEntry`, `MemorizePage`), used for precise type checking with `mypy` instead of generic `dict`.

---

## output.py

All output/formatting logic, kept separate from orchestration (`main.py`) and business logic (`library_parser.py`).

Responsibilities:

* `format_copy_line()` — format a single copy's line, including due date if available and not already part of the status text
* `format_results_markdown()` — build the full Markdown report
* `write_results_markdown()` — write the report to `results.md`
* `print_results_console()` — console output, using the same `format_copy_line()` as the Markdown output


---

## account.py

Handles the account overview.

Responsibilities:

* Load account page
* Extract borrowed book info

---

## main.py

Entry point of the program.

Current flow:

1. Login
2. Load wish list pages (`get_all_memorize_pages`)
3. For each page: classify each entry's status; collect already-borrowed entries separately, excluding them from the report
4. Remove already-borrowed entries from the wish list on that page
5. Sort the remaining (non-borrowed) results
6. Delegate console and file output to `output.py`

---

## __main__.py

Enables running the package directly via `python -m library_tracker`; simply calls `main()` from `main.py`.

---

## tests/

## tests/

`pytest` suite covering the pure parsing/business logic:

* `test_library_parser.py` — `clean_text`, `extract_due_date`, `normalize_copy_status`, `classify_item`, `parse_title`
* `test_wishlist.py` — `extract_memorize_page`, `remove_entries`, `get_all_memorize_pages`
* `test_account.py` — `parse_loans`, `parse_loan_dates`
* `test_output.py` — `format_copy_line`, `format_status_summary`

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
