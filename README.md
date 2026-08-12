# Library Tracker

## Goal

This project automatically evaluates the personal wish list ("Merkliste") of the Stadtbibliothek Bremen (Bremen public library).

The focus is on passively analyzing your own account. The program shows you

* which titles are currently available at the central library,
* which titles can be ordered for free from another branch,
* which titles are fully checked out,
* which items have already been ordered.

This project is intended exclusively for private use.

---

## Current features

### Core functionality

* Login to the online catalog
* Session handling, including cookies and CSId
* Reading the personal wish list
* Support for wish lists spanning any number of pages
* Fetching detail pages for every title
* Detection of multiple copies per title
* Distinction between the central library and branch libraries
* Status classification:

  * `ausleihbar` (available at the central library)
  * `bestellbar` (free order from a branch)
  * `entliehen` (checked out)
  * `bestellt` (already ordered)
* Extraction of due dates from the status text (not yet shown in the output)
* Sorted output of results following this order

### Engineering / project setup

* Installable Python package (`pyproject.toml`, `pip install -e ".[dev]"`)
* Full type hints across all modules, checked with `mypy`
* `pytest` test suite covering the pure parsing/business logic (`library_parser.py`, `wishlist.py`)
* Continuous Integration via GitHub Actions: `mypy` + `pytest` (with coverage report) run on every push/PR
* Scheduled daily scrape via GitHub Actions (cron), writing results to `results.md` in the repo

---

## Planned enhancements

### High priority

* Show due dates in the output (extraction is already implemented)
* Overview of currently checked-out items
* Detection of renewable items
* Overview of already-ordered items

### Medium priority

* Manually trigger free orders
* Console menu
* Additional features such as:
    - filtering new releases by favorite authors
    - filtering books by genre
    - querying two accounts at once

### Not planned

* Automatic paid reservations ("Vormerkung")
* Bulk/mass requests
* Public deployment as a hosted service
