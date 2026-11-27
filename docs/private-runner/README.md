# Private runner

The public repository contains only code, tests and CI. Scheduled runs that
log in to the library, read personal lists or store personal data run in a
separate **private** repository, so logs, artifacts and results are never
public.

## Setup

1. Create a new private GitHub repository, for example `library-tracker-runner`.
2. Copy [`daily.yml`](daily.yml) to `.github/workflows/daily.yml` in that repository.
3. In the private repository, add these secrets under
   *Settings → Secrets and variables → Actions*:
   - `LIBRARY_USERNAME`
   - `LIBRARY_PASSWORD`
   - `READO_WISHLIST_URL` (required for `sync`)
   - `READO_SECOND_WISHLIST_URL` (optional; the public wishlist URL of a second READO account, for example a partner's, including `?source=profile&userId=...`. Its books are searched and put on the same Merkliste and get their own Telegram section. The owner's name for the heading goes into `READO_SECOND_WISHLIST_NAME`, set directly in `daily.yml`.)
   - `READO_TBR_URL`, `READO_READING_URL`, `READO_COMPLETED_URL`, `READO_ABANDONED_URL` (optional; books on these lists are removed from the Merkliste)
   - `OPENLIBRARY_CONTACT_EMAIL`
   - `GOOGLE_BOOKS_API_KEY` (optional)
   - `TELEGRAM_BOT_TOKEN` (from @BotFather)
   - `TELEGRAM_CHAT_ID` (your chat ID, see below)
4. Optionally move the existing database: download the latest
   `library-tracker-db` artifact from the public repository's last
   scheduled run and upload it once via a manual run, or simply let the
   first private run start with an empty database.
5. Start the workflow once via *Actions → Daily library run → Run workflow*.

The workflow installs `library-tracker` from the public repository's
`master` branch, so merged changes are picked up on the next run.

## What the daily run does

`library-tracker sync --telegram` runs the whole pipeline:

1. read the READO lists
2. resolve metadata for new books only (Open Library, Google Books, DNB editions)
3. search the Bremen catalog: up to 15 not yet searched ISBNs per wishlist book and run. Every search is stored, so books with many editions are covered over several days. ISBNs without a hit are searched again after 30 days.
4. read the library Merkliste
5. remove books that are on a finished READO list (Stapel ungelesener Bücher, Am Lesen/Hören, Abgeschlossen, Abgebrochen) and not on either wishlist. Each book is checked once; books without a stored catalog title need one catalog search, at most 30 per run.
6. add wishlist books found in the catalog to the Merkliste (only via the catalog's free "in die Merkliste" link, never a reservation)
7. send the Telegram overview, including added and removed titles. Titles that are only on the second wishlist are listed in their own section at the end.

Removing runs before adding so the Merkliste page data from step 4 stays valid; the result is the same.

If a step fails, the remaining steps still run and the Telegram message
contains a warning. The job is then marked as failed, but the database is
uploaded anyway, so the catalog search progress is kept.

## Telegram

The daily run sends one message with two sections:

- **Ausleihbar in der Zentralbibliothek**: a copy is available in the central library (with its shelf location)
- **Bestellbar aus anderen Zweigstellen**: no copy is free in the central library, but one is in another branch (with branch names)

Titles added to the Merkliste in this run are listed under **Neu auf der Merkliste**, removed ones under **Von der Merkliste entfernt**. Alternative editions that are a single volume of a multi-volume edition are not added; they appear once under **Bitte prüfen**. Fully loaned titles stay on the Merkliste and are simply not shown.

Setup:

1. In Telegram, send `/newbot` to @BotFather and follow the prompts. Store the token as `TELEGRAM_BOT_TOKEN`.
2. Open the new bot and press **Start**, otherwise it cannot message you.
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser. The number in `"chat":{"id":...}` is your `TELEGRAM_CHAT_ID`. If the result is empty, send the bot any message and reload.
4. Locally, `library-tracker telegram-test` sends a test message using the same variables from `.env`.

If sending fails or a step reports a warning, the workflow run is marked as failed, so GitHub notifies you by e-mail.

## Rules for the public repository

- No scheduled workflows that use personal credentials.
- No committed scrape output (`results.md` is gitignored).
- No artifacts containing the SQLite database.
