from __future__ import annotations

import sqlite3

from library_tracker.config import WISHLIST_TYPES_SQL
from library_tracker.models import LibraryIsbnCandidateSource


def get_unmatched_wishlist_isbns(connection: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            f"""
            SELECT DISTINCT rlm.isbn13
            FROM reado_list_memberships AS rlm
            LEFT JOIN library_matches AS lm ON lm.reado_isbn = rlm.isbn13
            WHERE rlm.list_type IN {WISHLIST_TYPES_SQL} AND rlm.is_active = 1 AND lm.reado_isbn IS NULL
            ORDER BY rlm.isbn13
            """
        )
    ]


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


def get_matches_to_memorize(connection: sqlite3.Connection) -> list[tuple[str, str]]:
    """(reado_isbn, matched_isbn) of active wishlist matches not yet on the Merkliste."""
    return [
        (str(reado_isbn), str(matched_isbn))
        for reado_isbn, matched_isbn in connection.execute(
            f"""
            SELECT DISTINCT lm.reado_isbn, lm.matched_isbn
            FROM library_matches AS lm
            JOIN reado_list_memberships AS rlm
              ON rlm.isbn13 = lm.reado_isbn AND rlm.list_type IN {WISHLIST_TYPES_SQL} AND rlm.is_active = 1
            WHERE lm.memorize_status IS NULL OR lm.memorize_status = 'failed'
            ORDER BY lm.reado_isbn
            """
        )
    ]


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
    """Catalog titles of the matched books that are active on the given wishlist."""
    return [
        str(row[0])
        for row in connection.execute(
            """
            SELECT DISTINCT lm.catalog_title
            FROM library_matches AS lm
            JOIN reado_list_memberships AS rlm
              ON rlm.isbn13 = lm.reado_isbn AND rlm.list_type = ? AND rlm.is_active = 1
            WHERE lm.catalog_title IS NOT NULL
            ORDER BY lm.catalog_title
            """,
            (list_type,),
        )
    ]
