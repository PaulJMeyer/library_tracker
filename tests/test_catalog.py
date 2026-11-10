from unittest.mock import Mock

from library_tracker.catalog import (
    normalize_isbn,
    parse_catalog_hit_urls,
    search_catalog_by_isbn,
)


def test_normalize_isbn() -> None:
    assert normalize_isbn(
        "978-3-423-44922-9"
    ) == "9783423449229"


def test_parse_direct_single_hit() -> None:
    url = (
        "https://opac.stabi-hb.de/"
        "webOPACClient/singleHit.do"
        "?methodToCall=showHit"
        "&curPos=1"
        "&identifier=-1_FT_123456"
    )

    assert parse_catalog_hit_urls(
        "<html></html>",
        url,
    ) == [url]


def test_parse_hit_links() -> None:
    html = """
    <html>
        <body>
            <a href="singleHit.do?methodToCall=showHit&curPos=1&identifier=-1_FT_123">
                Book A
            </a>

            <a href="
                singleHit.do?methodToCall=showHit&curPos=2&identifier=-1_FT_456">
                Book B
            </a>
        </body>
    </html>
    """

    results = parse_catalog_hit_urls(
        html,
        (
            "https://opac.stabi-hb.de/"
            "webOPACClient/start.do"
        ),
    )

    assert len(results) == 2


def test_search_catalog_by_isbn() -> None:
    response = Mock()
    response.url = (
        "https://opac.stabi-hb.de/"
        "webOPACClient/singleHit.do"
        "?methodToCall=showHit"
        "&identifier=-1_FT_123"
    )
    response.text = "<html></html>"
    response.raise_for_status.return_value = None

    session = Mock()
    session.get.return_value = response

    result = search_catalog_by_isbn(
        session,
        "test-csid",
        "978-3-406-72778-8",
    )

    assert result == [response.url]

    _, kwargs = session.get.call_args

    assert kwargs["params"]["CSId"] == "test-csid"
    assert kwargs["params"]["searchCategories[0]"] == "540"
    assert kwargs["params"]["searchString[0]"] == "9783406727788"


def test_parse_direct_hit_without_identifier() -> None:
    html = """
    <html>
        <body>
            <a href="/webOPACClient/singleHit.do?methodToCall=activateTab&tab=showExemplarActive">
                Exemplare
            </a>
            <a href="/webOPACClient/singleHit.do?methodToCall=activateTab&tab=showAvailabilityActive">
                Verfügbarkeit
            </a>
            <a href="/webOPACClient/singleHit.do?methodToCall=activateTab&tab=showTitleActive">
                Titel
            </a>
        </body>
    </html>
    """

    results = parse_catalog_hit_urls(
        html,
        "https://opac.stabi-hb.de/webOPACClient/search.do",
    )

    assert results == [
        (
            "https://opac.stabi-hb.de/"
            "webOPACClient/singleHit.do"
            "?methodToCall=activateTab"
            "&tab=showTitleActive"
        )
    ]