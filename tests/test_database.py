from pathlib import Path

from library_tracker.database import get_connection, initialize_database


def test_connection_and_schema(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "tracker.db"
    connection = get_connection(path)
    try:
        initialize_database(connection)
        assert path.exists()
        assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"copies", "reado_books", "openlibrary_editions"} <= tables
        initialize_database(connection)
    finally:
        connection.close()


def test_migrates_old_reado_wishlist_schema(tmp_path: Path) -> None:
    connection = get_connection(tmp_path / "old.db")
    connection.execute(
        """
        CREATE TABLE reado_books (
            isbn13 TEXT PRIMARY KEY,
            reado_url TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            on_wishlist INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT INTO reado_books VALUES (?, ?, ?, ?, ?)",
        ("9783423449229", "url", "first", "last", 1),
    )
    connection.commit()

    initialize_database(connection)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(reado_books)")}
    membership = connection.execute(
        "SELECT isbn13, list_type, is_active FROM reado_list_memberships"
    ).fetchone()
    connection.close()

    assert "on_wishlist" not in columns
    assert membership == ("9783423449229", "wishlist", 1)
