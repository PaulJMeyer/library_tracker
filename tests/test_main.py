from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from requests import Response, Session

from library_tracker.main import main
from library_tracker.models import Item, Loan, MemorizePage


def make_session_mock() -> tuple[Session, MagicMock]:
    session_mock = MagicMock(spec=Session)
    return cast(Session, session_mock), session_mock


def make_response_mock(text: str = "") -> MagicMock:
    response = MagicMock(spec=Response)
    response.text = text
    return response


def test_main_runs_complete_workflow(
    capsys: pytest.CaptureFixture[str],
) -> None:
    session, session_mock = make_session_mock()

    page: MemorizePage = {
        "cur_pos": "1",
        "cs_id": "test-csid",
        "display_type": "short",
        "selected_memorize_list": "",
        "entries": [
            {
                "uuid": "loaned-uuid",
                "availability_link": "url-1",
            },
            {
                "uuid": "orderable-uuid",
                "availability_link": "url-2",
            },
            {
                "uuid": "available-uuid",
                "availability_link": "url-3",
            },
        ],
    }

    loaned_item: Item = {
        "title": "Loaned Book",
        "overall_status": "entliehen",
        "copies": [],
    }
    orderable_item: Item = {
        "title": "Orderable Book",
        "overall_status": "bestellbar",
        "copies": [],
    }
    available_item: Item = {
        "title": "Available Book",
        "overall_status": "ausleihbar",
        "copies": [],
    }
    loans: list[Loan] = []

    detail_responses = [
        make_response_mock(),
        make_response_mock("loaned-page"),
        make_response_mock(),
        make_response_mock("orderable-page"),
        make_response_mock(),
        make_response_mock("available-page"),
    ]

    with (
        patch(
            "library_tracker.main.login",
            return_value=session_mock,
        ),
        patch(
            "library_tracker.main.get_all_memorize_pages",
            return_value=[page],
        ),
        patch(
            "library_tracker.main.get",
            side_effect=detail_responses,
        ),
        patch(
            "library_tracker.main.parse_availability_page",
            side_effect=[
                loaned_item,
                orderable_item,
                available_item,
            ],
        ),
        patch(
            "library_tracker.main.remove_entries",
            return_value=True,
        ) as mock_remove_entries,
        patch(
            "library_tracker.main.print_results_console"
        ) as mock_print_results,
        patch(
            "library_tracker.main.write_results_markdown"
        ) as mock_write_results,
        patch(
            "library_tracker.main.get_account_page",
            return_value="<html></html>",
        ),
        patch(
            "library_tracker.main.parse_loans",
            return_value=loans,
        ),
        patch(
            "library_tracker.main.print_loans_console"
        ) as mock_print_loans,
    ):
        main()

    mock_remove_entries.assert_called_once_with(
        session_mock,
        page,
        ["loaned-uuid"],
    )

    result_items = cast(list[Item], mock_print_results.call_args.args[0])
    assert [item["title"] for item in result_items] == [
        "Available Book",
        "Orderable Book",
    ]

    mock_write_results.assert_called_once_with(result_items)
    mock_print_loans.assert_called_once_with(loans)

    output = capsys.readouterr().out
    assert "Gefundene Medien: 3" in output
    assert "Entfernt: 1 Titel (Erfolg: True)" in output
    assert cast(Session, session_mock) is session
