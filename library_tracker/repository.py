from __future__ import annotations

import datetime
import sqlite3
import json
from collections.abc import Iterable
from typing import cast

from library_tracker.models import (AvailabilitySnapshot,
                                    Item,
                                    ReadoListEntry,
                                    ReadoListSyncResult,
                                    ReadoListType,
                                    OpenLibraryResolution,
                                    GoogleBooksResolution,
                                    OpenLibraryEdition)


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


def sync_reado_list(
    connection: sqlite3.Connection,
    entries: list[ReadoListEntry],
    list_type: ReadoListType,
    checked_at: str,
) -> ReadoListSyncResult:
    existing_isbns = {
        str(row[0])
        for row in connection.execute(
            "SELECT isbn13 FROM reado_books"
        )
    }

    active_isbns = {
        str(row[0])
        for row in connection.execute(
            """
            SELECT isbn13
            FROM reado_list_memberships
            WHERE list_type = ?
              AND is_active = 1
            """,
            (list_type,),
        )
    }

    current_isbns = {
        entry["isbn13"]
        for entry in entries
    }

    new_entries = [
        entry
        for entry in entries
        if entry["isbn13"] not in existing_isbns
    ]

    removed_isbns = sorted(
        active_isbns - current_isbns
    )

    connection.executemany(
        """
        INSERT INTO reado_books (
            isbn13,
            reado_url,
            first_seen_at,
            last_seen_at
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(isbn13) DO UPDATE SET
            reado_url = excluded.reado_url,
            last_seen_at = excluded.last_seen_at
        """,
        [
            (
                entry["isbn13"],
                entry["reado_url"],
                checked_at,
                checked_at,
            )
            for entry in entries
        ],
    )

    connection.execute(
        """
        UPDATE reado_list_memberships
        SET is_active = 0
        WHERE list_type = ?
        """,
        (list_type,),
    )

    connection.executemany(
        """
        INSERT INTO reado_list_memberships (
            isbn13,
            list_type,
            first_seen_at,
            last_seen_at,
            is_active
        )
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(isbn13, list_type) DO UPDATE SET
            last_seen_at = excluded.last_seen_at,
            is_active = 1
        """,
        [
            (
                entry["isbn13"],
                list_type,
                checked_at,
                checked_at,
            )
            for entry in entries
        ],
    )

    connection.commit()

    return {
        "new_entries": new_entries,
        "removed_isbns": removed_isbns,
    }


def get_unresolved_reado_isbns(
    connection: sqlite3.Connection,
) -> list[str]:
    rows = connection.execute(
        """
        SELECT rb.isbn13
        FROM reado_books AS rb
        LEFT JOIN bibliographic_resolutions AS br
            ON br.isbn13 = rb.isbn13
        WHERE br.isbn13 IS NULL
        ORDER BY rb.isbn13
        """
    ).fetchall()

    return [
        str(row[0])
        for row in rows
    ]


def save_openlibrary_resolutions(
    connection: sqlite3.Connection,
    resolutions: list[OpenLibraryResolution],
    resolved_at: str,
) -> None:
    for resolution in resolutions:
        work_key = resolution["work_key"]
        title = resolution["title"]

        if (
            resolution["status"] == "resolved"
            and work_key is not None
            and title is not None
        ):
            connection.execute(
                """
                INSERT INTO openlibrary_works (
                    work_key,
                    title
                )
                VALUES (?, ?)
                ON CONFLICT(work_key) DO UPDATE SET
                    title = excluded.title
                """,
                (
                    work_key,
                    title,
                ),
            )

        connection.execute(
            """
            INSERT INTO bibliographic_resolutions (
                isbn13,
                status,
                work_key,
                resolved_at,
                source,
                error_message
            )
            VALUES (?, ?, ?, ?, 'openlibrary', ?)
            ON CONFLICT(isbn13) DO UPDATE SET
                status = excluded.status,
                work_key = excluded.work_key,
                resolved_at = excluded.resolved_at,
                source = excluded.source,
                error_message = excluded.error_message
            """,
            (
                resolution["isbn13"],
                resolution["status"],
                work_key,
                resolved_at,
                resolution["error_message"],
            ),
        )

    connection.commit()


def get_googlebooks_fallback_isbns(
    connection: sqlite3.Connection,
) -> list[str]:
    rows = connection.execute(
        """
        SELECT br.isbn13
        FROM bibliographic_resolutions AS br
        LEFT JOIN google_books_resolutions AS gbr
            ON gbr.isbn13 = br.isbn13
        WHERE br.source = 'openlibrary'
          AND br.status = 'not_found'
          AND gbr.isbn13 IS NULL
        ORDER BY br.isbn13
        """
    ).fetchall()

    return [
        str(row[0])
        for row in rows
    ]


def save_googlebooks_resolutions(
    connection: sqlite3.Connection,
    resolutions: list[GoogleBooksResolution],
    resolved_at: str,
) -> None:
    for resolution in resolutions:
        volume_id = resolution["volume_id"]

        if (
            resolution["status"] == "found"
            and volume_id is not None
            and resolution["title"] is not None
        ):
            connection.execute(
                """
                INSERT INTO google_books_volumes (
                    volume_id,
                    title,
                    authors_json,
                    language,
                    publisher,
                    published_date
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(volume_id) DO UPDATE SET
                    title = excluded.title,
                    authors_json = excluded.authors_json,
                    language = excluded.language,
                    publisher = excluded.publisher,
                    published_date = excluded.published_date
                """,
                (
                    volume_id,
                    resolution["title"],
                    json.dumps(
                        resolution["authors"],
                        ensure_ascii=False,
                    ),
                    resolution["language"],
                    resolution["publisher"],
                    resolution["published_date"],
                ),
            )

            connection.execute(
                """
                DELETE FROM google_books_identifiers
                WHERE volume_id = ?
                """,
                (volume_id,),
            )

            connection.executemany(
                """
                INSERT INTO google_books_identifiers (
                    volume_id,
                    identifier_type,
                    identifier
                )
                VALUES (?, ?, ?)
                """,
                [
                    (
                        volume_id,
                        identifier["type"],
                        identifier["identifier"],
                    )
                    for identifier
                    in resolution["identifiers"]
                ],
            )

        connection.execute(
            """
            INSERT INTO google_books_resolutions (
                isbn13,
                status,
                volume_id,
                resolved_at,
                error_message
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(isbn13) DO UPDATE SET
                status = excluded.status,
                volume_id = excluded.volume_id,
                resolved_at = excluded.resolved_at,
                error_message = excluded.error_message
            """,
            (
                resolution["isbn13"],
                resolution["status"],
                volume_id,
                resolved_at,
                resolution["error_message"],
            ),
        )

    connection.commit()


def get_unsynced_wishlist_work_keys(
    connection: sqlite3.Connection,
) -> list[str]:
    rows = connection.execute(
        """
        SELECT DISTINCT br.work_key
        FROM reado_list_memberships AS rlm
        JOIN bibliographic_resolutions AS br
            ON br.isbn13 = rlm.isbn13
        LEFT JOIN openlibrary_edition_syncs AS oes
            ON oes.work_key = br.work_key
        WHERE rlm.list_type = 'wishlist'
          AND rlm.is_active = 1
          AND br.source = 'openlibrary'
          AND br.status = 'resolved'
          AND br.work_key IS NOT NULL
          AND oes.work_key IS NULL
        ORDER BY br.work_key
        """
    ).fetchall()

    return [
        str(row[0])
        for row in rows
    ]


def save_openlibrary_editions(
    connection: sqlite3.Connection,
    work_key: str,
    editions: list[OpenLibraryEdition],
    synced_at: str,
) -> None:
    with connection:
        connection.execute(
            """
            DELETE FROM openlibrary_editions
            WHERE work_key = ?
            """,
            (work_key,),
        )

        for edition in editions:
            connection.execute(
                """
                INSERT INTO openlibrary_editions (
                    edition_key,
                    work_key,
                    title,
                    physical_format,
                    print_status
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    edition["edition_key"],
                    edition["work_key"],
                    edition["title"],
                    edition["physical_format"],
                    edition["print_status"],
                ),
            )

            connection.executemany(
                """
                INSERT INTO openlibrary_edition_languages (
                    edition_key,
                    language
                )
                VALUES (?, ?)
                """,
                [
                    (
                        edition["edition_key"],
                        language,
                    )
                    for language
                    in edition["languages"]
                ],
            )

            connection.executemany(
                """
                INSERT INTO openlibrary_edition_isbns (
                    edition_key,
                    isbn_type,
                    isbn
                )
                VALUES (?, ?, ?)
                """,
                [
                    (
                        edition["edition_key"],
                        identifier["type"],
                        identifier["identifier"],
                    )
                    for identifier
                    in edition["identifiers"]
                ],
            )

        connection.execute(
            """
            INSERT INTO openlibrary_edition_syncs (
                work_key,
                synced_at
            )
            VALUES (?, ?)
            ON CONFLICT(work_key) DO UPDATE SET
                synced_at = excluded.synced_at
            """,
            (
                work_key,
                synced_at,
            ),
        )