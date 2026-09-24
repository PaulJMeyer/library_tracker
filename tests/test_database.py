import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from library_tracker.database import get_connection, initialize_database


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
