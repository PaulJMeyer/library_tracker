from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Sequence

from library_tracker.clients.dnb import DnbError
from library_tracker.clients.googlebooks import GoogleBooksError
from library_tracker.clients.library import LibraryClient, LibraryClientError
from library_tracker.clients.openlibrary import OpenLibraryError
from library_tracker.clients.reado import ReadoError
from library_tracker.clients.telegram import TelegramClient, TelegramError
from library_tracker.config import (
    ConfigurationError,
    configured_reado_list_types,
    get_telegram_settings,
    second_wishlist_heading,
)
from library_tracker.database import get_connection, initialize_database
from library_tracker.models import ReadoListType
from library_tracker.output import (
    format_history_line,
    format_match_report,
    format_telegram_message,
    print_scrape_result,
)
from library_tracker.repositories.availability import get_copy_history
from library_tracker.repositories.telegram_overviews import (
    get_last_fingerprint,
    overview_fingerprint,
    save_fingerprint,
)
from library_tracker.services.library_matching import (
    add_matches_to_merkliste,
    build_match_report,
    match_wishlist_book,
    match_wishlist_books,
    search_catalog,
)
from library_tracker.services.sync import run_sync
from library_tracker.services.library_scrape import scrape_library
from library_tracker.services.merkliste_cleanup import remove_finished_from_merkliste
from library_tracker.services.metadata import (
    link_googlebooks_titles,
    lookup_dnb_editions,
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
    scrape = commands.add_parser("scrape", help="Scrape the current library wish list.")
    scrape.add_argument(
        "--telegram",
        action="store_true",
        help="Send the available/orderable overview via Telegram.",
    )
    commands.add_parser("telegram-test", help="Send a Telegram test message.")

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
    commands.add_parser(
        "dnb-editions",
        help="Find German print editions in the Deutsche Nationalbibliothek.",
    )
    commands.add_parser(
        "openlibrary-link-titles",
        help="Find Open Library works by title/author for Google-Books-only ISBNs.",
    )
    editions = commands.add_parser(
        "openlibrary-editions", help="Cache DE/EN editions for wishlist works."
    )
    editions.add_argument(
        "--refresh",
        action="store_true",
        help="Reload editions for already synced works too.",
    )

    library_search = commands.add_parser("library-search", help="Search Bremen catalog by ISBN.")
    library_search.add_argument("isbn")

    library_match = commands.add_parser(
        "library-match",
        help="Match one READO wishlist book using prioritized German ISBNs.",
    )
    library_match.add_argument("isbn")

    commands.add_parser(
        "match-report",
        help="Show for every READO wishlist book whether and how it matches the catalog.",
    )
    commands.add_parser(
        "match-books",
        help="Search the catalog for unmatched wishlist books (continues where the last run stopped).",
    )
    commands.add_parser(
        "merkliste-add",
        help="Put matched wishlist books on the library Merkliste (never orders or reservations).",
    )
    commands.add_parser(
        "merkliste-cleanup",
        help="Remove books on finished READO lists (TBR, reading, completed, abandoned) from the Merkliste.",
    )
    sync = commands.add_parser(
        "sync",
        help="Daily pipeline: READO, metadata, catalog matches, Merkliste, overview.",
    )
    sync.add_argument(
        "--telegram",
        action="store_true",
        help="Send the overview via Telegram, but only if it changed since the last message.",
    )
    sync.add_argument(
        "--always",
        action="store_true",
        help="With --telegram: send the overview even if nothing changed.",
    )
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
    list_types: tuple[ReadoListType, ...] = (
        ("wishlist",) if wishlist_only else configured_reado_list_types()
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


def _run_openlibrary_link_titles() -> int:
    results = link_googlebooks_titles()
    linked = sum(work_key is not None for _, work_key in results)
    print(f"Google-Books-only ISBNs searched by title: {len(results)}")
    print(f"Linked to Open Library works: {linked}")
    for isbn, work_key in results:
        print(f"{isbn} -> {work_key or 'no match'}")
    return 0


def _run_dnb_editions() -> int:
    results, failed = lookup_dnb_editions()
    print(f"Wishlist books looked up in DNB: {len(results)}")
    print(f"Found in DNB: {sum(found for _, found, _ in results)}")
    print(f"German print editions cached: {sum(count for _, _, count in results)}")
    for isbn, found, count in results:
        print(f"{isbn}: {'found' if found else 'not found'}, {count} edition(s)")
    if failed:
        print(f"Failed (will be retried next run): {', '.join(failed)}")
    return 0


def _run_match_report() -> int:
    print(format_match_report(build_match_report()))
    return 0


def _run_match_books() -> int:
    summary = match_wishlist_books()
    print(
        f"Wishlist books checked: {summary['books']} | ISBNs searched: {summary['searched']}"
        f" | new matches: {summary['new_matches']} | new editions: {summary['new_editions']}"
        f" | errors: {summary['errors']}"
    )
    return 0


def _run_merkliste_add() -> int:
    scrape = scrape_library()
    results = add_matches_to_merkliste(
        scrape["all_titles"],
        existing_media_numbers=[
            number for entry in scrape["entries"] for number in entry.get("media_numbers", [])
        ],
    )
    for reado_isbn, title, status in results:
        print(f"{reado_isbn} | {title} | {status}")
    print(f"Added to Merkliste: {sum(status == 'added' for _, _, status in results)}")
    return 0


def _run_merkliste_cleanup() -> int:
    client = LibraryClient.login()
    results = remove_finished_from_merkliste(scrape_library(client)["entries"], client)
    for isbn13, title, status in results:
        print(f"{isbn13} | {title} | {status}")
    print(f"Removed from Merkliste: {sum(status == 'removed' for _, _, status in results)}")
    return 0


def _send_overview_if_changed(client: TelegramClient, message: str, *, always: bool) -> bool:
    """Send the overview unless it equals the last one sent (ignoring the date).

    Messages with warnings are always sent. Returns whether a message was sent."""
    fingerprint = overview_fingerprint(message)
    connection = get_connection()
    try:
        initialize_database(connection)
        if not always and get_last_fingerprint(connection, client.chat_id) == fingerprint:
            return False
        client.send_message(message)
        save_fingerprint(connection, client.chat_id, fingerprint)
    finally:
        connection.close()
    return True


def _run_sync(*, telegram: bool, always: bool = False) -> int:
    client = _telegram_client() if telegram else None
    report = run_sync()
    if report.scrape is not None:
        print_scrape_result(report.scrape)
    if report.added_titles:
        print(f"\nNeu auf der Merkliste: {', '.join(report.added_titles)}")
    if report.removed_titles:
        print(f"\nVon der Merkliste entfernt: {', '.join(report.removed_titles)}")
    if report.review_titles:
        print(f"\nBitte prüfen (nicht hinzugefügt): {', '.join(report.review_titles)}")
    if report.warnings:
        print(f"\nWarnungen: {'; '.join(report.warnings)}")
    if client is not None:
        if report.scrape is None:
            client.send_message(
                "⚠️ library-tracker: Die Merkliste konnte heute nicht gelesen werden ("
                + "; ".join(report.warnings)
                + ")."
            )
            print("Telegram warning sent.")
        else:
            message = format_telegram_message(
                report.scrape["items"],
                added_titles=report.added_titles,
                warnings=report.warnings,
                review_titles=report.review_titles,
                removed_titles=report.removed_titles,
                second_wishlist_titles=report.second_wishlist_titles,
                own_wishlist_titles=report.own_wishlist_titles,
                second_wishlist_heading=second_wishlist_heading(),
            )
            if _send_overview_if_changed(client, message, always=always or bool(report.warnings)):
                print("Telegram overview sent.")
            else:
                print("Overview unchanged since the last Telegram message, nothing sent.")
    return 1 if report.warnings else 0


def _run_openlibrary_editions(*, refresh: bool = False) -> int:
    summary = sync_openlibrary_editions(refresh=refresh)
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


def _telegram_client() -> TelegramClient:
    token, chat_id = get_telegram_settings()
    return TelegramClient(token, chat_id)


def _run_scrape(*, telegram: bool) -> int:
    client = _telegram_client() if telegram else None
    result = scrape_library()
    print_scrape_result(result)
    if client is not None:
        client.send_message(format_telegram_message(result["items"]))
        print("Telegram overview sent.")
    return 0


def _run_telegram_test() -> int:
    _telegram_client().send_message("✅ library-tracker kann dir Nachrichten schicken.")
    print("Telegram test message sent.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in (None, "scrape"):
            return _run_scrape(telegram=bool(getattr(args, "telegram", False)))
        if args.command == "telegram-test":
            return _run_telegram_test()
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
        if args.command == "dnb-editions":
            return _run_dnb_editions()
        if args.command == "openlibrary-link-titles":
            return _run_openlibrary_link_titles()
        if args.command == "openlibrary-editions":
            return _run_openlibrary_editions(refresh=bool(args.refresh))
        if args.command == "match-report":
            return _run_match_report()
        if args.command == "match-books":
            return _run_match_books()
        if args.command == "merkliste-add":
            return _run_merkliste_add()
        if args.command == "merkliste-cleanup":
            return _run_merkliste_cleanup()
        if args.command == "sync":
            return _run_sync(telegram=bool(args.telegram), always=bool(args.always))
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
        DnbError,
        TelegramError,
    ) as exc:
        print(f"Error: {exc}")
        return 1

    return 2
