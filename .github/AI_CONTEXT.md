# AI_CONTEXT

## Project description

This repository contains a private Python project for reading the user account of the Stadtbibliothek Bremen (Bremen public library).

Its purpose is a convenient overview of your own wish list ("Merkliste") and library account.

The project is meant to demonstrate web scraping and session handling, while also serving as a personal everyday tool.

---

## Key project goals

The user wants to distinguish between the following end states:

1. `ausleihbar` (available)

   * at least one copy available at the central library

2. `bestellbar` (orderable)

   * no copy available at the central library
   * but can be ordered for free from another branch

3. `entliehen` (checked out)

   * all relevant copies are checked out

4. `bestellt` (ordered)

   * the user has already triggered a free order

Output must be sorted in exactly this order.

---

## Hard constraints

### Never place an automatic hold ("Vormerkung")

Holds cost money (1 €).

The project must never automatically trigger a hold.

In particular, no actions may be taken if terms such as

* Vormerkung
* Gebühren (fees)
* 1,- Euro

are detected.

---

## Orders

Free orders from other branches are generally desired.

However, automatic ordering should only be implemented in a later project phase, and only after explicit user confirmation.

---

## Coding style

* simple, readable functions
* no unnecessarily complex class hierarchies
* BeautifulSoup for HTML parsing
* `requests.Session` for HTTP communication
* clear separation between

  * HTTP
  * parsing
  * business logic
  * output
* full type hints, checked with `mypy`
* `pytest` for the pure parsing/business logic

---

## Current state

Implemented:

* Login
* Session handling
* Wish list across multiple pages
* Status detection
* Multiple copies per title
* Branch vs. central library detection
* Sorting
* Type hints across all modules (mypy-checked)
* pytest test suite (`library_parser.py`, `wishlist.py`)
* Installable package structure (`pyproject.toml`)
* CI via GitHub Actions (mypy + pytest on every push/PR)
* Scheduled daily scrape via GitHub Actions (cron), writing results to `results.md`

Planned:

* Account overview
* Show due dates in the output (extraction already implemented)
* Renewals
* Orders
* Further features
