import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from library_tracker.database import (get_connection,
                                      initialize_database)


@pytest.fixture
def connection(
    tmp_path: Path,
) -> Iterator[sqlite3.Connection]:
    db_path = tmp_path / "nested" / "library_tracker.db"
    db_connection = get_connection(db_path)
    initialize_database(db_connection)

    try:
        yield db_connection
    finally:
        db_connection.close()


def test_get_connection_creates_parent_directory_and_database(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "data" / "library_tracker.db"

    connection = get_connection(db_path)
    try:
        assert db_path.exists()

        foreign_keys = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()
        assert foreign_keys == (1,)
    finally:
        connection.close()


def test_initialize_database_creates_expected_tables(
    connection: sqlite3.Connection,
) -> None:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        """
    ).fetchall()
    table_names = {str(row[0]) for row in rows}

    assert "copies" in table_names
    assert "availability_snapshots" in table_names


def test_initialize_database_is_idempotent(
    connection: sqlite3.Connection,
) -> None:
    initialize_database(connection)
    initialize_database(connection)

    row = connection.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'copies'
        """
    ).fetchone()

    assert row == (1,)


def test_initialize_database_migrates_reado_wishlist_memberships(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "old_database.db"
    connection = get_connection(database_path)

    connection.execute(
        """
        CREATE TABLE reado_books (
            isbn13 TEXT PRIMARY KEY,
            reado_url TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            on_wishlist INTEGER NOT NULL
                CHECK (on_wishlist IN (0, 1))
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX idx_reado_books_on_wishlist
        ON reado_books(on_wishlist)
        """
    )

    connection.executemany(
        """
        INSERT INTO reado_books (
            isbn13,
            reado_url,
            first_seen_at,
            last_seen_at,
            on_wishlist
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                "9783423449229",
                "https://reado.app/de/book/a/9783423449229",
                "2026-10-28T10:00:00+00:00",
                "2026-10-29T10:00:00+00:00",
                1,
            ),
            (
                "9798987380420",
                "https://reado.app/de/book/b/9798987380420",
                "2026-10-28T10:00:00+00:00",
                "2026-10-29T10:00:00+00:00",
                0,
            ),
        ],
    )
    connection.commit()

    initialize_database(connection)

    columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(reado_books)"
        )
    }

    assert "on_wishlist" not in columns

    memberships = connection.execute(
        """
        SELECT isbn13, list_type, is_active
        FROM reado_list_memberships
        ORDER BY isbn13
        """
    ).fetchall()

    assert memberships == [
        ("9783423449229", "wishlist", 1),
        ("9798987380420", "wishlist", 0),
    ]

    old_index = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'index'
          AND name = 'idx_reado_books_on_wishlist'
        """
    ).fetchone()

    assert old_index is None

    connection.close()