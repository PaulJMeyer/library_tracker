from __future__ import annotations

import sqlite3

from library_tracker.config import FINISHED_LIST_TYPES


def forget_removals_of_wishlist_books(connection: sqlite3.Connection) -> None:
    """A book that is back on the wishlist may be removed again once it is finished."""
    with connection:
        connection.execute(
            """
            DELETE FROM merkliste_removals
            WHERE isbn13 IN (
                SELECT isbn13 FROM reado_list_memberships
                WHERE list_type = 'wishlist' AND is_active = 1
            )
            """
        )


def get_finished_books_to_check(
    connection: sqlite3.Connection,
) -> list[tuple[str, list[str], set[str]]]:
    """(isbn13, stored catalog titles, stored copy numbers) of books on a finished READO
    list (and not on the wishlist) that were not checked against the Merkliste yet.
    Titles and copy numbers cover every edition that was found in the catalog."""
    placeholders = ", ".join("?" for _ in FINISHED_LIST_TYPES)
    isbns = [
        str(row[0])
        for row in connection.execute(
            f"""
            SELECT DISTINCT rlm.isbn13
            FROM reado_list_memberships AS rlm
            LEFT JOIN merkliste_removals AS mr ON mr.isbn13 = rlm.isbn13
            WHERE rlm.list_type IN ({placeholders}) AND rlm.is_active = 1
              AND (mr.isbn13 IS NULL OR mr.status = 'failed')
              AND rlm.isbn13 NOT IN (
                  SELECT isbn13 FROM reado_list_memberships
                  WHERE list_type = 'wishlist' AND is_active = 1
              )
            ORDER BY rlm.isbn13
            """,
            FINISHED_LIST_TYPES,
        )
    ]
    books: list[tuple[str, list[str], set[str]]] = []
    for isbn13 in isbns:
        titles: list[str] = []
        media_numbers: set[str] = set()
        for title, numbers in connection.execute(
            """
            SELECT catalog_title, media_numbers FROM catalog_editions WHERE reado_isbn = ?
            UNION ALL
            SELECT catalog_title, NULL FROM library_matches WHERE reado_isbn = ?
            """,
            (isbn13, isbn13),
        ):
            if title is not None and str(title) not in titles:
                titles.append(str(title))
            media_numbers.update(str(numbers or "").split())
        books.append((isbn13, titles, media_numbers))
    return books


def save_removal_result(
    connection: sqlite3.Connection,
    isbn13: str,
    status: str,
    catalog_title: str | None,
    checked_at: str,
) -> None:
    with connection:
        connection.execute(
            """
            INSERT INTO merkliste_removals (isbn13, catalog_title, status, checked_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(isbn13) DO UPDATE SET
                catalog_title = excluded.catalog_title,
                status = excluded.status,
                checked_at = excluded.checked_at
            """,
            (isbn13, catalog_title, status, checked_at),
        )
