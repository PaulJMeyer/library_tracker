import os
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from requests import Response, Session

from library_tracker.login import (
    LOGIN_PAGE_URL,
    LOGIN_URL,
    extract_login_payload,
    get_login_page,
    login,
)


def make_session_mock() -> tuple[Session, MagicMock]:
    session_mock = MagicMock(spec=Session)
    return cast(Session, session_mock), session_mock


def make_response_mock(text: str) -> MagicMock:
    response = MagicMock(spec=Response)
    response.text = text
    return response


def test_get_login_page() -> None:
    session, _ = make_session_mock()
    response = make_response_mock("<html>login</html>")

    with patch("library_tracker.login.get", return_value=response) as mock_get:
        result = get_login_page(session)

    mock_get.assert_called_once_with(
        session,
        LOGIN_PAGE_URL,
        delay=False,
    )
    assert result is response


def test_extract_login_payload() -> None:
    html = '<input name="CSId" value="abc-123">'

    with patch.dict(
        os.environ,
        {
            "LIBRARY_USERNAME": "test-user",
            "LIBRARY_PASSWORD": "test-password",
        },
    ):
        payload = extract_login_payload(html)

    assert payload["methodToCall"] == "submit"
    assert payload["CSId"] == "abc-123"
    assert payload["username"] == "test-user"
    assert payload["password"] == "test-password"
    assert payload["login_action"] == "Login"


def test_extract_login_payload_without_csid_raises_error() -> None:
    with pytest.raises(
        ValueError,
        match="CSId wurde nicht gefunden",
    ):
        extract_login_payload("<html><body></body></html>")


def test_login_success(capsys: pytest.CaptureFixture[str]) -> None:
    session, session_mock = make_session_mock()
    login_page = make_response_mock('<input name="CSId" value="abc-123">')
    login_response = make_response_mock(
        '<a href="?methodToCall=logout">Logout</a>'
    )

    with (
        patch(
            "library_tracker.login.Session",
            return_value=session_mock,
        ),
        patch(
            "library_tracker.login.get_login_page",
            return_value=login_page,
        ),
        patch(
            "library_tracker.login.post",
            return_value=login_response,
        ) as mock_post,
        patch.dict(
            os.environ,
            {
                "LIBRARY_USERNAME": "test-user",
                "LIBRARY_PASSWORD": "test-password",
            },
        ),
    ):
        result = login()

    assert result is session_mock
    mock_post.assert_called_once_with(
        session_mock,
        LOGIN_URL,
        data={
            "methodToCall": "submit",
            "CSId": "abc-123",
            "username": "test-user",
            "password": "test-password",
            "login_action": "Login",
        },
        delay=False,
    )
    login_response.raise_for_status.assert_called_once_with()

    captured = capsys.readouterr()
    assert "Login erfolgreich." in captured.out
    assert cast(Session, result) is session


def test_login_invalid_response_raises_error() -> None:
    _, session_mock = make_session_mock()
    login_page = make_response_mock('<input name="CSId" value="abc-123">')
    login_response = make_response_mock("<html>Login form</html>")

    with (
        patch(
            "library_tracker.login.Session",
            return_value=session_mock,
        ),
        patch(
            "library_tracker.login.get_login_page",
            return_value=login_page,
        ),
        patch(
            "library_tracker.login.post",
            return_value=login_response,
        ),
        patch.dict(
            os.environ,
            {
                "LIBRARY_USERNAME": "test-user",
                "LIBRARY_PASSWORD": "test-password",
            },
        ),
        pytest.raises(
            ValueError,
            match="Login wahrscheinlich fehlgeschlagen",
        ),
    ):
        login()
