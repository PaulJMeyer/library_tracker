"""Remove books from the library Merkliste once they are on a finished READO list."""
from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import UTC, datetime

from library_tracker.clients.library import LibraryClient, LibraryClientError
from library_tracker.clients.openlibrary import normalize_title, strip_sort_markers
from library_tracker.database import get_connection, initialize_database
from library_tracker.models import MerklisteEntry
from library_tracker.parsers.library import parse_single_hit
from library_tracker.repositories.merkliste_removals import (
    forget_removals_of_wishlist_books,
    get_finished_books_to_check,
    save_removal_result,
)

# Books without a stored catalog title need one catalog search each, so the first
# run with a long "completed" list is spread over several days.
CATALOG_LOOKUPS_PER_RUN = 30


def _print_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _catalog_title(client: LibraryClient, isbn13: str) -> str | None:
    hits = client.search_catalog_by_isbn(isbn13)
    if not hits:
        return None
    html, page_url = client.get_page(hits[0])
    title, _ = parse_single_hit(html, page_url)
    return strip_sort_markers(title)


def remove_finished_from_merkliste(
    entries: list[MerklisteEntry],
    client: LibraryClient,
    *,
    lookup_limit: int = CATALOG_LOOKUPS_PER_RUN,
    progress: Callable[[str], None] = _print_progress,
) -> list[tuple[str, str, str]]:
    """Returns [(isbn13, title, status)] with status removed/not_on_merkliste/
    not_in_catalog/failed. Each book is checked once; failures are retried."""
    by_title: dict[str, list[MerklisteEntry]] = {}
    for entry in entries:
        by_title.setdefault(normalize_title(entry["title"]), []).append(entry)

    results: list[tuple[str, str, str]] = []
    lookups = 0
    connection = get_connection()
    try:
        initialize_database(connection)
        forget_removals_of_wishlist_books(connection)
        for isbn13, title in get_finished_books_to_check(connection):
            status: str
            try:
                if title is None:
                    if lookups >= lookup_limit:
                        continue
                    lookups += 1
                    title = _catalog_title(client, isbn13)
                if title is None:
                    status = "not_in_catalog"
                else:
                    matching = by_title.pop(normalize_title(title), [])
                    if not matching:
                        status = "not_on_merkliste"
                    elif all(
                        client.remove_entries(entry["page"], [entry["uuid"]]) for entry in matching
                    ):
                        status = "removed"
                    else:
                        status = "failed"
            except LibraryClientError as exc:
                progress(f"  Entfernen-Fehler bei {isbn13}: {exc}")
                status = "failed"
            save_removal_result(
                connection, isbn13, status, title, datetime.now(UTC).isoformat(timespec="seconds")
            )
            results.append((isbn13, title or isbn13, status))
        return results
    finally:
        connection.close()
