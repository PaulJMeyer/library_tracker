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
   - `TELEGRAM_BOT_TOKEN` (from @BotFather)
   - `TELEGRAM_CHAT_ID` (your chat ID, see below)
4. Optionally move the existing database: download the latest
   `library-tracker-db` artifact from the public repository's last
   scheduled run and upload it once via a manual run, or simply let the
   first private run start with an empty database.
5. Start the workflow once via *Actions → Daily library run → Run workflow*.

The workflow installs `library-tracker` from the public repository's
`master` branch, so merged changes are picked up on the next run.

## Telegram

The daily run sends one message with two sections:

- **Ausleihbar in der Zentralbibliothek**: a copy is available in the central library (with its shelf location)
- **Bestellbar aus anderen Zweigstellen**: no copy is free in the central library, but one is in another branch (with branch names)

Setup:

1. In Telegram, send `/newbot` to @BotFather and follow the prompts. Store the token as `TELEGRAM_BOT_TOKEN`.
2. Open the new bot and press **Start**, otherwise it cannot message you.
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser. The number in `"chat":{"id":...}` is your `TELEGRAM_CHAT_ID`. If the result is empty, send the bot any message and reload.
4. Locally, `library-tracker telegram-test` sends a test message using the same variables from `.env`.

If sending fails, the workflow run fails, so GitHub notifies you by e-mail.

## Rules for the public repository

- No scheduled workflows that use personal credentials.
- No committed scrape output (`results.md` is gitignored).
- No artifacts containing the SQLite database.
