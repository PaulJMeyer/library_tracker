# Library Tracker Roadmap

**Current milestone:** refactored READO ↔ Stadtbibliothek integration foundation
**Primary goal:** turn READO into the source of reading state and automatically surface library availability changes without repeatedly querying metadata that is already known.

## Current state

### Done — library foundation

- [x] authenticated Stadtbibliothek Bremen session + CSId
- [x] multi-page library wish-list scraping
- [x] copy-level availability and due-date parsing
- [x] central-library vs. branch classification
- [x] SQLite copy and availability history
- [x] persistent SQLite artifact in scheduled GitHub Actions scrape
- [x] ISBN search against the Bremen catalog

### Done — READO and metadata foundation

- [x] synchronize READO wishlist
- [x] synchronize TBR / reading / completed lists
- [x] model list membership separately from cached books
- [x] resolve ISBNs to Open Library works
- [x] exact Open Library ISBN fallback
- [x] Google Books fallback for unresolved Open Library ISBNs
- [x] cache German and English Open Library editions
- [x] filter explicit digital/audio editions
- [x] prioritize German print ISBN-13 candidates
- [x] verify READO → alternative German edition → Bremen catalog end-to-end matching

### Done — architecture refactor

- [x] split external clients from parsing
- [x] split repository responsibilities
- [x] move multi-step workflows into services
- [x] reduce CLI to routing/output
- [x] centralize ISBN normalization and configuration
- [x] consolidate SQLite schema creation
- [x] simplify and focus tests

## P1 — Full READO → library synchronization

The next milestone is to replace one-book manual matching with a complete, cached synchronization run.

- [ ] add a service that processes every active READO wishlist book
- [ ] resolve only ISBNs that are not already cached
- [ ] fetch editions only for works without an edition-sync marker
- [ ] match all active wishlist books against Bremen using prioritized German ISBNs
- [ ] persist catalog-match results instead of re-searching unchanged ISBNs every run
- [ ] record the matched ISBN and match source (`reado`, confirmed edition, unknown-format edition)
- [ ] distinguish "not in catalog" from transient request failure
- [ ] add retry/backoff around catalog searches without creating high request volume

Target flow:

```text
READO sync
  ↓
new/unresolved ISBNs only
  ↓
Open Library → Google Books fallback
  ↓
unsynced wishlist works → editions
  ↓
German ISBN candidates
  ↓
Bremen catalog matching
  ↓
persisted match state
```

## P1 — READO as the source of reading state

READO should determine whether a title still belongs in the library workflow.

- [ ] wishlist → eligible for Bremen matching/library wish-list handling
- [ ] TBR → no longer treated as a library-wishlist candidate
- [ ] reading → no longer treated as a library-wishlist candidate
- [ ] completed → no longer treated as a library-wishlist candidate
- [ ] detect transitions between READO lists
- [ ] keep all bibliographic metadata cached after transitions
- [ ] reconcile READO state with the Stadtbibliothek personal wish list

The intended rule is: moving a book out of the READO wishlist should stop availability monitoring for that wishlist item without deleting its cached work/edition metadata.

## P1 — Update / notification system

After full matching is persisted, add a user-facing update layer.

Preferred first implementation: **e-mail** because it is simple, mobile-friendly and works without hosting a frontend.

- [ ] persist the previous relevant library state for each matched READO book
- [ ] calculate changes between runs
- [ ] report newly found catalog matches
- [ ] report newly `ausleihbar` books
- [ ] report newly `bestellbar` books
- [ ] optionally report titles that became unavailable
- [ ] send a concise daily/changed-only e-mail
- [ ] keep notification credentials in GitHub Secrets
- [ ] avoid sending an empty "nothing changed" message unless explicitly desired

Possible later channels:

- e-mail via SMTP or mail API
- Telegram/Signal-style notification integration if it provides a clear benefit
- small web/dashboard view only if notification output becomes insufficient

## P2 — Library wish-list synchronization

Once read-only matching and notification are stable:

- [ ] detect whether a matched title is already on the Stadtbibliothek wish list
- [ ] add matched READO wishlist books to the library wish list where technically safe
- [ ] remove entries when their READO state moves to TBR/reading/completed
- [ ] make synchronization idempotent
- [ ] store reconciliation results and errors

### Safety constraint

Paid reservations (`Vormerkung`, currently 1 €) must **never** be triggered automatically.

Free branch orders may be supported later only with explicit user confirmation and a clear distinction from paid reservations.

## P2 — Availability workflow cleanup

The old library-wishlist scraper predates the READO integration. After the READO-driven pipeline is complete:

- [ ] decide which parts of `scrape` remain useful
- [ ] stop deleting library-wishlist entries merely because all copies are currently checked out if that conflicts with the new monitoring model
- [ ] consolidate availability tracking around READO-linked catalog matches
- [ ] store snapshots only when relevant availability changes if history volume becomes noisy
- [ ] add database status/statistics command

## P2 — Automation

- [ ] create one scheduled orchestration command, e.g. `library-tracker sync`
- [ ] install Playwright Chromium in the relevant GitHub Actions job
- [ ] restore SQLite state before the run
- [ ] sync READO
- [ ] resolve/cache new metadata
- [ ] update library matches and availability
- [ ] generate/send update
- [ ] upload SQLite artifact after the run
- [ ] expose useful workflow summaries on failure

## P3 — Portfolio polish

- [ ] structured logging instead of ad-hoc prints for automated runs
- [ ] optional `ruff` formatting/linting
- [ ] versioned schema migrations if SQLite changes become more frequent
- [ ] command for database/cache statistics
- [ ] documented demo flow using mocked/sample data
- [ ] optional Streamlit dashboard only if historical visualization adds real value

## Definition of the intended end state

```text
READO is the source of truth
        ↓
list changes are synchronized
        ↓
metadata is resolved once and cached
        ↓
German print editions are matched to Bremen
        ↓
relevant catalog/availability state is persisted
        ↓
changes are detected
        ↓
user receives a concise update (initially e-mail)
```

The project should remain a private, low-volume automation tool rather than a public scraping service.
