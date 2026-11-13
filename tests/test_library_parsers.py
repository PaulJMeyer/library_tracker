import pytest
from bs4 import BeautifulSoup

from library_tracker.parsers.library import (
    classify_item,
    clean_text,
    extract_csid,
    extract_due_date,
    normalize_copy_status,
    parse_availability_page,
    parse_catalog_hit_urls,
    parse_loan_dates,
    parse_loans,
    parse_memorize_page,
)


def test_text_and_status_helpers() -> None:
    assert clean_text("  hallo\n welt ") == "hallo welt"
    assert extract_due_date("entliehen bis 15.08.2026") == "15.08.2026"
    assert extract_due_date("kein Datum") is None
    assert normalize_copy_status("bereits bestellt") == "bestellt"
    assert normalize_copy_status("Verfügbar") == "ausleihbar"
    assert normalize_copy_status("unbekannter Text") == "unbekannt"


def test_parse_availability_page_and_classification() -> None:
    html = """
    <h2>Mein Testbuch</h2>
    <div class="row py-1">
      <div class="col-12">123</div><div class="col-12">ABC</div>
      <div class="col-12">10-Zentralbibliothek</div>
      <div class="col-12">Ausleihbar</div>
    </div>
    """
    item = parse_availability_page(html)
    assert item["title"] == "Mein Testbuch"
    assert item["overall_status"] == "ausleihbar"
    assert item["copies"][0]["media_number"] == "123"
    assert classify_item([]) == "unbekannt"


def test_parse_availability_page_recovers_due_date_from_link() -> None:
    html = """
    <h2>Test</h2>
    <div class="row py-1">
      <div class="col-12">123</div><div class="col-12">ABC</div>
      <div class="col-12">Vegesack</div>
      <div class="col-12"><a href="#">entliehen bis 20.08.2026</a></div>
    </div>
    """
    copy = parse_availability_page(html)["copies"][0]
    assert copy["status"] == "entliehen"
    assert copy["due_date"] == "20.08.2026"


def test_parse_loans_and_dates() -> None:
    html = """
    <div class="row border-bottom">
      <span class="d-block"><strong>Medea</strong></span>
      <span class="d-block">Rosie Hewlett</span>
      <span class="d-block">2090411478</span>
      <span class="d-block"> / S Hewl Fantasy</span>
      <span class="d-block">Verlängerung noch nicht möglich.</span>
      <div class="d-none d-md-block col-md-3">11.08.2026 - 01.09.2026<br>10-Zentralbibliothek</div>
    </div>
    """
    loan = parse_loans(html)[0]
    assert loan["title"] == "Medea"
    assert loan["signature"] == "S Hewl Fantasy"
    assert loan["due_date"] == "01.09.2026"
    assert parse_loan_dates("keine Daten") == (None, None, "keine Daten")


def test_parse_memorize_page() -> None:
    html = """
    <form id="MemorizeBean">
      <input name="selectedMemorizeList" value=""><input name="displayType" value="short">
      <input name="CSId" value="test-csid">
      <div class="row border-bottom">
        <input type="checkbox" value="uuid-1">
        <a href="/webOPACClient/availability.do?methodToCall=runMemorizeAvailability">Titel</a>
      </div>
    </form>
    """
    page = parse_memorize_page(html, 1)
    assert page["cs_id"] == "test-csid"
    assert page["entries"][0]["uuid"] == "uuid-1"
    assert page["entries"][0]["availability_link"].startswith("https://opac.stabi-hb.de/")


def test_extract_csid() -> None:
    assert extract_csid('<input name="CSId" value="abc">') == "abc"
    with pytest.raises(ValueError, match="CSId"):
        extract_csid("<html></html>")


def test_parse_catalog_hits() -> None:
    direct = "https://opac.stabi-hb.de/webOPACClient/singleHit.do?identifier=123"
    assert parse_catalog_hit_urls("", direct) == [direct]

    html = """
    <a href="singleHit.do?methodToCall=showHit&identifier=one">A</a>
    <a href="singleHit.do?methodToCall=showHit&identifier=two">B</a>
    """
    assert len(parse_catalog_hit_urls(html, "https://opac.stabi-hb.de/webOPACClient/search.do")) == 2

    single_html = """
    <a href="/webOPACClient/singleHit.do?methodToCall=activateTab&tab=showTitleActive">Titel</a>
    """
    assert parse_catalog_hit_urls(
        single_html,
        "https://opac.stabi-hb.de/webOPACClient/search.do",
    ) == [
        "https://opac.stabi-hb.de/webOPACClient/singleHit.do?methodToCall=activateTab&tab=showTitleActive"
    ]
