import sqlite3
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from library_tracker.cli import (
    format_history_line,
    main,
    print_copy_history,
    run_history_command,
)
from library_tracker.models import AvailabilitySnapshot


def make_connection_mock() -> tuple[sqlite3.Connection, MagicMock]:
    connection_mock = MagicMock(spec=sqlite3.Connection)
    return cast(sqlite3.Connection, connection_mock), connection_mock


def make_snapshot(
    *,
    checked_at: str = "2026-09-24T06:00:00+00:00",
    status: str = "ausleihbar",
    status_text: str = "Ausleihbar",
    due_date: str | None = None,
) -> AvailabilitySnapshot:
    return {
        "media_number": "123456789",
        "checked_at": checked_at,
        "status": status,
        "status_text": status_text,
        "due_date": due_date,
    }


def test_format_history_line_without_due_date() -> None:
    snapshot = make_snapshot()

    assert format_history_line(snapshot) == (
        "2026-09-24T06:00:00+00:00 | "
        "ausleihbar | Ausleihbar"
    )


def test_format_history_line_with_due_date() -> None:
    snapshot = make_snapshot(
        status="entliehen",
        status_text="entliehen bis 30.09.2026",
        due_date="30.09.2026",
    )

    assert format_history_line(snapshot) == (
        "2026-09-24T06:00:00+00:00 | "
        "entliehen | entliehen bis 30.09.2026 "
        "| due: 30.09.2026"
    )


def test_print_copy_history_outputs_snapshots(
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection, _ = make_connection_mock()
    history = [
        make_snapshot(
            checked_at="2026-09-23T06:00:00+00:00",
            status="entliehen",
            status_text="entliehen bis 24.09.2026",
            due_date="24.09.2026",
        ),
        make_snapshot(),
    ]

    with patch(
        "library_tracker.cli.get_copy_history",
        return_value=history,
    ):
        found = print_copy_history(
            connection,
            "123456789",
        )

    output = capsys.readouterr().out

    assert found is True
    assert "Availability history for copy 123456789:" in output
    assert "2026-09-23T06:00:00+00:00" in output
    assert "entliehen" in output
    assert "2026-09-24T06:00:00+00:00" in output
    assert "ausleihbar" in output


def test_print_copy_history_unknown_copy(
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection, _ = make_connection_mock()

    with patch(
        "library_tracker.cli.get_copy_history",
        return_value=[],
    ):
        found = print_copy_history(
            connection,
            "999999999",
        )

    output = capsys.readouterr().out

    assert found is False
    assert "No history found for copy 999999999." in output


def test_run_history_command_closes_connection() -> None:
    connection, connection_mock = make_connection_mock()

    with (
        patch(
            "library_tracker.cli.get_connection",
            return_value=connection,
        ),
        patch(
            "library_tracker.cli.initialize_database"
        ) as mock_initialize_database,
        patch(
            "library_tracker.cli.print_copy_history",
            return_value=True,
        ) as mock_print_copy_history,
    ):
        exit_code = run_history_command("123456789")

    assert exit_code == 0
    mock_initialize_database.assert_called_once_with(connection)
    mock_print_copy_history.assert_called_once_with(
        connection,
        "123456789",
    )
    connection_mock.close.assert_called_once_with()


def test_main_without_command_runs_scrape() -> None:
    with patch("library_tracker.cli.run_scrape") as mock_run_scrape:
        exit_code = main([])

    assert exit_code == 0
    mock_run_scrape.assert_called_once_with()


def test_main_scrape_command_runs_scrape() -> None:
    with patch("library_tracker.cli.run_scrape") as mock_run_scrape:
        exit_code = main(["scrape"])

    assert exit_code == 0
    mock_run_scrape.assert_called_once_with()


def test_main_history_command() -> None:
    with patch(
        "library_tracker.cli.run_history_command",
        return_value=0,
    ) as mock_run_history_command:
        exit_code = main(
            ["history", "123456789"]
        )

    assert exit_code == 0
    mock_run_history_command.assert_called_once_with(
        "123456789"
    )
