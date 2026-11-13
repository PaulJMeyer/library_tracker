from __future__ import annotations

import sqlite3

from library_tracker.models import ReadoListEntry, ReadoListSyncResult, ReadoListType


def sync_reado_list(
    connection: sqlite3.Connection,
    entries: list[ReadoListEntry],
    list_type: ReadoListType,
    checked_at: str,
) -> ReadoListSyncResult:
    existing_isbns = {
        str(row[0]) for row in connection.execute("SELECT isbn13 FROM reado_books")
    }
    active_isbns = {
        str(row[0])
        for row in connection.execute(
            """
            SELECT isbn13
            FROM reado_list_memberships
            WHERE list_type = ? AND is_active = 1
            """,
            (list_type,),
        )
    }
    current_isbns = {entry["isbn13"] for entry in entries}
    new_entries = [entry for entry in entries if entry["isbn13"] not in existing_isbns]

    with connection:
        connection.executemany(
            """
            INSERT INTO reado_books (isbn13, reado_url, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(isbn13) DO UPDATE SET
                reado_url = excluded.reado_url,
                last_seen_at = excluded.last_seen_at
            """,
            [
                (entry["isbn13"], entry["reado_url"], checked_at, checked_at)
                for entry in entries
            ],
        )
        connection.execute(
            "UPDATE reado_list_memberships SET is_active = 0 WHERE list_type = ?",
            (list_type,),
        )
        connection.executemany(
            """
            INSERT INTO reado_list_memberships (
                isbn13, list_type, first_seen_at, last_seen_at, is_active
            ) VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(isbn13, list_type) DO UPDATE SET
                last_seen_at = excluded.last_seen_at,
                is_active = 1
            """,
            [
                (entry["isbn13"], list_type, checked_at, checked_at)
                for entry in entries
            ],
        )

    return {
        "new_entries": new_entries,
        "removed_isbns": sorted(active_isbns - current_isbns),
    }
