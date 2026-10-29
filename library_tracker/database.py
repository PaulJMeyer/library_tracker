import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path("data/library_tracker.db")


def get_connection(path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Create a SQLite connection and enable foreign-key enforcement."""
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    """Create the database schema if it does not exist yet."""
    with connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS copies (
                media_number TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                signature TEXT NOT NULL,
                branch TEXT NOT NULL,
                is_central INTEGER NOT NULL CHECK (is_central IN (0, 1)),
                last_seen_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS availability_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_number TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                status TEXT NOT NULL,
                status_text TEXT NOT NULL,
                due_date TEXT,
                FOREIGN KEY (media_number)
                    REFERENCES copies(media_number)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_snapshots_media_number_checked_at
            ON availability_snapshots (media_number, checked_at)
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reado_books (
                isbn13 TEXT PRIMARY KEY,
                reado_url TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reado_list_memberships (
                isbn13 TEXT NOT NULL,
                list_type TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                is_active INTEGER NOT NULL
                    CHECK (is_active IN (0, 1)),
                PRIMARY KEY (isbn13, list_type),
                FOREIGN KEY (isbn13)
                    REFERENCES reado_books(isbn13)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_reado_list_memberships_active
            ON reado_list_memberships(list_type, is_active)
            """
        )

        _migrate_reado_list_memberships(connection)

        connection.commit()


def _get_table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(
            f"PRAGMA table_info({table_name})"
        )
    }

def _migrate_reado_list_memberships(
    connection: sqlite3.Connection,
) -> None:
    columns = _get_table_columns(
        connection,
        "reado_books",
    )

    if "on_wishlist" not in columns:
        return

    connection.execute(
        """
        INSERT OR REPLACE INTO reado_list_memberships (
            isbn13,
            list_type,
            first_seen_at,
            last_seen_at,
            is_active
        )
        SELECT
            isbn13,
            'wishlist',
            first_seen_at,
            last_seen_at,
            on_wishlist
        FROM reado_books
        """
    )

    connection.execute(
        """
        DROP INDEX IF EXISTS idx_reado_books_on_wishlist
        """
    )

    connection.execute(
        """
        ALTER TABLE reado_books
        DROP COLUMN on_wishlist
        """
    )