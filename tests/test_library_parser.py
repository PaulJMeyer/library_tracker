import pytest
from bs4 import BeautifulSoup

from library_tracker.library_parser import (
    classify_item,
    clean_text,
    extract_due_date,
    normalize_copy_status,
    parse_availability_page,
    parse_copies,
    parse_title,
)
from library_tracker.models import Copy


def make_copy(status: str, is_central: bool) -> Copy:
    return {
        "media_number": "123",
        "signature": "sig",
        "branch": "10-Zentralbibliothek" if is_central else "Vegesack",
        "status_text": status,
        "status": status,
        "due_date": None,
        "is_central": is_central,
    }


def test_clean_text_collapses_whitespace() -> None:
    assert clean_text("  hallo    welt  ") == "hallo welt"


def test_clean_text_handles_newlines_and_tabs() -> None:
    assert clean_text("hallo\n\twelt") == "hallo welt"


@pytest.mark.parametrize(
    ("status_text", "expected"),
    [
        ("entliehen bis 15.08.2026", "15.08.2026"),
        ("verfügbar ab 01.01.2027, Rückgabe", "01.01.2027"),
        ("kein Datum enthalten", None),
        ("", None),
    ],
)
def test_extract_due_date(
    status_text: str,
    expected: str | None,
) -> None:
    assert extract_due_date(status_text) == expected


@pytest.mark.parametrize(
    ("status_text", "expected"),
    [
        ("Ausleihbar", "ausleihbar"),
        ("Bestellbar", "bestellbar"),
        ("bereits bestellt", "bestellt"),
        ("Sie haben dieses Medium bereits ausgeliehen.", "entliehen"),
        ("Verfügbar in Zweigstelle", "ausleihbar"),
        ("entliehen bis 01.01.2027", "entliehen"),
        ("irgendein anderer Text", "unbekannt"),
    ],
)
def test_normalize_copy_status(
    status_text: str,
    expected: str,
) -> None:
    assert normalize_copy_status(status_text) == expected


def test_parse_copies_extracts_complete_copy() -> None:
    html = """
    <div class="row py-1">
        <div class="col-12">123456789</div>
        <div class="col-12">S Test 123</div>
        <div class="col-12">10-Zentralbibliothek / Zentralbibliothek</div>
        <div class="col-12">Ausleihbar</div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")

    assert parse_copies(soup) == [
        {
            "media_number": "123456789",
            "signature": "S Test 123",
            "branch": "10-Zentralbibliothek / Zentralbibliothek",
            "status_text": "Ausleihbar",
            "status": "ausleihbar",
            "due_date": None,
            "is_central": True,
        }
    ]


def test_parse_copies_recovers_due_date_when_link_is_removed() -> None:
    html = """
    <div class="row py-1">
        <div class="col-12">123</div>
        <div class="col-12">ABC</div>
        <div class="col-12">10-Zentralbibliothek</div>
        <div class="col-12">
            <a href="#">entliehen bis 20.08.2026</a>
        </div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")

    copy = parse_copies(soup)[0]

    assert copy["status_text"] == "entliehen bis 20.08.2026"
    assert copy["status"] == "entliehen"
    assert copy["due_date"] == "20.08.2026"


def test_parse_copies_removes_reservation_information() -> None:
    html = """
    <div class="row py-1">
        <div class="col-12">123</div>
        <div class="col-12">ABC</div>
        <div class="col-12">Vegesack</div>
        <div class="col-12">
            entliehen bis 20.08.2026 (gesamte Vormerkungen: 3)
        </div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")

    copy = parse_copies(soup)[0]

    assert copy["status_text"] == "entliehen bis 20.08.2026"
    assert copy["due_date"] == "20.08.2026"
    assert copy["is_central"] is False


def test_parse_copies_ignores_incomplete_row() -> None:
    html = """
    <div class="row py-1">
        <div class="col-12">123</div>
        <div class="col-12">ABC</div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")

    assert parse_copies(soup) == []


def test_parse_copies_ignores_empty_media_number() -> None:
    html = """
    <div class="row py-1">
        <div class="col-12"></div>
        <div class="col-12">ABC</div>
        <div class="col-12">10-Zentralbibliothek</div>
        <div class="col-12">Ausleihbar</div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")

    assert parse_copies(soup) == []


def test_classify_item_empty_list_is_unknown() -> None:
    assert classify_item([]) == "unbekannt"


def test_classify_item_ordered_is_bestellt() -> None:
    copies = [
        make_copy("ausleihbar", is_central=True),
        make_copy("bestellt", is_central=False),
    ]
    assert classify_item(copies) == "bestellt"


def test_classify_item_central_available_is_ausleihbar() -> None:
    copies = [make_copy("ausleihbar", is_central=True)]
    assert classify_item(copies) == "ausleihbar"


def test_classify_item_branch_available_is_bestellbar() -> None:
    copies = [make_copy("ausleihbar", is_central=False)]
    assert classify_item(copies) == "bestellbar"


def test_classify_item_branch_orderable_is_bestellbar() -> None:
    copies = [make_copy("bestellbar", is_central=False)]
    assert classify_item(copies) == "bestellbar"


def test_classify_item_all_loaned_is_entliehen() -> None:
    copies = [make_copy("entliehen", is_central=True)]
    assert classify_item(copies) == "entliehen"


@pytest.fixture
def soup_with_title() -> BeautifulSoup:
    return BeautifulSoup(
        "<html><body>"
        "<h1>Menu Closed Menu Open Exemplare</h1>"
        "<h2>Der Herr der Ringe</h2>"
        "</body></html>",
        "html.parser",
    )


def test_parse_title_skips_ignored_headings(
    soup_with_title: BeautifulSoup,
) -> None:
    assert parse_title(soup_with_title) == "Der Herr der Ringe"


def test_parse_title_fallback_when_nothing_found() -> None:
    soup = BeautifulSoup(
        "<html><body><p>kein heading</p></body></html>",
        "html.parser",
    )

    assert parse_title(soup) == "(Titel unbekannt)"


def test_parse_availability_page_combines_parser_results() -> None:
    html = """
    <html>
        <body>
            <h2>Mein Testbuch</h2>
            <div class="row py-1">
                <div class="col-12">123</div>
                <div class="col-12">ABC</div>
                <div class="col-12">10-Zentralbibliothek</div>
                <div class="col-12">Ausleihbar</div>
            </div>
        </body>
    </html>
    """

    item = parse_availability_page(html)

    assert item["title"] == "Mein Testbuch"
    assert item["overall_status"] == "ausleihbar"
    assert len(item["copies"]) == 1
