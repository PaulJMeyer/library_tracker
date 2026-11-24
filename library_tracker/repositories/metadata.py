from __future__ import annotations

import json
import sqlite3

from library_tracker.models import GoogleBooksResolution, OpenLibraryEdition, OpenLibraryResolution


def get_unresolved_reado_isbns(connection: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            """
            SELECT rb.isbn13
            FROM reado_books AS rb
            LEFT JOIN bibliographic_resolutions AS br ON br.isbn13 = rb.isbn13
            WHERE br.isbn13 IS NULL
            ORDER BY rb.isbn13
            """
        )
    ]


def save_openlibrary_resolutions(
    connection: sqlite3.Connection,
    resolutions: list[OpenLibraryResolution],
    resolved_at: str,
) -> None:
    with connection:
        for resolution in resolutions:
            work_key = resolution["work_key"]
            title = resolution["title"]
            if resolution["status"] == "resolved" and work_key and title:
                connection.execute(
                    """
                    INSERT INTO openlibrary_works (work_key, title)
                    VALUES (?, ?)
                    ON CONFLICT(work_key) DO UPDATE SET title = excluded.title
                    """,
                    (work_key, title),
                )
            connection.execute(
                """
                INSERT INTO bibliographic_resolutions (
                    isbn13, status, work_key, resolved_at, source, error_message
                ) VALUES (?, ?, ?, ?, 'openlibrary', ?)
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


def get_googlebooks_fallback_isbns(connection: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            """
            SELECT br.isbn13
            FROM bibliographic_resolutions AS br
            LEFT JOIN google_books_resolutions AS gbr ON gbr.isbn13 = br.isbn13
            WHERE br.source = 'openlibrary'
              AND br.status = 'not_found'
              AND gbr.isbn13 IS NULL
            ORDER BY br.isbn13
            """
        )
    ]


def save_googlebooks_resolutions(
    connection: sqlite3.Connection,
    resolutions: list[GoogleBooksResolution],
    resolved_at: str,
) -> None:
    with connection:
        for resolution in resolutions:
            volume_id = resolution["volume_id"]
            if resolution["status"] == "found" and volume_id and resolution["title"]:
                connection.execute(
                    """
                    INSERT INTO google_books_volumes (
                        volume_id, title, authors_json, language, publisher, published_date
                    ) VALUES (?, ?, ?, ?, ?, ?)
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
                        json.dumps(resolution["authors"], ensure_ascii=False),
                        resolution["language"],
                        resolution["publisher"],
                        resolution["published_date"],
                    ),
                )
                connection.execute(
                    "DELETE FROM google_books_identifiers WHERE volume_id = ?",
                    (volume_id,),
                )
                connection.executemany(
                    """
                    INSERT INTO google_books_identifiers (
                        volume_id, identifier_type, identifier
                    ) VALUES (?, ?, ?)
                    """,
                    [
                        (volume_id, identifier["type"], identifier["identifier"])
                        for identifier in resolution["identifiers"]
                    ],
                )

            connection.execute(
                """
                INSERT INTO google_books_resolutions (
                    isbn13, status, volume_id, resolved_at, error_message
                ) VALUES (?, ?, ?, ?, ?)
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


def get_unsynced_wishlist_work_keys(
    connection: sqlite3.Connection,
    *,
    include_synced: bool = False,
) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            """
            SELECT DISTINCT br.work_key
            FROM reado_list_memberships AS rlm
            JOIN bibliographic_resolutions AS br ON br.isbn13 = rlm.isbn13
            LEFT JOIN openlibrary_edition_syncs AS oes ON oes.work_key = br.work_key
            WHERE rlm.list_type = 'wishlist'
              AND rlm.is_active = 1
              AND br.source IN ('openlibrary', 'openlibrary_title')
              AND br.status = 'resolved'
              AND br.work_key IS NOT NULL
              AND (oes.work_key IS NULL OR ?)
            ORDER BY br.work_key
            """,
            (int(include_synced),),
        )
    ]


def save_openlibrary_editions(
    connection: sqlite3.Connection,
    work_key: str,
    editions: list[OpenLibraryEdition],
    synced_at: str,
) -> None:
    with connection:
        connection.execute("DELETE FROM openlibrary_editions WHERE work_key = ?", (work_key,))
        for edition in editions:
            connection.execute(
                """
                INSERT INTO openlibrary_editions (
                    edition_key, work_key, title, physical_format, print_status
                ) VALUES (?, ?, ?, ?, ?)
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
                "INSERT INTO openlibrary_edition_languages (edition_key, language) VALUES (?, ?)",
                [(edition["edition_key"], language) for language in edition["languages"]],
            )
            connection.executemany(
                """
                INSERT INTO openlibrary_edition_isbns (edition_key, isbn_type, isbn)
                VALUES (?, ?, ?)
                """,
                [
                    (edition["edition_key"], identifier["type"], identifier["identifier"])
                    for identifier in edition["identifiers"]
                ],
            )

        connection.execute(
            """
            INSERT INTO openlibrary_edition_syncs (work_key, synced_at)
            VALUES (?, ?)
            ON CONFLICT(work_key) DO UPDATE SET synced_at = excluded.synced_at
            """,
            (work_key, synced_at),
        )


def get_title_link_candidates(
    connection: sqlite3.Connection,
) -> list[tuple[str, str, list[str]]]:
    """ISBNs unknown to Open Library but found by Google Books, not yet title-searched."""
    rows = connection.execute(
        """
        SELECT br.isbn13, gbv.title, gbv.authors_json
        FROM bibliographic_resolutions AS br
        JOIN google_books_resolutions AS gbr ON gbr.isbn13 = br.isbn13
        JOIN google_books_volumes AS gbv ON gbv.volume_id = gbr.volume_id
        LEFT JOIN openlibrary_title_links AS otl ON otl.isbn13 = br.isbn13
        WHERE br.source = 'openlibrary'
          AND br.status = 'not_found'
          AND gbr.status = 'found'
          AND otl.isbn13 IS NULL
        ORDER BY br.isbn13
        """
    ).fetchall()
    result: list[tuple[str, str, list[str]]] = []
    for isbn, title, authors_json in rows:
        authors = json.loads(authors_json) if authors_json else []
        result.append((str(isbn), str(title), [str(a) for a in authors]))
    return result


def save_title_link(
    connection: sqlite3.Connection,
    isbn: str,
    match: tuple[str, str] | None,
    searched_at: str,
) -> None:
    with connection:
        connection.execute(
            """
            INSERT INTO openlibrary_title_links (isbn13, work_key, searched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(isbn13) DO UPDATE SET
                work_key = excluded.work_key,
                searched_at = excluded.searched_at
            """,
            (isbn, match[0] if match else None, searched_at),
        )
        if match is None:
            return
        work_key, title = match
        connection.execute(
            """
            INSERT INTO openlibrary_works (work_key, title) VALUES (?, ?)
            ON CONFLICT(work_key) DO NOTHING
            """,
            (work_key, title),
        )
        connection.execute(
            """
            UPDATE bibliographic_resolutions
            SET status = 'resolved', work_key = ?, source = 'openlibrary_title',
                resolved_at = ?, error_message = NULL
            WHERE isbn13 = ?
            """,
            (work_key, searched_at, isbn),
        )
