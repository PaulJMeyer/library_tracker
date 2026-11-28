from __future__ import annotations

import datetime
from pathlib import Path
import sqlite3
from unittest.mock import Mock, patch

from library_tracker.clients.telegram import TelegramClient
from library_tracker.cli import main
from library_tracker.database import get_connection
from library_tracker.output import format_telegram_message
from library_tracker.repositories.telegram_overviews import (
    get_last_fingerprint,
    overview_fingerprint,
    save_fingerprint,
)
from library_tracker.services.sync import SyncReport


def test_fingerprint_ignores_the_date_line() -> None:
    first = format_telegram_message([], datetime.date(2026, 1, 1))
    second = format_telegram_message([], datetime.date(2026, 1, 2))
    changed = format_telegram_message([], datetime.date(2026, 1, 2), added_titles=["Neu"])

    assert overview_fingerprint(first) == overview_fingerprint(second)
    assert overview_fingerprint(first) != overview_fingerprint(changed)


def test_fingerprint_is_stored_per_chat(connection: sqlite3.Connection) -> None:
    assert get_last_fingerprint(connection, "42") is None
    save_fingerprint(connection, "42", "a")
    save_fingerprint(connection, "42", "b")
    save_fingerprint(connection, "7", "c")

    assert get_last_fingerprint(connection, "42") == "b"
    assert get_last_fingerprint(connection, "7") == "c"


def _report(*, added: list[str] | None = None, warnings: list[str] | None = None) -> SyncReport:
    report = SyncReport()
    report.scrape = {"total_entries": 0, "all_titles": [], "entries": [], "items": [], "loans": []}
    report.added_titles = added or []
    report.warnings = warnings or []
    return report


def _run(tmp_path: Path, report: SyncReport, *args: str) -> Mock:
    client = Mock(spec=TelegramClient)
    client.chat_id = "42"
    db_path = tmp_path / "library_tracker.db"
    with (
        patch("library_tracker.cli._telegram_client", return_value=client),
        patch("library_tracker.cli.run_sync", return_value=report),
        patch("library_tracker.cli.print_scrape_result"),
        patch("library_tracker.database.get_connection", side_effect=lambda: get_connection(db_path)),
    ):
        main(["sync", "--telegram", *args])
    return client


def test_sync_sends_overview_only_when_it_changed(tmp_path: Path) -> None:
    assert _run(tmp_path, _report()).send_message.call_count == 1
    assert _run(tmp_path, _report()).send_message.call_count == 0
    assert _run(tmp_path, _report(added=["Neu"])).send_message.call_count == 1
    assert _run(tmp_path, _report(added=["Neu"])).send_message.call_count == 0
    assert _run(tmp_path, _report()).send_message.call_count == 1


def test_sync_always_sends_with_flag_or_warnings(tmp_path: Path) -> None:
    _run(tmp_path, _report())
    assert _run(tmp_path, _report(), "--always").send_message.call_count == 1
    assert _run(tmp_path, _report(warnings=["DNB fehlgeschlagen"])).send_message.call_count == 1
    assert _run(tmp_path, _report(warnings=["DNB fehlgeschlagen"])).send_message.call_count == 1


def test_failed_send_is_retried_next_run(tmp_path: Path) -> None:
    client = Mock(spec=TelegramClient)
    client.chat_id = "42"
    client.send_message.side_effect = RuntimeError("network")
    db_path = tmp_path / "library_tracker.db"
    with (
        patch("library_tracker.cli._telegram_client", return_value=client),
        patch("library_tracker.cli.run_sync", return_value=_report()),
        patch("library_tracker.cli.print_scrape_result"),
        patch("library_tracker.database.get_connection", side_effect=lambda: get_connection(db_path)),
    ):
        try:
            main(["sync", "--telegram"])
        except RuntimeError:
            pass

    assert _run(tmp_path, _report()).send_message.call_count == 1
