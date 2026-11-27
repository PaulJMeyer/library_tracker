from __future__ import annotations

import sqlite3

from library_tracker.config import WISHLIST_TYPES_SQL
from library_tracker.models import LibraryIsbnCandidateSource



def get_recent_misses(connection: sqlite3.Connection, since: str) -> set[str]:
    """ISBNs searched without a hit at or after `since` (skipped until then)."""
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT isbn FROM catalog_searches WHERE hit_url IS NULL AND searched_at >= ?",
            (since,),
        )
    }


def get_searched_isbns(connection: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in connection.execute("SELECT isbn FROM catalog_searches")}


def save_catalog_search(
    connection: sqlite3.Connection,
    isbn: str,
    hit_url: str | None,
    searched_at: str,
) -> None:
    with connection:
        connection.execute(
            """
            INSERT INTO catalog_searches (isbn, hit_url, searched_at) VALUES (?, ?, ?)
            ON CONFLICT(isbn) DO UPDATE SET
                hit_url = excluded.hit_url,
                searched_at = excluded.searched_at
            """,
            (isbn, hit_url, searched_at),
        )


def save_library_match(
    connection: sqlite3.Connection,
    reado_isbn: str,
    matched_isbn: str,
    source: LibraryIsbnCandidateSource,
    matched_at: str,
) -> None:
    with connection:
        connection.execute(
            """
            INSERT INTO library_matches (reado_isbn, matched_isbn, source, matched_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(reado_isbn) DO UPDATE SET
                matched_isbn = excluded.matched_isbn,
                source = excluded.source,
                matched_at = excluded.matched_at,
                memorize_status = NULL,
                memorize_checked_at = NULL
            """,
            (reado_isbn, matched_isbn, source, matched_at),
        )


def save_memorize_result(
    connection: sqlite3.Connection,
    reado_isbn: str,
    status: str,
    catalog_title: str | None,
    checked_at: str,
) -> None:
    with connection:
        connection.execute(
            """
            UPDATE library_matches
            SET memorize_status = ?, catalog_title = COALESCE(?, catalog_title),
                memorize_checked_at = ?
            WHERE reado_isbn = ?
            """,
            (status, catalog_title, checked_at, reado_isbn),
        )


def get_match_states(connection: sqlite3.Connection) -> dict[str, tuple[str, str, str | None]]:
    """reado_isbn -> (matched_isbn, source, memorize_status)."""
    return {
        str(reado_isbn): (str(matched_isbn), str(source), None if status is None else str(status))
        for reado_isbn, matched_isbn, source, status in connection.execute(
            "SELECT reado_isbn, matched_isbn, source, memorize_status FROM library_matches"
        )
    }


def get_wishlist_catalog_titles(connection: sqlite3.Connection, list_type: str) -> list[str]:
    """Catalog titles of all found editions of the books active on the given wishlist."""
    return [
        str(row[0])
        for row in connection.execute(
            """
            SELECT lm.catalog_title
            FROM library_matches AS lm
            JOIN reado_list_memberships AS rlm
              ON rlm.isbn13 = lm.reado_isbn AND rlm.list_type = ? AND rlm.is_active = 1
            WHERE lm.catalog_title IS NOT NULL
            UNION
            SELECT ce.catalog_title
            FROM catalog_editions AS ce
            JOIN reado_list_memberships AS rlm
              ON rlm.isbn13 = ce.reado_isbn AND rlm.list_type = ? AND rlm.is_active = 1
            WHERE ce.catalog_title IS NOT NULL
            ORDER BY 1
            """,
            (list_type, list_type),
        )
    ]


def get_wishlist_isbns_for_search(connection: sqlite3.Connection) -> list[tuple[str, bool]]:
    """(isbn13, already matched) of active wishlist books, books without a match first."""
    return [
        (str(isbn13), bool(matched))
        for isbn13, matched in connection.execute(
            """
            SELECT rlm.isbn13, lm.reado_isbn IS NOT NULL AS matched
            FROM reado_list_memberships AS rlm
            LEFT JOIN library_matches AS lm ON lm.reado_isbn = rlm.isbn13
            WHERE rlm.list_type = 'wishlist' AND rlm.is_active = 1
            ORDER BY matched, rlm.isbn13
            """
        )
    ]


def get_catalog_hits(connection: sqlite3.Connection) -> set[str]:
    """ISBNs that were found in the catalog (searched again only via their edition)."""
    return {
        str(row[0])
        for row in connection.execute("SELECT isbn FROM catalog_searches WHERE hit_url IS NOT NULL")
    }


def get_edition_isbns(connection: sqlite3.Connection, reado_isbn: str) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT isbn FROM catalog_editions WHERE reado_isbn = ?", (reado_isbn,)
        )
    }


def save_catalog_edition(
    connection: sqlite3.Connection,
    reado_isbn: str,
    isbn: str,
    source: LibraryIsbnCandidateSource,
    found_at: str,
) -> None:
    with connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO catalog_editions (reado_isbn, isbn, source, found_at)
            VALUES (?, ?, ?, ?)
            """,
            (reado_isbn, isbn, source, found_at),
        )


def get_editions_to_memorize(connection: sqlite3.Connection) -> list[tuple[str, str]]:
    """(reado_isbn, edition isbn) of active wishlist editions not yet on the Merkliste.

    English editions only count when no other edition of the book is in the catalog.
    """
    return [
        (str(reado_isbn), str(isbn))
        for reado_isbn, isbn in connection.execute(
            """
            SELECT ce.reado_isbn, ce.isbn
            FROM catalog_editions AS ce
            JOIN reado_list_memberships AS rlm
              ON rlm.isbn13 = ce.reado_isbn AND rlm.list_type = 'wishlist' AND rlm.is_active = 1
            WHERE (ce.memorize_status IS NULL OR ce.memorize_status = 'failed')
              AND NOT (
                  ce.source = 'openlibrary_english'
                  AND EXISTS (
                      SELECT 1 FROM catalog_editions AS other
                      WHERE other.reado_isbn = ce.reado_isbn
                        AND other.source != 'openlibrary_english'
                  )
              )
            ORDER BY ce.reado_isbn,
                CASE ce.source
                    WHEN 'reado' THEN 0
                    WHEN 'openlibrary_confirmed' THEN 1
                    WHEN 'dnb' THEN 2
                    WHEN 'openlibrary_unknown' THEN 3
                    ELSE 4
                END,
                ce.isbn
            """
        )
    ]


def save_edition_memorize_result(
    connection: sqlite3.Connection,
    reado_isbn: str,
    isbn: str,
    status: str,
    catalog_title: str | None,
    media_numbers: list[str],
    checked_at: str,
) -> None:
    with connection:
        connection.execute(
            """
            UPDATE catalog_editions
            SET memorize_status = ?, catalog_title = COALESCE(?, catalog_title),
                media_numbers = COALESCE(?, media_numbers), memorize_checked_at = ?
            WHERE reado_isbn = ? AND isbn = ?
            """,
            (
                status,
                catalog_title,
                " ".join(media_numbers) or None,
                checked_at,
                reado_isbn,
                isbn,
            ),
        )
        # Keep the first match's status in sync for the match report.
        connection.execute(
            """
            UPDATE library_matches
            SET memorize_status = ?, catalog_title = COALESCE(?, catalog_title),
                memorize_checked_at = ?
            WHERE reado_isbn = ? AND matched_isbn = ?
            """,
            (status, catalog_title, checked_at, reado_isbn, isbn),
        )