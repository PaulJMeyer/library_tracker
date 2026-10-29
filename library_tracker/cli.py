from __future__ import annotations

import argparse
import sqlite3
import os
from collections.abc import Sequence
from dotenv import load_dotenv
from datetime import UTC, datetime

from library_tracker.database import (get_connection,
                                      initialize_database)
from library_tracker.main import main as run_scrape
from library_tracker.models import (AvailabilitySnapshot,
                                    ReadoListType)
from library_tracker.repository import (get_copy_history,
                                        sync_reado_list)
from library_tracker.reado import (ReadoWishlistError,
                                   read_reado_wishlist)


load_dotenv()

READO_LIST_ENV_VARS = {
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

        entries = read_reado_wishlist(
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

    parser.error(f"Unknown command: {args.command}")
    return 2
