from unittest.mock import Mock, patch

import pytest
import requests

from library_tracker.clients.library import (
    ACCOUNT_URL,
    CATALOG_SEARCH_URL,
    LOGIN_URL,
    LibraryClient,
    LibraryClientError,
)
from library_tracker.config import ConfigurationError
from library_tracker.models import MemorizePage


def response(text: str = "", *, url: str = "https://example.com", status: int = 200) -> Mock:
    result = Mock(spec=requests.Response)
    result.text = text
    result.url = url
    result.status_code = status
    result.raise_for_status.return_value = None
    return result


def test_login_builds_authenticated_client() -> None:
    session = Mock(spec=requests.Session)
    login_page = response('<input name="CSId" value="abc">')
    login_response = response('<a href="?methodToCall=logout">Logout</a>')

    with (
        patch("library_tracker.clients.library.requests.Session", return_value=session),
        patch("library_tracker.clients.library._get", return_value=login_page),
        patch("library_tracker.clients.library._post", return_value=login_response) as post,
        patch.dict(
            "os.environ",
            {"LIBRARY_USERNAME": "user", "LIBRARY_PASSWORD": "password"},
            clear=True,
        ),
    ):
        client = LibraryClient.login()

    assert client.session is session
    assert client.cs_id == "abc"
    assert post.call_args.kwargs["data"]["username"] == "user"


def test_login_rejects_invalid_response() -> None:
    with (
        patch("library_tracker.clients.library.requests.Session"),
        patch(
            "library_tracker.clients.library._get",
            return_value=response('<input name="CSId" value="abc">'),
        ),
        patch("library_tracker.clients.library._post", return_value=response("login form")),
        patch.dict(
            "os.environ",
            {"LIBRARY_USERNAME": "user", "LIBRARY_PASSWORD": "password"},
            clear=True,
        ),
        pytest.raises(LibraryClientError, match="Login"),
    ):
        LibraryClient.login()


def test_login_requires_credentials() -> None:
    with (
        patch("library_tracker.clients.library.requests.Session"),
        patch(
            "library_tracker.clients.library._get",
            return_value=response('<input name="CSId" value="abc">'),
        ),
        patch.dict("os.environ", {}, clear=True),
        pytest.raises(ConfigurationError),
    ):
        LibraryClient.login()


def test_get_all_memorize_pages_and_remove_entries() -> None:
    client = LibraryClient(Mock(spec=requests.Session), "csid")
    first = response(
        '<form id="MemorizeBean"><input name="CSId" value="csid">'
        '<input name="displayType" value="short"><input name="selectedMemorizeList" value="">'
        + "".join(
            '<div class="row border-bottom"><input type="checkbox" value="u">'
            '<a href="/webOPACClient/availability.do?methodToCall=runMemorizeAvailability">x</a></div>'
            for _ in range(3)
        )
        + "</form>"
    )
    with patch("library_tracker.clients.library._get", return_value=first):
        pages = client.get_all_memorize_pages()
    assert len(pages) == 1
    assert len(pages[0]["entries"]) == 3

    full_page = response(
        '<form id="MemorizeBean"><input name="CSId" value="csid"></form>'
        + "".join(
            f'<div class="row border-bottom"><input type="checkbox" value="u{i}">'
            '<a href="/webOPACClient/availability.do?methodToCall=runMemorizeAvailability">x</a></div>'
            for i in range(10)
        )
    )
    # The OPAC repeats the last page past the end: stop instead of looping forever.
    with patch("library_tracker.clients.library._get", return_value=full_page) as get:
        pages = client.get_all_memorize_pages()
    assert len(pages) == 1
    assert get.call_count == 2

    page: MemorizePage = {
        "cur_pos": "1",
        "cs_id": "csid",
        "display_type": "short",
        "selected_memorize_list": "",
        "entries": [],
    }
    with patch(
        "library_tracker.clients.library._get",
        return_value=response(status=200),
    ) as get:
        assert client.remove_entries(page, ["a", "b"]) is True
    assert get.call_args.kwargs["params"]["selectedMemListentries[1]"] == "b"


def test_account_availability_and_catalog_requests() -> None:
    client = LibraryClient(Mock(spec=requests.Session), "csid")
    with patch(
        "library_tracker.clients.library._get",
        side_effect=[response(), response("availability"), response("account")],
    ):
        assert client.get_availability_page("https://example.com/availability") == "availability"
        assert client.get_account_page() == "account"

    hit_url = "https://opac.stabi-hb.de/webOPACClient/singleHit.do?identifier=123"
    with patch(
        "library_tracker.clients.library._get",
        return_value=response("", url=hit_url),
    ) as get:
        assert client.search_catalog_by_isbn("978-0-000-00010-5") == [hit_url]
    assert get.call_args.args[1] == CATALOG_SEARCH_URL
    assert get.call_args.kwargs["params"]["searchString[0]"] == "9780000000105"


def test_get_retries_timeouts_then_succeeds() -> None:
    from library_tracker.clients.library import _get

    session = Mock(spec=requests.Session)
    session.get.side_effect = [requests.Timeout(), response("ok")]
    with patch("library_tracker.clients.library.time.sleep") as sleep:
        assert _get(session, "https://example.com/search.do?x=1").text == "ok"
    assert session.get.call_count == 2
    assert sleep.call_count == 2  # request delay + one retry delay


def test_get_reports_cause_after_retries() -> None:
    from library_tracker.clients.library import _get

    session = Mock(spec=requests.Session)
    session.get.side_effect = requests.ConnectionError()
    with (
        patch("library_tracker.clients.library.time.sleep"),
        pytest.raises(LibraryClientError, match=r"ConnectionError\): https://example.com/search.do$"),
    ):
        _get(session, "https://example.com/search.do?CSId=secret")
    assert session.get.call_count == 3


def test_get_retries_server_errors() -> None:
    from library_tracker.clients.library import _get

    session = Mock(spec=requests.Session)
    session.get.side_effect = [response(status=503), response("ok")]
    with patch("library_tracker.clients.library.time.sleep"):
        assert _get(session, "https://example.com").text == "ok"


def test_catalog_search_logs_in_again_after_failure() -> None:
    client = LibraryClient(Mock(spec=requests.Session), "old-csid")
    fresh = LibraryClient(Mock(spec=requests.Session), "new-csid")
    hit_url = "https://opac.stabi-hb.de/webOPACClient/singleHit.do?identifier=1"
    with (
        patch(
            "library_tracker.clients.library._get",
            side_effect=[LibraryClientError("expired"), response("", url=hit_url)],
        ) as get,
        patch.object(LibraryClient, "login", return_value=fresh),
    ):
        assert client.search_catalog_by_isbn("9780000000105") == [hit_url]

    assert client.cs_id == "new-csid"
    assert get.call_args.kwargs["params"]["CSId"] == "new-csid"
