# Roadmap

## Version 0.1

* Set up the project
* Implement login
* Read the wish list

Status: done

---

## Version 0.2

* Fetch detail pages
* Detect status
* Sorted output

Status: done

---

## Version 0.3

* Detect multiple copies
* Distinguish central library vs. branch libraries

Status: done

---

## Version 0.4

* Type hints across all modules, checked with mypy
* pytest test suite for the core parsing/business logic
* Installable package structure (`pyproject.toml`)
* CI via GitHub Actions (mypy + pytest on every push/PR)
* Scheduled daily scrape via GitHub Actions (cron), writing results to `results.md`

Status: done

---

## Version 0.5

* Account overview - DONE
* Show due dates in the output (extraction is already implemented) - DONE
* Renewal options

---

## Version 0.55

* Automatically remove already-borrowed titles from the wish list
* Titles classified as `entliehen` are excluded from `results.md`

Status: done

---

## Version 0.6

* Order overview
* Pickup status
* History

---

## Version 0.7

* Manually trigger free orders
* Confirmation prompt before ordering

---

## Version 1.0

Complete private library management:

* Wish list
* Loans
* Orders
* Renewals
* Convenience features
* Clear separation between free orders and paid reservations ("Vormerkung")
* Automatically remove titles from the wish list once detected as already borrowed - DONE