from typing import cast
from unittest.mock import MagicMock, patch

from requests import Response, Session

from library_tracker.client import (
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    build_url,
    get,
    post,
)


def make_session_mock() -> tuple[Session, MagicMock]:
    session_mock = MagicMock(spec=Session)
    return cast(Session, session_mock), session_mock


def make_response_mock() -> MagicMock:
    return MagicMock(spec=Response)


def test_build_url() -> None:
    assert build_url("/test") == "https://opac.stabi-hb.de/test"


def test_get_sends_request_and_returns_response() -> None:
    session, session_mock = make_session_mock()
    response = make_response_mock()
    session_mock.get.return_value = response

    with patch("library_tracker.client.time.sleep") as mock_sleep:
        result = get(
            session,
            "https://example.com/test",
            params={"page": "1"},
        )

    mock_sleep.assert_called_once_with(REQUEST_DELAY)
    session_mock.get.assert_called_once_with(
        "https://example.com/test",
        params={"page": "1"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status.assert_called_once_with()
    assert result is response


def test_get_without_delay_does_not_sleep() -> None:
    session, session_mock = make_session_mock()
    response = make_response_mock()
    session_mock.get.return_value = response

    with patch("library_tracker.client.time.sleep") as mock_sleep:
        get(
            session,
            "https://example.com/test",
            delay=False,
        )

    mock_sleep.assert_not_called()


def test_post_sends_data_and_returns_response() -> None:
    session, session_mock = make_session_mock()
    response = make_response_mock()
    session_mock.post.return_value = response

    with patch("library_tracker.client.time.sleep") as mock_sleep:
        result = post(
            session,
            "https://example.com/login",
            data={"username": "test"},
        )

    mock_sleep.assert_called_once_with(REQUEST_DELAY)
    session_mock.post.assert_called_once_with(
        "https://example.com/login",
        data={"username": "test"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status.assert_called_once_with()
    assert result is response


def test_post_without_delay_does_not_sleep() -> None:
    session, session_mock = make_session_mock()
    response = make_response_mock()
    session_mock.post.return_value = response

    with patch("library_tracker.client.time.sleep") as mock_sleep:
        post(
            session,
            "https://example.com/login",
            data={},
            delay=False,
        )

    mock_sleep.assert_not_called()
