from unittest.mock import Mock, patch

import pytest
import requests

from library_tracker.openlibrary import (
    OpenLibraryClient,
    OpenLibraryError,
)


TEST_ISBN = "9783423449229"


def make_response(payload: dict[str, object]) -> Mock:
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_openlibrary_client_sets_user_agent() -> None:
    client = OpenLibraryClient(
        "test@example.com"
    )

    assert client.session.headers["User-Agent"] == (
        "library-tracker/1.0 "
        "(test@example.com)"
    )


def test_resolve_isbn_returns_work() -> None:
    client = OpenLibraryClient(
        "test@example.com"
    )

    response = make_response(
        {
            "docs": [
                {
                    "key": "/works/OL123W",
                    "title": "Example Book",
                    "isbn": [
                        TEST_ISBN,
                        "9780000000000",
                    ],
                }
            ]
        }
    )

    with (
        patch.object(
            client.session,
            "get",
            return_value=response,
        ),
        patch(
            "library_tracker.openlibrary.time.sleep"
        ),
    ):
        result = client.resolve_isbns(
            [TEST_ISBN]
        )

    assert result == [
        {
            "isbn13": TEST_ISBN,
            "status": "resolved",
            "work_key": "OL123W",
            "title": "Example Book",
            "error_message": None,
        }
    ]


def test_resolve_isbn_returns_not_found() -> None:
    client = OpenLibraryClient(
        "test@example.com"
    )

    search_response = make_response(
        {
            "docs": [],
        }
    )

    isbn_response = Mock()
    isbn_response.status_code = 404

    with (
        patch.object(
            client.session,
            "get",
            side_effect=[
                search_response,
                isbn_response,
            ],
        ),
        patch(
            "library_tracker.openlibrary.time.sleep"
        ),
    ):
        result = client.resolve_isbns(
            [TEST_ISBN]
        )

    assert result == [
        {
            "isbn13": TEST_ISBN,
            "status": "not_found",
            "work_key": None,
            "title": None,
            "error_message": None,
        }
    ]


def test_resolve_isbn_returns_ambiguous() -> None:
    client = OpenLibraryClient(
        "test@example.com"
    )

    search_response = make_response(
        {
            "docs": [
                {
                    "key": "/works/OL123W",
                    "title": "Example Book",
                    "isbn": [TEST_ISBN],
                },
                {
                    "key": "/works/OL456W",
                    "title": "Another Book",
                    "isbn": [TEST_ISBN],
                },
            ]
        }
    )

    isbn_response = make_response(
        {
            "title": "Example Book",
            "works": [
                {
                    "key": "/works/OL123W",
                },
                {
                    "key": "/works/OL456W",
                },
            ],
        }
    )
    isbn_response.status_code = 200

    with (
        patch.object(
            client.session,
            "get",
            side_effect=[
                search_response,
                isbn_response,
            ],
        ),
        patch(
            "library_tracker.openlibrary.time.sleep"
        ),
    ):
        result = client.resolve_isbns(
            [TEST_ISBN]
        )

    assert result == [
        {
            "isbn13": TEST_ISBN,
            "status": "ambiguous",
            "work_key": None,
            "title": None,
            "error_message": (
                "ISBN is linked to multiple "
                "Open Library works."
            ),
        }
    ]


def test_resolve_isbn_raises_on_request_error() -> None:
    client = OpenLibraryClient(
        "test@example.com"
    )

    with (
        patch.object(
            client.session,
            "get",
            side_effect=requests.Timeout,
        ),
        patch(
            "library_tracker.openlibrary.time.sleep"
        ),
        pytest.raises(
            OpenLibraryError,
            match="Open Library request failed",
        ),
    ):
        client.resolve_isbns(
            [TEST_ISBN]
        )


def test_exact_isbn_fallback_resolves_work() -> None:
    client = OpenLibraryClient(
        "test@example.com"
    )

    search_response = make_response(
        {
            "docs": [],
        }
    )

    isbn_response = make_response(
        {
            "title": "Example Book",
            "works": [
                {
                    "key": "/works/OL123W",
                }
            ],
        }
    )
    isbn_response.status_code = 200

    with (
        patch.object(
            client.session,
            "get",
            side_effect=[
                search_response,
                isbn_response,
            ],
        ),
        patch(
            "library_tracker.openlibrary.time.sleep"
        ),
    ):
        result = client.resolve_isbns(
            [TEST_ISBN]
        )

    assert result == [
        {
            "isbn13": TEST_ISBN,
            "status": "resolved",
            "work_key": "OL123W",
            "title": "Example Book",
            "error_message": None,
        }
    ]


def test_exact_isbn_fallback_returns_not_found_on_404() -> None:
    client = OpenLibraryClient(
        "test@example.com"
    )

    search_response = make_response(
        {
            "docs": [],
        }
    )

    isbn_response = Mock()
    isbn_response.status_code = 404

    with (
        patch.object(
            client.session,
            "get",
            side_effect=[
                search_response,
                isbn_response,
            ],
        ),
        patch(
            "library_tracker.openlibrary.time.sleep"
        ),
    ):
        result = client.resolve_isbns(
            [TEST_ISBN]
        )

    assert result == [
        {
            "isbn13": TEST_ISBN,
            "status": "not_found",
            "work_key": None,
            "title": None,
            "error_message": None,
        }
    ]