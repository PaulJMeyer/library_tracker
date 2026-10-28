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
                last_seen_at TEXT NOT NULL,
                on_wishlist INTEGER NOT NULL
                    CHECK (on_wishlist IN (0, 1))
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_reado_books_on_wishlist
            ON reado_books(on_wishlist)
            """
        )
