from __future__ import annotations

import argparse
import sqlite3
from collections.abc import Sequence

from library_tracker.database import get_connection, initialize_database
from library_tracker.main import main as run_scrape
from library_tracker.models import AvailabilitySnapshot
from library_tracker.repository import get_copy_history


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

    return parser


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


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in (None, "scrape"):
        run_scrape()
        return 0

    if args.command == "history":
        return run_history_command(str(args.media_number))

    parser.error(f"Unknown command: {args.command}")
    return 2
