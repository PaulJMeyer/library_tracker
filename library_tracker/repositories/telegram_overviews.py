from __future__ import annotations

import datetime
import hashlib
import sqlite3


def overview_fingerprint(message: str) -> str:
    """Hash of the overview without its first line, which only holds the date."""
    body = message.split("\n", 1)[1] if "\n" in message else ""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def get_last_fingerprint(connection: sqlite3.Connection, chat_id: str) -> str | None:
    row = connection.execute(
        "SELECT fingerprint FROM telegram_overviews WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return str(row[0]) if row else None


def save_fingerprint(connection: sqlite3.Connection, chat_id: str, fingerprint: str) -> None:
    sent_at = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    with connection:
        connection.execute(
            """
            INSERT INTO telegram_overviews (chat_id, fingerprint, sent_at)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                fingerprint = excluded.fingerprint,
                sent_at = excluded.sent_at
            """,
            (chat_id, fingerprint, sent_at),
        )
