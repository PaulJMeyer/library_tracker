# Library Tracker Roadmap

**Current milestone:** base version complete (November 2026).
The daily run in the private runner reads READO, matches wishlist books against the Bremen catalog, keeps the library Merkliste in sync and sends a Telegram overview.

## Done

### Library foundation

- [x] authenticated Stadtbibliothek Bremen session + CSId
- [x] multi-page Merkliste scraping (robust against the OPAC repeating the last page)
- [x] copy-level availability, due dates, central library vs. branches
- [x] "bestellbar" excludes the prison library and reference-only copies
- [x] SQLite copy and availability history
- [x] catalog search by ISBN with retries and re-login

### READO and metadata

- [x] public READO lists: wishlist, TBR, reading, completed, abandoned
- [x] list membership stored separately from cached book metadata
- [x] Open Library works and editions, Google Books fallback, title/author linking
- [x] Deutsche Nationalbibliothek (SRU) for German editions and translations
- [x] prioritized ISBN candidates (READO → German print → DNB → unknown format → English)
- [x] metadata only for wishlist books

### Daily pipeline (`sync --telegram`)

- [x] incremental catalog search: every searched ISBN is stored, 15 new ISBNs per book and run, misses rechecked after 30 days
- [x] add found wishlist books to the Merkliste (only the free "in die Merkliste" link)
- [x] single volumes of multi-volume alternative editions go to "Bitte prüfen" instead
- [x] remove books from the Merkliste once they are on a finished READO list
- [x] Telegram overview with available, orderable (with page counts), added and removed titles plus warnings
- [x] failing steps become warnings, the rest of the run continues
- [x] private runner repository; the public repository holds no personal data

## Next

### P1 — Books without an ISBN match

About 20 wishlist books have no catalog hit for any known ISBN.

- [ ] catalog search by title and author for these books
- [ ] strict safeguards (title and author must match, no single volumes)
- [ ] uncertain hits go to "Bitte prüfen" in Telegram instead of being added automatically

### P1 — More useful Telegram messages

- [ ] mark titles that became available since the previous run ("neu")
- [ ] optional: send only when something changed, plus a short weekly summary
- [ ] show the same work only once when two editions are on the Merkliste
- [ ] loan reminders: titles due in the next 3 days (loans are already read from the account page)

### P2 — Robustness and maintenance

- [ ] treat a READO list that is really empty differently from a list that failed to load
- [ ] `status` command with database statistics (books, matches, open ISBNs, last run)
- [ ] structured logging for the scheduled run
- [ ] `ruff` for formatting and linting in CI

### P2 — Portfolio polish

- [ ] demo mode with sample data, so the pipeline can be tried without accounts
- [ ] architecture diagram in the README
- [ ] versioned schema migrations if the SQLite schema keeps changing

### Later / only with explicit confirmation

- [ ] free branch orders ("Bestellung") triggered from Telegram with an explicit confirmation button

## Safety constraint

Paid reservations (`Vormerkung`, currently 1 €) must **never** be triggered automatically.
Free branch orders may only be supported with explicit user confirmation and a clear distinction from paid reservations.

The project remains a private, low-volume automation tool rather than a public scraping service.
