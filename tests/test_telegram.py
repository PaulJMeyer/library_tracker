from unittest.mock import Mock

import pytest
import requests

from library_tracker.clients.telegram import TelegramClient, TelegramError, split_message


def make_client(response: Mock | None = None, error: Exception | None = None) -> tuple[TelegramClient, Mock]:
    session = Mock(spec=requests.Session)
    if error is not None:
        session.post.side_effect = error
    else:
        session.post.return_value = response or Mock(status_code=200)
    return TelegramClient("123:secret", "42", session=session), session


def test_send_message_posts_html_message() -> None:
    client, session = make_client()

    client.send_message("<b>Hallo</b>")

    url = session.post.call_args.args[0]
    data = session.post.call_args.kwargs["data"]
    assert url == "https://api.telegram.org/bot123:secret/sendMessage"
    assert data["chat_id"] == "42"
    assert data["text"] == "<b>Hallo</b>"
    assert data["parse_mode"] == "HTML"


def test_send_message_splits_long_text() -> None:
    client, session = make_client()

    client.send_message("\n".join(["x" * 3000, "y" * 3000]))

    assert session.post.call_count == 2


def test_send_message_raises_on_rejection() -> None:
    response = Mock(status_code=400)
    response.json.return_value = {"description": "Bad Request: chat not found"}
    client, _ = make_client(response=response)

    with pytest.raises(TelegramError, match="chat not found"):
        client.send_message("Hallo")


def test_request_error_does_not_leak_token() -> None:
    client, _ = make_client(error=requests.ConnectionError("https://api.telegram.org/bot123:secret"))

    with pytest.raises(TelegramError) as excinfo:
        client.send_message("Hallo")

    assert "secret" not in str(excinfo.value)


def test_split_message_keeps_short_text_together() -> None:
    assert split_message("a\nb\nc", limit=10) == ["a\nb\nc"]


def test_split_message_breaks_at_lines_and_long_lines() -> None:
    assert split_message("aaaa\nbbbb\ncc", limit=9) == ["aaaa\nbbbb", "cc"]
    assert split_message("abcdefghij", limit=4) == ["abcd", "efgh", "ij"]
