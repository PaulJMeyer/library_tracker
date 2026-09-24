from __future__ import annotations

import datetime
import sqlite3
from collections.abc import Iterable
from typing import cast

from library_tracker.models import AvailabilitySnapshot, Item


SnapshotRow = tuple[str, str, str, str, str | None]


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
