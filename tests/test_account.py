from typing import cast
from unittest.mock import MagicMock, patch

from requests import Response, Session

from library_tracker.account import (
    ACCOUNT_URL,
    get_account_page,
    parse_loan_dates,
    parse_loans,
)


SAMPLE_ROW_HTML = """
<div class="row border-bottom">
    <div class="d-none d-xl-inline-block col-xl-auto my-2"></div>
    <div class="col-2 col-xl-1 my-2"></div>
    <div class="col-8 col-md-7 my-2">
        <span class="d-block"><strong>Medea</strong></span>
        <span class="d-block">Hewlett, Rosie [VerfasserIn]</span>
        <span class="d-block">2090411478</span>
        <span class="d-block">&nbsp;/&nbsp;S Hewl Fantasy</span>
        <span class="d-block">
            <span class="textgruen">Eine Verlängerung ist noch nicht möglich.</span>
        </span>
        <div class="d-block d-md-none">
            11.08.2026 - 01.09.2026
            <br>
            10-Zentralbibliothek&nbsp;/&nbsp;Zentralbibliothek
        </div>
    </div>
    <div class="d-none d-md-block col-md-3 my-2">
        11.08.2026 - 01.09.2026
        <br>
        10-Zentralbibliothek&nbsp;/&nbsp;Zentralbibliothek
    </div>
</div>
"""


def make_session_mock() -> tuple[Session, MagicMock]:
    session_mock = MagicMock(spec=Session)
    return cast(Session, session_mock), session_mock


def test_get_account_page() -> None:
    session, _ = make_session_mock()
    response = MagicMock(spec=Response)
    response.text = "<html>account</html>"

    with patch("library_tracker.account.get", return_value=response) as mock_get:
        result = get_account_page(session)

    assert result == "<html>account</html>"
    mock_get.assert_called_once_with(session, ACCOUNT_URL)


def test_parse_loans_extracts_all_fields() -> None:
    loans = parse_loans(SAMPLE_ROW_HTML)

    assert len(loans) == 1
    loan = loans[0]
    assert loan["title"] == "Medea"
    assert loan["author"] == "Hewlett, Rosie [VerfasserIn]"
    assert loan["media_number"] == "2090411478"
    assert loan["signature"] == "S Hewl Fantasy"
    assert loan["branch"] == "10-Zentralbibliothek / Zentralbibliothek"
    assert loan["borrowed_since"] == "11.08.2026"
    assert loan["due_date"] == "01.09.2026"
    assert loan["renewal_note"] == "Eine Verlängerung ist noch nicht möglich."


def test_parse_loans_empty_html_returns_empty_list() -> None:
    assert parse_loans("<html><body></body></html>") == []


def test_parse_loans_skips_row_with_too_few_fields() -> None:
    html = """
    <div class="row border-bottom">
        <span class="d-block">Titel</span>
        <span class="d-block">Autor</span>
    </div>
    """

    assert parse_loans(html) == []


def test_parse_loans_skips_row_without_date_information() -> None:
    html = """
    <div class="row border-bottom">
        <span class="d-block">Titel</span>
        <span class="d-block">Autor</span>
        <span class="d-block">123</span>
        <span class="d-block">ABC</span>
    </div>
    """

    assert parse_loans(html) == []


def test_parse_loans_skips_empty_title() -> None:
    html = """
    <div class="row border-bottom">
        <span class="d-block">   </span>
        <span class="d-block">Autor</span>
        <span class="d-block">123</span>
        <span class="d-block">ABC</span>
        <div class="d-none d-md-block col-md-3">
            11.08.2026 - 01.09.2026
            10-Zentralbibliothek
        </div>
    </div>
    """

    assert parse_loans(html) == []


def test_parse_loan_dates_both_dates_present() -> None:
    text = (
        "11.08.2026 - 01.09.2026\n"
        "10-Zentralbibliothek / Zentralbibliothek"
    )

    borrowed_since, due_date, branch = parse_loan_dates(text)

    assert borrowed_since == "11.08.2026"
    assert due_date == "01.09.2026"
    assert branch == "10-Zentralbibliothek / Zentralbibliothek"


def test_parse_loan_dates_one_date_present() -> None:
    borrowed_since, due_date, branch = parse_loan_dates(
        "11.08.2026\n10-Zentralbibliothek"
    )

    assert borrowed_since == "11.08.2026"
    assert due_date is None
    assert branch == "10-Zentralbibliothek"


def test_parse_loan_dates_no_dates() -> None:
    borrowed_since, due_date, branch = parse_loan_dates("keine Daten hier")

    assert borrowed_since is None
    assert due_date is None
    assert branch == "keine Daten hier"
