from __future__ import annotations

import argparse
import sqlite3
import os
import time
from collections.abc import Sequence
from dotenv import load_dotenv
from datetime import UTC, datetime

from library_tracker.database import    (get_connection,
                                         initialize_database)
from library_tracker.main import main as run_scrape
from library_tracker.models import      (AvailabilitySnapshot,
                                         ReadoListType,
                                         ReadoListEntry)
from library_tracker.repository import  (get_copy_history,
                                         sync_reado_list,
                                         get_unresolved_reado_isbns,
                                         save_openlibrary_resolutions,
                                         get_googlebooks_fallback_isbns,
                                         save_googlebooks_resolutions,
                                         get_unsynced_wishlist_work_keys,
                                         save_openlibrary_editions)
from library_tracker.reado import       (ReadoWishlistError,
                                         read_reado_list)
from library_tracker.openlibrary import (OpenLibraryClient,
                                         OpenLibraryError)
from library_tracker.googlebooks import (GoogleBooksClient,
                                         GoogleBooksError)


load_dotenv()

READO_LIST_TYPES: tuple[ReadoListType, ...] = (
    "wishlist",
    "tbr",
    "reading",
    "completed",
)

READO_LIST_ENV_VARS: dict[ReadoListType, str] = {
    "wishlist": "READO_WISHLIST_URL",
    "tbr": "READO_TBR_URL",
    "reading": "READO_READING_URL",
    "completed": "READO_COMPLETED_URL",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="library-tracker",
        description=(
            "Check library availability and inspect stored "
            "SQLite availability history."
        ),
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "scrape",
        help="Run the normal library scrape.",
    )

    subparsers.add_parser(
        "openlibrary-resolve",
        help=(
            "Resolve uncached READO ISBNs "
            "with Open Library."
        ),
    )

    subparsers.add_parser(
        "googlebooks-resolve",
        help=(
            "Resolve Open Library fallback ISBNs "
            "with Google Books."
        ),
    )

    subparsers.add_parser(
        "openlibrary-editions",
        help=(
            "Cache German and English print "
            "editions for wishlist works."
        ),
    )

    history_parser = subparsers.add_parser(
        "history",
        help="Show availability history for one library copy.",
    )
    history_parser.add_argument(
        "media_number",
        help="Media number of the library copy.",
    )

    reado_parser = subparsers.add_parser(
        "reado-wishlist",
        help="Read ISBNs from a public READO wishlist.",
    )

    reado_parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the READO browser without a visible window.",
    )

    reado_sync_parser = subparsers.add_parser(
        "reado-sync",
        help="Synchronize all configured READO lists.",
    )

    reado_sync_parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the READO browser without a visible window.",
    )

    return parser


def get_reado_list_url(
    list_type: ReadoListType,
) -> str:
    variable_name = READO_LIST_ENV_VARS[list_type]
    list_url = os.getenv(variable_name)

    if not list_url:
        raise ReadoWishlistError(
            f"{variable_name} is not configured."
        )

    return list_url


def format_history_line(snapshot: AvailabilitySnapshot) -> str:
    due_date = snapshot["due_date"]
    due_suffix = f" | due: {due_date}" if due_date else ""

    return (
        f'{snapshot["checked_at"]} | '
        f'{snapshot["status"]} | '
        f'{snapshot["status_text"]}'
        f"{due_suffix}"
    )


def print_copy_history(
    connection: sqlite3.Connection,
    media_number: str,
) -> bool:
    history = get_copy_history(connection, media_number)

    if not history:
        print(f"No history found for copy {media_number}.")
        return False

    print(f"Availability history for copy {media_number}:")
    for snapshot in history:
        print(format_history_line(snapshot))

    return True


def run_history_command(media_number: str) -> int:
    connection = get_connection()

    try:
        initialize_database(connection)
        found = print_copy_history(connection, media_number)
    finally:
        connection.close()

    return 0 if found else 1


def run_reado_wishlist_command(
    *,
    headless: bool = False,
) -> int:
    try:
        wishlist_url = get_reado_list_url("wishlist")

        entries = read_reado_list(
            wishlist_url,
            headless=headless,
        )
    except ReadoWishlistError as exc:
        print(f"READO error: {exc}")
        return 1

    checked_at = datetime.now(UTC).isoformat(
        timespec="seconds"
    )

    connection = get_connection()

    try:
        initialize_database(connection)

        sync_result = sync_reado_list(
            connection,
            entries,
            "wishlist",
            checked_at,
        )
    finally:
        connection.close()

    print(f"READO wishlist: {len(entries)} books")
    print(
        "New books: "
        f'{len(sync_result["new_entries"])}'
    )
    print(
        "Removed books: "
        f'{len(sync_result["removed_isbns"])}'
    )

    for entry in entries:
        print(
            f'{entry["isbn13"]} | '
            f'{entry["reado_url"]}'
        )

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in (None, "scrape"):
        run_scrape()
        return 0

    if args.command == "history":
        return run_history_command(str(args.media_number))

    if args.command == "reado-wishlist":
        return run_reado_wishlist_command(
            headless=bool(args.headless),
        )

    if args.command == "reado-sync":
        return run_reado_sync_command(
            headless=bool(args.headless),
        )

    if args.command == "openlibrary-resolve":
        return run_openlibrary_resolve_command()

    if args.command == "googlebooks-resolve":
        return run_googlebooks_resolve_command()

    if args.command == "openlibrary-editions":
        return run_openlibrary_editions_command()

    parser.error(f"Unknown command: {args.command}")
    return 2


def run_reado_sync_command(
    *,
    headless: bool = False,
) -> int:
    entries_by_list: dict[
        ReadoListType,
        list[ReadoListEntry],
    ] = {}

    try:
        for list_type in READO_LIST_TYPES:
            list_url = get_reado_list_url(list_type)

            entries_by_list[list_type] = read_reado_list(
                list_url,
                headless=headless,
            )

    except ReadoWishlistError as exc:
        print(f"READO error: {exc}")
        return 1

    checked_at = datetime.now(UTC).isoformat(
        timespec="seconds"
    )

    connection = get_connection()

    try:
        initialize_database(connection)

        total_new_isbns: set[str] = set()

        for list_type in READO_LIST_TYPES:
            entries = entries_by_list[list_type]

            result = sync_reado_list(
                connection,
                entries,
                list_type,
                checked_at,
            )

            total_new_isbns.update(
                entry["isbn13"]
                for entry in result["new_entries"]
            )

            print(
                f"READO {list_type}: "
                f"{len(entries)} books"
            )

            print(
                "  New to cache: "
                f'{len(result["new_entries"])}'
            )

            print(
                "  Removed from list: "
                f'{len(result["removed_isbns"])}'
            )

        print(
            "Total new books: "
            f"{len(total_new_isbns)}"
        )

    finally:
        connection.close()

    return 0


def get_openlibrary_contact_email() -> str:
    contact_email = os.getenv(
        "OPENLIBRARY_CONTACT_EMAIL"
    )

    if not contact_email:
        raise OpenLibraryError(
            "OPENLIBRARY_CONTACT_EMAIL "
            "is not configured."
        )

    return contact_email


def run_openlibrary_resolve_command() -> int:
    try:
        contact_email = (
            get_openlibrary_contact_email()
        )
    except OpenLibraryError as exc:
        print(f"Open Library error: {exc}")
        return 1

    connection = get_connection()

    try:
        initialize_database(connection)

        unresolved_isbns = (
            get_unresolved_reado_isbns(
                connection
            )
        )

        print(
            "Unresolved ISBNs: "
            f"{len(unresolved_isbns)}"
        )

        if not unresolved_isbns:
            return 0

        client = OpenLibraryClient(
            contact_email
        )

        try:
            resolutions = client.resolve_isbns(
                unresolved_isbns
            )
        except OpenLibraryError as exc:
            print(
                f"Open Library error: {exc}"
            )
            return 1

        resolved_at = datetime.now(
            UTC
        ).isoformat(
            timespec="seconds"
        )

        save_openlibrary_resolutions(
            connection,
            resolutions,
            resolved_at,
        )

    finally:
        connection.close()

    resolved = sum(
        result["status"] == "resolved"
        for result in resolutions
    )

    not_found = sum(
        result["status"] == "not_found"
        for result in resolutions
    )

    ambiguous = sum(
        result["status"] == "ambiguous"
        for result in resolutions
    )

    print(f"Resolved: {resolved}")
    print(f"Not found: {not_found}")
    print(f"Ambiguous: {ambiguous}")

    return 0


def get_google_books_api_key() -> str:
    api_key = os.getenv("GOOGLE_BOOKS_API_KEY")

    if not api_key:
        raise GoogleBooksError(
            "GOOGLE_BOOKS_API_KEY is not configured."
        )

    return api_key


def run_googlebooks_resolve_command() -> int:
    try:
        api_key = get_google_books_api_key()
    except GoogleBooksError as exc:
        print(f"Google Books error: {exc}")
        return 1

    connection = get_connection()

    try:
        initialize_database(connection)

        fallback_isbns = (
            get_googlebooks_fallback_isbns(
                connection
            )
        )

        print(
            "Google Books fallback ISBNs: "
            f"{len(fallback_isbns)}"
        )

        if not fallback_isbns:
            return 0

        client = GoogleBooksClient(api_key)

        try:
            resolutions = client.resolve_isbns(
                fallback_isbns
            )
        except GoogleBooksError as exc:
            print(f"Google Books error: {exc}")
            return 1

        resolved_at = datetime.now(
            UTC
        ).isoformat(
            timespec="seconds"
        )

        save_googlebooks_resolutions(
            connection,
            resolutions,
            resolved_at,
        )

    finally:
        connection.close()

    found = sum(
        result["status"] == "found"
        for result in resolutions
    )

    not_found = sum(
        result["status"] == "not_found"
        for result in resolutions
    )

    ambiguous = sum(
        result["status"] == "ambiguous"
        for result in resolutions
    )

    failed = sum(
        result["status"] == "failed"
        for result in resolutions
    )

    print(f"Found: {found}")
    print(f"Not found: {not_found}")
    print(f"Ambiguous: {ambiguous}")
    print(f"Failed: {failed}")

    return 0


def run_openlibrary_editions_command() -> int:
    try:
        contact_email = (
            get_openlibrary_contact_email()
        )
    except OpenLibraryError as exc:
        print(f"Open Library error: {exc}")
        return 1

    connection = get_connection()

    try:
        initialize_database(connection)

        work_keys = (
            get_unsynced_wishlist_work_keys(
                connection
            )
        )

        print(
            "Wishlist works needing editions: "
            f"{len(work_keys)}"
        )

        if not work_keys:
            return 0

        client = OpenLibraryClient(
            contact_email
        )

        total_editions = 0

        for index, work_key in enumerate(
            work_keys,
            start=1,
        ):
            try:
                editions = (
                    client.get_work_editions(
                        work_key
                    )
                )
            except OpenLibraryError as exc:
                print(
                    f"Open Library error: {exc}"
                )
                return 1

            synced_at = datetime.now(
                UTC
            ).isoformat(
                timespec="seconds"
            )

            save_openlibrary_editions(
                connection,
                work_key,
                editions,
                synced_at,
            )

            total_editions += len(editions)

            print(
                f"[{index}/{len(work_keys)}] "
                f"{work_key}: "
                f"{len(editions)} relevant editions"
            )

            time.sleep(0.5)

    finally:
        connection.close()

    print(
        "Relevant editions cached: "
        f"{total_editions}"
    )

    return 0