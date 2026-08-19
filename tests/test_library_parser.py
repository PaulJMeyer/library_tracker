import pytest
from bs4 import BeautifulSoup

from library_tracker.library_parser import (
    clean_text,
    extract_due_date,
    normalize_copy_status,
    classify_item,
    parse_title,
)
from library_tracker.models import Copy


# --- clean_text: einfachster Fall, ein assert pro Test -------------------

def test_clean_text_collapses_whitespace():
    assert clean_text("  hallo    welt  ") == "hallo welt"


def test_clean_text_handles_newlines_and_tabs():
    assert clean_text("hallo\n\twelt") == "hallo welt"


# --- extract_due_date: mehrere Fälle -> parametrize statt Copy-Paste -----

@pytest.mark.parametrize(
    "status_text, expected",
    [
        ("entliehen bis 15.08.2026", "15.08.2026"),
        ("verfügbar ab 01.01.2027, Rückgabe", "01.01.2027"),
        ("kein Datum enthalten", None),   # Edge Case: kein Match -> None
        ("", None),                        # Edge Case: leerer String
    ],
)
def test_extract_due_date(status_text, expected):
    assert extract_due_date(status_text) == expected


# --- normalize_copy_status: Groß-/Kleinschreibung + Reihenfolge der ifs --

@pytest.mark.parametrize(
    "status_text, expected",
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
def test_normalize_copy_status(status_text, expected):
    assert normalize_copy_status(status_text) == expected


# --- classify_item: Testdaten sind hier "echte" Copy-TypedDicts ----------
# Praktischer Nebeneffekt: mypy prüft auch die Testdaten selbst mit,
# falls du mypy später auch über tests/ laufen lässt.

def make_copy(status: str, is_central: bool) -> Copy:
    return {
        "media_number": "123",
        "signature": "sig",
        "branch": "irrelevant",
        "status_text": status,
        "status": status,
        "due_date": None,
        "is_central": is_central,
    }


def test_classify_item_empty_list_is_unknown():
    assert classify_item([]) == "unbekannt"


def test_classify_item_ordered_is_bestellt():
    # "bestellt" muss Vorrang vor allem anderen haben
    copies = [make_copy("ausleihbar", is_central=True), make_copy("bestellt", is_central=False)]
    assert classify_item(copies) == "bestellt"


def test_classify_item_central_available_is_ausleihbar():
    copies = [make_copy("ausleihbar", is_central=True)]
    assert classify_item(copies) == "ausleihbar"


def test_classify_item_branch_only_is_bestellbar():
    copies = [make_copy("bestellbar", is_central=False)]
    assert classify_item(copies) == "bestellbar"


def test_classify_item_all_loaned_is_entliehen():
    copies = [make_copy("entliehen", is_central=True)]
    assert classify_item(copies) == "entliehen"


# --- parse_title: braucht ein BeautifulSoup-Objekt -> Fixture ------------

@pytest.fixture
def soup_with_title() -> BeautifulSoup:
    html = "<html><body><h1>Menu Closed Menu Open Exemplare</h1><h2>Der Herr der Ringe</h2></body></html>"
    return BeautifulSoup(html, "html.parser")


def test_parse_title_skips_ignored_headings(soup_with_title):
    assert parse_title(soup_with_title) == "Der Herr der Ringe"


def test_parse_title_fallback_when_nothing_found():
    soup = BeautifulSoup("<html><body><p>kein heading</p></body></html>", "html.parser")
    assert parse_title(soup) == "(Titel unbekannt)"
