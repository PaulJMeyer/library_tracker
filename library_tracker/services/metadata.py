from __future__ import annotations

from datetime import UTC, datetime
import time

from library_tracker.clients.dnb import DnbClient, DnbError
from library_tracker.clients.googlebooks import GoogleBooksClient
from library_tracker.clients.openlibrary import OpenLibraryClient
from library_tracker.config import require_env
from library_tracker.database import open_database
from library_tracker.models import GoogleBooksResolution, OpenLibraryResolution
from library_tracker.repositories.metadata import (
    get_dnb_lookup_candidates,
    get_googlebooks_fallback_isbns,
    get_title_link_candidates,
    get_unresolved_reado_isbns,
    get_unsynced_wishlist_work_keys,
    save_dnb_lookup,
    save_googlebooks_resolutions,
    save_openlibrary_editions,
    save_openlibrary_resolutions,
    save_title_link,
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def resolve_openlibrary() -> tuple[int, list[OpenLibraryResolution]]:
    with open_database() as connection:
        isbns = get_unresolved_reado_isbns(connection)
        if not isbns:
            return 0, []
        resolutions = OpenLibraryClient(
            require_env("OPENLIBRARY_CONTACT_EMAIL")
        ).resolve_isbns(isbns)
        save_openlibrary_resolutions(connection, resolutions, _now())
        return len(isbns), resolutions


def resolve_googlebooks() -> tuple[int, list[GoogleBooksResolution]]:
    with open_database() as connection:
        isbns = get_googlebooks_fallback_isbns(connection)
        if not isbns:
            return 0, []
        resolutions = GoogleBooksClient(
            require_env("GOOGLE_BOOKS_API_KEY")
        ).resolve_isbns(isbns)
        save_googlebooks_resolutions(connection, resolutions, _now())
        return len(isbns), resolutions


def link_googlebooks_titles() -> list[tuple[str, str | None]]:
    """Search Open Library by title/author for books only Google Books knows."""
    with open_database() as connection:
        candidates = get_title_link_candidates(connection)
        if not candidates:
            return []
        client = OpenLibraryClient(require_env("OPENLIBRARY_CONTACT_EMAIL"))
        results: list[tuple[str, str | None]] = []
        for isbn, title, authors in candidates:
            match = client.search_work(title, authors)
            save_title_link(connection, isbn, match, _now())
            results.append((isbn, match[0] if match else None))
            time.sleep(0.5)
        return results


def sync_openlibrary_editions(*, refresh: bool = False) -> list[tuple[str, int]]:
    with open_database() as connection:
        work_keys = get_unsynced_wishlist_work_keys(connection, include_synced=refresh)
        if not work_keys:
            return []

        client = OpenLibraryClient(require_env("OPENLIBRARY_CONTACT_EMAIL"))
        summary: list[tuple[str, int]] = []
        for work_key in work_keys:
            editions = client.get_work_editions(work_key)
            save_openlibrary_editions(connection, work_key, editions, _now())
            summary.append((work_key, len(editions)))
            time.sleep(0.5)
        return summary


def lookup_dnb_editions(
    client: DnbClient | None = None,
) -> tuple[list[tuple[str, bool, int]], list[str]]:
    """Find German print editions in the DNB for wishlist books.

    Returns ([(isbn, found, edition_count)], [isbns that failed and will be retried]).
    """
    with open_database() as connection:
        candidates = get_dnb_lookup_candidates(connection)
        client = client or DnbClient()
        results: list[tuple[str, bool, int]] = []
        failed: list[str] = []
        for isbn, known_title, known_authors in candidates:
            try:
                record = client.lookup_isbn(isbn)
                title = record.title if record else known_title
                authors = (record.authors if record else []) or known_authors
                editions: dict[str, str] = {}
                if record and record.is_print and record.is_german:
                    editions.update({edition: record.title for edition in record.isbns})
                if title and authors:
                    for found in client.find_german_print_editions(title, authors):
                        for edition in found.isbns:
                            editions.setdefault(edition, found.title)
            except DnbError:
                failed.append(isbn)
                continue
            editions.pop(isbn, None)
            save_dnb_lookup(
                connection,
                isbn,
                title=title,
                authors=authors,
                editions=sorted(editions.items()),
                found=record is not None or bool(editions),
                searched_at=_now(),
            )
            results.append((isbn, record is not None or bool(editions), len(editions)))
        return results, failed
