from __future__ import annotations

import sqlite3

from library_tracker.config import FINISHED_LIST_TYPES, WISHLIST_TYPES_SQL


def forget_removals_of_wishlist_books(connection: sqlite3.Connection) -> None:
    """A book that is back on the wishlist may be removed again once it is finished."""
    with connection:
        connection.execute(
            f"""
            DELETE FROM merkliste_removals
            WHERE isbn13 IN (
                SELECT isbn13 FROM reado_list_memberships
                WHERE list_type IN {WISHLIST_TYPES_SQL} AND is_active = 1
            )
            """
        )


def get_finished_books_to_check(connection: sqlite3.Connection) -> list[tuple[str, str | None]]:
    """(isbn13, stored catalog title or None) of books on a finished READO list or
    no longer on the second wishlist (and not on any wishlist) that were not
    checked against the Merkliste yet."""
    placeholders = ", ".join("?" for _ in FINISHED_LIST_TYPES)
    return [
        (str(isbn13), str(title) if title is not None else None)
        for isbn13, title in connection.execute(
            f"""
            SELECT DISTINCT rlm.isbn13, lm.catalog_title
            FROM reado_list_memberships AS rlm
            LEFT JOIN library_matches AS lm ON lm.reado_isbn = rlm.isbn13
            LEFT JOIN merkliste_removals AS mr ON mr.isbn13 = rlm.isbn13
            WHERE (
                (rlm.list_type IN ({placeholders}) AND rlm.is_active = 1)
                -- The second wishlist has no finished lists here: a book that left it
                -- is done with for its owner.
                OR (rlm.list_type = 'second_wishlist' AND rlm.is_active = 0)
              )
              AND (mr.isbn13 IS NULL OR mr.status = 'failed')
              AND rlm.isbn13 NOT IN (
                  SELECT isbn13 FROM reado_list_memberships
                  WHERE list_type IN {WISHLIST_TYPES_SQL} AND is_active = 1
              )
            ORDER BY rlm.isbn13
            """,
            FINISHED_LIST_TYPES,
        )
    ]


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
