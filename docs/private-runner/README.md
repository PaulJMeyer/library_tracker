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
4. Optionally move the existing database: download the latest
   `library-tracker-db` artifact from the public repository's last
   scheduled run and upload it once via a manual run, or simply let the
   first private run start with an empty database.
5. Start the workflow once via *Actions → Daily library run → Run workflow*.

The workflow installs `library-tracker` from the public repository's
`master` branch, so merged changes are picked up on the next run.

## Rules for the public repository

- No scheduled workflows that use personal credentials.
- No committed scrape output (`results.md` is gitignored).
- No artifacts containing the SQLite database.
