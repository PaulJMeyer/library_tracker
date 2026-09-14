from typing import cast
from unittest.mock import ANY, MagicMock, patch

from bs4 import BeautifulSoup, Tag
from requests import Response, Session

from library_tracker.models import MemorizePage
from library_tracker.wishlist import (
    WISHLIST_URL,
    _tag_value,
    extract_memorize_page,
    get_all_memorize_pages,
    get_wishlist_page,
    remove_entries,
)


def make_session_mock() -> tuple[Session, MagicMock]:
    session_mock = MagicMock(spec=Session)
    return cast(Session, session_mock), session_mock


def build_page_html(cur_pos: int, entry_count: int) -> str:
    entries_html = "".join(
        f"""
        <div class="row border-bottom py-2">
            <div class="col-auto my-2 order-1">
                <input
                    type="checkbox"
                    value="uuid-{cur_pos}-{index}"
                    name="selectedMemListentries[{index}]"
                >
            </div>
            <div class="col-12 col-md-9 my-2 order-4 order-md-3">
                <a href="/webOPACClient/availability.do?methodToCall=runMemorizeAvailability&amp;curPos={cur_pos}&amp;activeTab={index}">
                    zum Dokument
                </a>
            </div>
        </div>
        """
        for index in range(entry_count)
    )

    return f"""
    <html>
        <body>
            <form id="MemorizeBean">
                <input type="hidden" name="selectedMemorizeList" value="">
                <input type="hidden" name="displayType" value="short">
                <input type="hidden" name="curPos" value="{cur_pos}">
                <input type="hidden" name="CSId" value="test-cs-id">
                {entries_html}
            </form>
        </body>
    </html>
    """


def make_memorize_page() -> MemorizePage:
    return {
        "cur_pos": "21",
        "cs_id": "test-cs-id-123",
        "display_type": "short",
        "selected_memorize_list": "",
        "entries": [],
    }


def test_extract_memorize_page_finds_hidden_fields_and_entry() -> None:
    page = extract_memorize_page(build_page_html(cur_pos=21, entry_count=1), cur_pos=21)

    assert page["cur_pos"] == "21"
    assert page["cs_id"] == "test-cs-id"
    assert page["display_type"] == "short"
    assert page["selected_memorize_list"] == ""
    assert page["entries"] == [
        {
            "uuid": "uuid-21-0",
            "availability_link": (
                "https://opac.stabi-hb.de/webOPACClient/availability.do"
                "?methodToCall=runMemorizeAvailability&curPos=21&activeTab=0"
            ),
        }
    ]


def test_extract_memorize_page_skips_entry_without_link() -> None:
    html = """
    <html>
        <body>
            <form id="MemorizeBean">
                <input type="hidden" name="selectedMemorizeList" value="">
                <input type="hidden" name="displayType" value="short">
                <input type="hidden" name="CSId" value="test-cs-id">
                <div class="row border-bottom py-2">
                    <input type="checkbox" value="uuid-1">
                </div>
            </form>
        </body>
    </html>
    """

    page = extract_memorize_page(html, cur_pos=1)

    assert page["entries"] == []


def test_extract_memorize_page_without_form_uses_empty_hidden_values() -> None:
    page = extract_memorize_page("<html><body></body></html>", cur_pos=1)

    assert page == {
        "cur_pos": "1",
        "cs_id": "",
        "display_type": "",
        "selected_memorize_list": "",
        "entries": [],
    }


def test_tag_value_handles_list_attribute() -> None:
    soup = BeautifulSoup('<div class="first second"></div>', "html.parser")
    tag = soup.find("div")

    assert isinstance(tag, Tag)
    assert _tag_value(tag, "class") == "first"


def test_tag_value_missing_attribute_returns_empty_string() -> None:
    soup = BeautifulSoup("<div></div>", "html.parser")
    tag = soup.find("div")

    assert isinstance(tag, Tag)
    assert _tag_value(tag, "missing") == ""


def test_get_wishlist_page_first_page() -> None:
    session, _ = make_session_mock()
    response = MagicMock(spec=Response)
    response.text = "<html>first page</html>"

    with patch("library_tracker.wishlist.get", return_value=response) as mock_get:
        result = get_wishlist_page(session)

    assert result == "<html>first page</html>"
    mock_get.assert_called_once_with(
        session,
        f"{WISHLIST_URL}?methodToCall=show",
    )


def test_get_wishlist_page_later_page() -> None:
    session, _ = make_session_mock()
    response = MagicMock(spec=Response)
    response.text = "<html>page 11</html>"

    with patch("library_tracker.wishlist.get", return_value=response) as mock_get:
        result = get_wishlist_page(session, cur_pos=11)

    assert result == "<html>page 11</html>"
    mock_get.assert_called_once_with(
        session,
        f"{WISHLIST_URL}?methodToCall=pos&curPos=11",
    )


def test_remove_entries_sends_correct_params() -> None:
    session, _ = make_session_mock()
    response = MagicMock(spec=Response)
    response.status_code = 200
    page = make_memorize_page()

    with patch("library_tracker.wishlist.get", return_value=response) as mock_get:
        result = remove_entries(
            session=session,
            page=page,
            uuids=["uuid-1", "uuid-2"],
        )

    assert result is True

    _, called_kwargs = mock_get.call_args
    params = called_kwargs["params"]

    assert params["methodToCall"] == "deleteSelectedEntries"
    assert params["CSId"] == "test-cs-id-123"
    assert params["curPos"] == "21"
    assert params["displayType"] == "short"
    assert params["selectedMemorizeList"] == ""
    assert params["selectedMemListentries[0]"] == "uuid-1"
    assert params["selectedMemListentries[1]"] == "uuid-2"


def test_remove_entries_no_uuids_skips_request() -> None:
    session, _ = make_session_mock()
    page = make_memorize_page()

    with patch("library_tracker.wishlist.get") as mock_get:
        result = remove_entries(session=session, page=page, uuids=[])

    mock_get.assert_not_called()
    assert result is True


def test_remove_entries_returns_false_on_error_status() -> None:
    session, _ = make_session_mock()
    response = MagicMock(spec=Response)
    response.status_code = 404
    page = make_memorize_page()

    with patch("library_tracker.wishlist.get", return_value=response):
        result = remove_entries(
            session=session,
            page=page,
            uuids=["uuid-1"],
        )

    assert result is False


def test_get_all_memorize_pages_single_page() -> None:
    session, _ = make_session_mock()
    html = build_page_html(cur_pos=1, entry_count=1)

    with patch(
        "library_tracker.wishlist.get_wishlist_page",
        return_value=html,
    ) as mock_get_wishlist_page:
        pages = get_all_memorize_pages(session)

    assert len(pages) == 1
    assert len(pages[0]["entries"]) == 1
    mock_get_wishlist_page.assert_called_once_with(ANY, 1)


def test_get_all_memorize_pages_empty_wishlist() -> None:
    session, _ = make_session_mock()
    html = build_page_html(cur_pos=1, entry_count=0)

    with patch(
        "library_tracker.wishlist.get_wishlist_page",
        return_value=html,
    ) as mock_get_wishlist_page:
        pages = get_all_memorize_pages(session)

    assert pages == []
    mock_get_wishlist_page.assert_called_once_with(ANY, 1)


def test_get_all_memorize_pages_multiple_pages() -> None:
    session, _ = make_session_mock()
    page_1_html = build_page_html(cur_pos=1, entry_count=10)
    page_2_html = build_page_html(cur_pos=11, entry_count=3)

    with patch(
        "library_tracker.wishlist.get_wishlist_page",
        side_effect=[page_1_html, page_2_html],
    ) as mock_get_wishlist_page:
        pages = get_all_memorize_pages(session)

    assert len(pages) == 2
    assert len(pages[0]["entries"]) == 10
    assert len(pages[1]["entries"]) == 3
    assert mock_get_wishlist_page.call_count == 2
    mock_get_wishlist_page.assert_any_call(ANY, 1)
    mock_get_wishlist_page.assert_any_call(ANY, 11)
