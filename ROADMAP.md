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

### P1 — Reliable start and interactive Telegram

GitHub starts scheduled runs late or not at all on free accounts, and the bot
can only send messages so far. Planned approach: a small serverless function
(e.g. Cloudflare Workers, free tier) that

- [ ] starts the daily workflow on time via `workflow_dispatch` (replaces the GitHub `schedule`)
- [ ] receives Telegram messages through a webhook (only from the configured chat ID, with a secret token)
- [ ] starts a GitHub workflow for each command, which answers in Telegram (about 1–3 minutes)

### P1 — More useful Telegram messages

- [ ] send only when something changed, plus a short weekly summary
- [ ] mark titles that became available since the previous run ("neu")
- [ ] "seltene Chance" ⭐: mark titles that are usually loaned but available today
  (loan quota per title from the daily availability snapshots)
- [ ] put all editions of a wishlist book that the catalog has on the Merkliste, not only the first hit
  (keep searching after the first hit, detect duplicates by catalog record instead of by title,
  remove all editions once the book is finished)
- [ ] show the same work only once in the Telegram message when several editions are on the Merkliste
- [ ] loan reminders: titles due in the next 3 days (loans are already read from the account page)

### P1 — Availability statistics

- [ ] loan quota per title from the daily availability snapshots (also used for "seltene Chance")
- [ ] Telegram command for the X most loaned books (e.g. `/top 10`), sorted by loan quota, highest first

### P1 — Second READO account

- [x] monitor the wishlist of another READO account with the same rules (`READO_SECOND_WISHLIST_URL`, books go on the same library Merkliste)
- [ ] separate state per account (matches, Merkliste entries)
- [x] separate section at the end of the Telegram message ("Von X's Wunschliste:" with available and orderable titles, name from `READO_SECOND_WISHLIST_NAME`)

### P2 — Loans and orders from Telegram (only with explicit confirmation)

- [ ] renew loans with a button and a confirmation step
- [ ] free branch orders ("Bestellung") with a button and a confirmation step, clearly separated from paid reservations

### P2 — Books without an ISBN match

About 20 wishlist books have no catalog hit for any known ISBN. First check by hand
(`match-report`) which of them the library actually has; only then decide how to find them
automatically (e.g. a careful title/author search with "Bitte prüfen").

### P3 — Statistics and visuals

- [ ] return forecast ("vermutlich ab 3.12. wieder da") from due dates and past loan durations
- [ ] weekly chart in Telegram (most loaned titles, longest on the wishlist, availability heatmap, branches)
- [ ] static HTML dashboard: built with personal data in the private runner, with sample data as a public demo

### P3 — Robustness and maintenance

- [ ] treat a READO list that is really empty differently from a list that failed to load
- [ ] `status` command with database statistics (books, matches, open ISBNs, last run)
- [ ] structured logging for the scheduled run
- [ ] `ruff` for formatting and linting in CI

### P3 — Portfolio polish

- [ ] demo mode with sample data, so the pipeline can be tried without accounts
- [ ] architecture diagram in the README
- [ ] versioned schema migrations if the SQLite schema keeps changing

## Long-term goal

### Own server

The Cloudflare Worker comes first. Later the tracker should run on its own server.
Which one is still open: Steam Deck, a free online server or a Raspberry Pi.

- [ ] daily run as a timer on the server (replaces GitHub Actions and the Worker start)
- [ ] Telegram bot via long polling: commands answered in seconds, no public address needed

### Own app

- [ ] once everything works: present the tracker as its own app, e.g. a web app (PWA) on the
  phone home screen with the overview, statistics and buttons for renewals

## Safety constraint

Paid reservations (`Vormerkung`, currently 1 €) must **never** be triggered automatically.
Renewals and free branch orders may only be triggered with explicit user confirmation, with a clear distinction from paid reservations.

The project remains a private, low-volume automation tool rather than a public scraping service.
