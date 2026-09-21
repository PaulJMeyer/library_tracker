from __future__ import annotations

import datetime
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import cast

from library_tracker.models import AvailabilitySnapshot, Item


DEFAULT_DB_PATH = Path("data/library_tracker.db")

SnapshotRow = tuple[str, str, str, str, str | None]


def get_connection(path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Create a SQLite connection and enable foreign-key enforcement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    """Create the database schema if it does not exist yet."""
    with connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS copies (
                media_number TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                signature TEXT NOT NULL,
                branch TEXT NOT NULL,
                is_central INTEGER NOT NULL CHECK (is_central IN (0, 1)),
                last_seen_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS availability_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_number TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                status TEXT NOT NULL,
                status_text TEXT NOT NULL,
                due_date TEXT,
                FOREIGN KEY (media_number)
                    REFERENCES copies(media_number)
                    ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_snapshots_media_number_checked_at
            ON availability_snapshots (media_number, checked_at)
            """
        )


def persist_items(
    connection: sqlite3.Connection,
    items: Iterable[Item],
    *,
    checked_at: datetime.datetime | None = None,
) -> None:
    """Store the current state of every parsed copy as a historical snapshot."""
    timestamp = checked_at or datetime.datetime.now(datetime.timezone.utc)

    if timestamp.tzinfo is None:
        raise ValueError("checked_at must be timezone-aware")

    checked_at_iso = timestamp.astimezone(datetime.timezone.utc).isoformat()
    with connection:
        for item in items:
            for copy in item["copies"]:
                connection.execute(
                    """
                    INSERT INTO copies (
                        media_number,
                        title,
                        signature,
                        branch,
                        is_central,
                        last_seen_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(media_number) DO UPDATE SET
                        title = excluded.title,
                        signature = excluded.signature,
                        branch = excluded.branch,
                        is_central = excluded.is_central,
                        last_seen_at = excluded.last_seen_at
                    """,
                    (
                        copy["media_number"],
                        item["title"],
                        copy["signature"],
                        copy["branch"],
                        int(copy["is_central"]),
                        checked_at_iso,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO availability_snapshots (
                        media_number,
                        checked_at,
                        status,
                        status_text,
                        due_date
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        copy["media_number"],
                        checked_at_iso,
                        copy["status"],
                        copy["status_text"],
                        copy["due_date"],
                    ),
                )


def _snapshot_from_row(row: SnapshotRow) -> AvailabilitySnapshot:
    return {
        "media_number": row[0],
        "checked_at": row[1],
        "status": row[2],
        "status_text": row[3],
        "due_date": row[4],
    }


def get_copy_history(
    connection: sqlite3.Connection,
    media_number: str,
) -> list[AvailabilitySnapshot]:
    """Return all stored snapshots for one copy, oldest first."""
    rows = connection.execute(
        """
        SELECT
            media_number,
            checked_at,
            status,
            status_text,
            due_date
        FROM availability_snapshots
        WHERE media_number = ?
        ORDER BY checked_at ASC, id ASC
        """,
        (media_number,),
    ).fetchall()

    return [
        _snapshot_from_row(cast(SnapshotRow, row))
        for row in rows
    ]


def get_latest_snapshot(
    connection: sqlite3.Connection,
    media_number: str,
) -> AvailabilitySnapshot | None:
    """Return the newest stored snapshot for one copy, if available."""
    row = connection.execute(
        """
        SELECT
            media_number,
            checked_at,
            status,
            status_text,
            due_date
        FROM availability_snapshots
        WHERE media_number = ?
        ORDER BY checked_at DESC, id DESC
        LIMIT 1
        """,
        (media_number,),
    ).fetchone()

    if row is None:
        return None

    return _snapshot_from_row(cast(SnapshotRow, row))
