"""Remove books from the library Merkliste once they are on a finished READO list,
and e-books, which the overview does not show."""
from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import UTC, datetime

from library_tracker.clients.library import LibraryClient, LibraryClientError
from library_tracker.clients.openlibrary import strip_sort_markers
from library_tracker.titles import merkliste_title_key
from library_tracker.database import open_database
from library_tracker.models import MerklisteEntry
from library_tracker.parsers.library import parse_single_hit
from library_tracker.repositories.merkliste_removals import (
    forget_removals_of_wishlist_books,
    get_finished_books_to_check,
    get_wishlist_merkliste_keys,
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


def _matches(entry: MerklisteEntry, titles: set[str], media_numbers: set[str]) -> bool:
    return merkliste_title_key(entry["title"]) in titles or not media_numbers.isdisjoint(
        entry.get("media_numbers", [])
    )


def remove_ebooks_from_merkliste(
    entries: list[MerklisteEntry],
    client: LibraryClient,
    *,
    progress: Callable[[str], None] = _print_progress,
) -> list[tuple[str, str, str]]:
    """Removes Merkliste entries whose copies are all e-books of the online branch.

    Returns [("", title, status)] with status removed/failed, one row per entry."""
    results: list[tuple[str, str, str]] = []
    for entry in entries:
        if not entry.get("ebook"):
            continue
        try:
            removed = client.remove_entries(entry["page"], [entry["uuid"]])
        except LibraryClientError as exc:
            progress(f"  Entfernen-Fehler bei {entry['title']}: {exc}")
            removed = False
        results.append(("", entry["title"], "removed" if removed else "failed"))
    return results


def remove_finished_from_merkliste(
    entries: list[MerklisteEntry],
    client: LibraryClient,
    *,
    lookup_limit: int = CATALOG_LOOKUPS_PER_RUN,
    progress: Callable[[str], None] = _print_progress,
) -> list[tuple[str, str, str]]:
    """Removes every edition of a finished book (matched by title or copy number).

    Returns [(isbn13, title, status)] with status removed/not_on_merkliste/
    not_in_catalog/failed, one row per removed Merkliste entry and one per book
    otherwise. Each book is checked once; failures are retried."""
    remaining = list(entries)
    results: list[tuple[str, str, str]] = []
    lookups = 0
    with open_database() as connection:
        forget_removals_of_wishlist_books(connection)
        # Entries that belong to a wishlist book are never removed.
        wishlist_titles, wishlist_media = get_wishlist_merkliste_keys(connection)
        wishlist_wanted = {merkliste_title_key(title) for title in wishlist_titles}
        remaining = [e for e in remaining if not _matches(e, wishlist_wanted, wishlist_media)]
        for isbn13, titles, media_numbers in get_finished_books_to_check(connection):
            status: str
            matching: list[MerklisteEntry] = []
            try:
                if not titles and not media_numbers:
                    if lookups >= lookup_limit:
                        continue
                    lookups += 1
                    looked_up = _catalog_title(client, isbn13)
                    titles = [looked_up] if looked_up is not None else []
                if not titles and not media_numbers:
                    status = "not_in_catalog"
                else:
                    wanted = {merkliste_title_key(title) for title in titles}
                    matching = [e for e in remaining if _matches(e, wanted, media_numbers)]
                    remaining = [e for e in remaining if not _matches(e, wanted, media_numbers)]
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
            title = titles[0] if titles else None
            save_removal_result(
                connection, isbn13, status, title, datetime.now(UTC).isoformat(timespec="seconds")
            )
            if status == "removed":
                results.extend((isbn13, entry["title"], status) for entry in matching)
            else:
                results.append((isbn13, title or isbn13, status))
        return results
