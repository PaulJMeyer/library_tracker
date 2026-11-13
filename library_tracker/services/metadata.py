from __future__ import annotations

from datetime import UTC, datetime
import time

from library_tracker.clients.googlebooks import GoogleBooksClient
from library_tracker.clients.openlibrary import OpenLibraryClient
from library_tracker.config import require_env
from library_tracker.database import get_connection, initialize_database
from library_tracker.models import GoogleBooksResolution, OpenLibraryResolution
from library_tracker.repositories.metadata import (
    get_googlebooks_fallback_isbns,
    get_unresolved_reado_isbns,
    get_unsynced_wishlist_work_keys,
    save_googlebooks_resolutions,
    save_openlibrary_editions,
    save_openlibrary_resolutions,
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def resolve_openlibrary() -> tuple[int, list[OpenLibraryResolution]]:
    connection = get_connection()
    try:
        initialize_database(connection)
        isbns = get_unresolved_reado_isbns(connection)
        if not isbns:
            return 0, []
        resolutions = OpenLibraryClient(
            require_env("OPENLIBRARY_CONTACT_EMAIL")
        ).resolve_isbns(isbns)
        save_openlibrary_resolutions(connection, resolutions, _now())
        return len(isbns), resolutions
    finally:
        connection.close()


def resolve_googlebooks() -> tuple[int, list[GoogleBooksResolution]]:
    connection = get_connection()
    try:
        initialize_database(connection)
        isbns = get_googlebooks_fallback_isbns(connection)
        if not isbns:
            return 0, []
        resolutions = GoogleBooksClient(
            require_env("GOOGLE_BOOKS_API_KEY")
        ).resolve_isbns(isbns)
        save_googlebooks_resolutions(connection, resolutions, _now())
        return len(isbns), resolutions
    finally:
        connection.close()


def sync_openlibrary_editions() -> list[tuple[str, int]]:
    connection = get_connection()
    try:
        initialize_database(connection)
        work_keys = get_unsynced_wishlist_work_keys(connection)
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
    finally:
        connection.close()
