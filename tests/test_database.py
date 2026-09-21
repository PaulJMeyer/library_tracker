import datetime
import sqlite3
from pathlib import Path

import pytest

from library_tracker.database import (
    get_connection,
    initialize_database,
    persist_items,
)
from library_tracker.models import Copy, Item


def make_copy(
    *,
    media_number: str = "123456789",
    signature: str = "S Test",
    branch: str = "10-Zentralbibliothek",
    status: str = "ausleihbar",
    status_text: str = "Ausleihbar",
    due_date: str | None = None,
    is_central: bool = True,
) -> Copy:
    return {
        "media_number": media_number,
        "signature": signature,
        "branch": branch,
        "status_text": status_text,
        "status": status,
        "due_date": due_date,
        "is_central": is_central,
    }


def make_item(
    title: str = "Testbuch",
    copies: list[Copy] | None = None,
) -> Item:
    return {
        "title": title,
        "overall_status": "ausleihbar",
        "copies": copies or [make_copy()],
    }


@pytest.fixture
def connection(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "nested" / "library_tracker.db"
    db_connection = get_connection(db_path)
    initialize_database(db_connection)

    yield db_connection

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


def test_persist_items_stores_copy_and_snapshot(
    connection: sqlite3.Connection,
) -> None:
    checked_at = datetime.datetime(
        2026,
        9,
        21,
        18,
        30,
        tzinfo=datetime.timezone.utc,
    )
    item = make_item()

    persist_items(
        connection,
        [item],
        checked_at=checked_at,
    )

    copy_row = connection.execute(
        """
        SELECT
            media_number,
            title,
            signature,
            branch,
            is_central,
            last_seen_at
        FROM copies
        """
    ).fetchone()

    assert copy_row == (
        "123456789",
        "Testbuch",
        "S Test",
        "10-Zentralbibliothek",
        1,
        "2026-09-21T18:30:00+00:00",
    )

    snapshot_row = connection.execute(
        """
        SELECT
            media_number,
            checked_at,
            status,
            status_text,
            due_date
        FROM availability_snapshots
        """
    ).fetchone()

    assert snapshot_row == (
        "123456789",
        "2026-09-21T18:30:00+00:00",
        "ausleihbar",
        "Ausleihbar",
        None,
    )


def test_persist_items_stores_multiple_copies(
    connection: sqlite3.Connection,
) -> None:
    copies = [
        make_copy(media_number="111111111"),
        make_copy(
            media_number="222222222",
            branch="Vegesack",
            status="bestellbar",
            status_text="Bestellbar",
            is_central=False,
        ),
    ]
    item = make_item(copies=copies)

    persist_items(connection, [item])

    copy_count = connection.execute(
        "SELECT COUNT(*) FROM copies"
    ).fetchone()
    snapshot_count = connection.execute(
        "SELECT COUNT(*) FROM availability_snapshots"
    ).fetchone()

    assert copy_count == (2,)
    assert snapshot_count == (2,)


def test_persist_items_updates_copy_and_keeps_history(
    connection: sqlite3.Connection,
) -> None:
    first_check = datetime.datetime(
        2026,
        9,
        21,
        8,
        0,
        tzinfo=datetime.timezone.utc,
    )
    second_check = datetime.datetime(
        2026,
        9,
        22,
        8,
        0,
        tzinfo=datetime.timezone.utc,
    )

    first_item = make_item(
        copies=[
            make_copy(
                status="entliehen",
                status_text="entliehen bis 22.09.2026",
                due_date="22.09.2026",
            )
        ]
    )
    second_item = make_item(
        copies=[
            make_copy(
                signature="S Test Updated",
                status="ausleihbar",
                status_text="Ausleihbar",
                due_date=None,
            )
        ]
    )

    persist_items(
        connection,
        [first_item],
        checked_at=first_check,
    )
    persist_items(
        connection,
        [second_item],
        checked_at=second_check,
    )

    copy_row = connection.execute(
        """
        SELECT signature, last_seen_at
        FROM copies
        WHERE media_number = ?
        """,
        ("123456789",),
    ).fetchone()

    assert copy_row == (
        "S Test Updated",
        "2026-09-22T08:00:00+00:00",
    )

    snapshots = connection.execute(
        """
        SELECT status, due_date
        FROM availability_snapshots
        WHERE media_number = ?
        ORDER BY checked_at
        """,
        ("123456789",),
    ).fetchall()

    assert snapshots == [
        ("entliehen", "22.09.2026"),
        ("ausleihbar", None),
    ]


def test_persist_items_stores_due_date(
    connection: sqlite3.Connection,
) -> None:
    item = make_item(
        copies=[
            make_copy(
                status="entliehen",
                status_text="entliehen bis 30.09.2026",
                due_date="30.09.2026",
            )
        ]
    )

    persist_items(connection, [item])

    row = connection.execute(
        """
        SELECT due_date
        FROM availability_snapshots
        """
    ).fetchone()

    assert row == ("30.09.2026",)


def test_persist_items_rejects_naive_timestamp(
    connection: sqlite3.Connection,
) -> None:
    naive_timestamp = datetime.datetime(2026, 9, 21, 12, 0)

    with pytest.raises(
        ValueError,
        match="checked_at must be timezone-aware",
    ):
        persist_items(
            connection,
            [make_item()],
            checked_at=naive_timestamp,
        )
