from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Sequence

from library_tracker.clients.googlebooks import GoogleBooksError
from library_tracker.clients.library import LibraryClientError
from library_tracker.clients.openlibrary import OpenLibraryError
from library_tracker.clients.reado import ReadoError
from library_tracker.config import ConfigurationError
from library_tracker.database import get_connection, initialize_database
from library_tracker.models import ReadoListType
from library_tracker.output import format_history_line, print_scrape_result
from library_tracker.repositories.availability import get_copy_history
from library_tracker.services.library_matching import match_wishlist_book, search_catalog
from library_tracker.services.library_scrape import scrape_library
from library_tracker.services.metadata import (
    resolve_googlebooks,
    resolve_openlibrary,
    sync_openlibrary_editions,
)
from library_tracker.services.reado_sync import sync_lists


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="library-tracker",
        description="Synchronize READO data and match books with Stadtbibliothek Bremen.",
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("scrape", help="Scrape the current library wish list.")

    history = commands.add_parser("history", help="Show stored history for one copy.")
    history.add_argument("media_number")

    for name, help_text in (
        ("reado-wishlist", "Synchronize the configured READO wishlist."),
        ("reado-sync", "Synchronize all configured READO lists."),
    ):
        subparser = commands.add_parser(name, help=help_text)
        subparser.add_argument("--headless", action="store_true")

    commands.add_parser("openlibrary-resolve", help="Resolve uncached READO ISBNs.")
    commands.add_parser("googlebooks-resolve", help="Resolve Open Library fallback ISBNs.")
    commands.add_parser("openlibrary-editions", help="Cache DE/EN editions for wishlist works.")

    library_search = commands.add_parser("library-search", help="Search Bremen catalog by ISBN.")
    library_search.add_argument("isbn")

    library_match = commands.add_parser(
        "library-match",
        help="Match one READO wishlist book using prioritized German ISBNs.",
    )
    library_match.add_argument("isbn")
    return parser


def _run_history(media_number: str) -> int:
    connection = get_connection()
    try:
        initialize_database(connection)
        history = get_copy_history(connection, media_number)
    finally:
        connection.close()

    if not history:
        print(f"No history found for copy {media_number}.")
        return 1

    print(f"Availability history for copy {media_number}:")
    for snapshot in history:
        print(format_history_line(snapshot))
    return 0


def _run_reado(*, headless: bool, wishlist_only: bool) -> int:
    list_types: tuple[ReadoListType, ...] = ("wishlist",) if wishlist_only else (
        "wishlist",
        "tbr",
        "reading",
        "completed",
    )
    entries, results = sync_lists(headless=headless, list_types=list_types)
    total_new = {
        entry["isbn13"]
        for result in results.values()
        for entry in result["new_entries"]
    }

    for list_type in list_types:
        result = results[list_type]
        print(f"READO {list_type}: {len(entries[list_type])} books")
        print(f"  New to cache: {len(result['new_entries'])}")
        print(f"  Removed from list: {len(result['removed_isbns'])}")

    if wishlist_only:
        for entry in entries["wishlist"]:
            print(f"{entry['isbn13']} | {entry['reado_url']}")
    else:
        print(f"Total new books: {len(total_new)}")
    return 0


def _print_resolution_summary(label: str, total: int, statuses: list[str]) -> None:
    print(f"{label}: {total}")
    for status, count in sorted(Counter(statuses).items()):
        print(f"{status.replace('_', ' ').title()}: {count}")


def _run_openlibrary_resolve() -> int:
    total, resolutions = resolve_openlibrary()
    _print_resolution_summary(
        "Unresolved ISBNs",
        total,
        [resolution["status"] for resolution in resolutions],
    )
    return 0


def _run_googlebooks_resolve() -> int:
    total, resolutions = resolve_googlebooks()
    _print_resolution_summary(
        "Google Books fallback ISBNs",
        total,
        [resolution["status"] for resolution in resolutions],
    )
    return 0


def _run_openlibrary_editions() -> int:
    summary = sync_openlibrary_editions()
    print(f"Wishlist works needing editions: {len(summary)}")
    total = 0
    for index, (work_key, count) in enumerate(summary, start=1):
        total += count
        print(f"[{index}/{len(summary)}] {work_key}: {count} relevant editions")
    print(f"Relevant editions cached: {total}")
    return 0


def _run_library_search(isbn: str) -> int:
    hits = search_catalog(isbn)
    print(f"ISBN: {isbn}")
    print(f"Catalog hits: {len(hits)}")
    for hit in hits:
        print(hit)
    return 0


def _run_library_match(isbn: str) -> int:
    result = match_wishlist_book(isbn)
    if not result["attempts"]:
        print(f"No active READO wishlist entry found for ISBN {isbn}.")
        return 1

    print(f"ISBN candidates for {isbn}: {len(result['attempts'])}")
    for index, attempt in enumerate(result["attempts"], start=1):
        print(
            f"[{index}/{len(result['attempts'])}] {attempt['isbn']} "
            f"({attempt['source']}) -> {attempt['hit_count']} hit(s)"
        )

    if result["match"] is None:
        print("\nNo library match found.")
        return 0

    print("\nLibrary match found.")
    print(f"READO ISBN: {isbn}")
    print(f"Matched ISBN: {result['match']['isbn']}")
    print(f"Source: {result['match']['source']}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in (None, "scrape"):
            print_scrape_result(scrape_library())
            return 0
        if args.command == "history":
            return _run_history(str(args.media_number))
        if args.command == "reado-wishlist":
            return _run_reado(headless=bool(args.headless), wishlist_only=True)
        if args.command == "reado-sync":
            return _run_reado(headless=bool(args.headless), wishlist_only=False)
        if args.command == "openlibrary-resolve":
            return _run_openlibrary_resolve()
        if args.command == "googlebooks-resolve":
            return _run_googlebooks_resolve()
        if args.command == "openlibrary-editions":
            return _run_openlibrary_editions()
        if args.command == "library-search":
            return _run_library_search(str(args.isbn))
        if args.command == "library-match":
            return _run_library_match(str(args.isbn))
    except (
        ConfigurationError,
        LibraryClientError,
        ReadoError,
        OpenLibraryError,
        GoogleBooksError,
    ) as exc:
        print(f"Error: {exc}")
        return 1

    return 2
