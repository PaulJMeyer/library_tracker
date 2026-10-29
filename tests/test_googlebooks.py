from unittest.mock import Mock, patch

import pytest
import requests

from library_tracker.googlebooks import (
    GoogleBooksClient,
    GoogleBooksError,
    normalize_isbn,
)


TEST_ISBN = "9783423449229"


def make_response(payload: dict[str, object]) -> Mock:
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_normalize_isbn() -> None:
    assert normalize_isbn(
        "978-3-423-44922-9"
    ) == "9783423449229"


def test_google_books_client_sets_api_key_header() -> None:
    client = GoogleBooksClient("test-api-key")

    assert (
        client.session.headers["X-Goog-Api-Key"]
        == "test-api-key"
    )


def test_resolve_isbn_returns_found() -> None:
    client = GoogleBooksClient("test-api-key")

    response = make_response(
        {
            "items": [
                {
                    "id": "volume123",
                    "volumeInfo": {
                        "title": "Example Book",
                        "authors": [
                            "Example Author",
                        ],
                        "language": "de",
                        "publisher": "Example Publisher",
                        "publishedDate": "2024",
                        "industryIdentifiers": [
                            {
                                "type": "ISBN_13",
                                "identifier": TEST_ISBN,
                            },
                            {
                                "type": "ISBN_10",
                                "identifier": "3423449220",
                            },
                        ],
                    },
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
            "library_tracker.googlebooks.time.sleep"
        ),
    ):
        result = client.resolve_isbns(
            [TEST_ISBN]
        )

    assert result == [
        {
            "isbn13": TEST_ISBN,
            "status": "found",
            "volume_id": "volume123",
            "title": "Example Book",
            "authors": [
                "Example Author",
            ],
            "language": "de",
            "publisher": "Example Publisher",
            "published_date": "2024",
            "identifiers": [
                {
                    "type": "ISBN_13",
                    "identifier": TEST_ISBN,
                },
                {
                    "type": "ISBN_10",
                    "identifier": "3423449220",
                },
            ],
            "error_message": None,
        }
    ]


def test_resolve_isbn_returns_not_found() -> None:
    client = GoogleBooksClient("test-api-key")

    response = make_response(
        {
            "totalItems": 0,
        }
    )

    with (
        patch.object(
            client.session,
            "get",
            return_value=response,
        ),
        patch(
            "library_tracker.googlebooks.time.sleep"
        ),
    ):
        result = client.resolve_isbns(
            [TEST_ISBN]
        )

    assert result == [
        {
            "isbn13": TEST_ISBN,
            "status": "not_found",
            "volume_id": None,
            "title": None,
            "authors": [],
            "language": None,
            "publisher": None,
            "published_date": None,
            "identifiers": [],
            "error_message": None,
        }
    ]


def test_resolve_isbn_ignores_wrong_isbn() -> None:
    client = GoogleBooksClient("test-api-key")

    response = make_response(
        {
            "items": [
                {
                    "id": "wrong-volume",
                    "volumeInfo": {
                        "title": "Wrong Book",
                        "industryIdentifiers": [
                            {
                                "type": "ISBN_13",
                                "identifier": "9780000000000",
                            }
                        ],
                    },
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
            "library_tracker.googlebooks.time.sleep"
        ),
    ):
        result = client.resolve_isbns(
            [TEST_ISBN]
        )

    assert result[0]["status"] == "not_found"


def test_resolve_isbn_returns_ambiguous() -> None:
    client = GoogleBooksClient("test-api-key")

    response = make_response(
        {
            "items": [
                {
                    "id": "volume123",
                    "volumeInfo": {
                        "title": "Example Book",
                        "industryIdentifiers": [
                            {
                                "type": "ISBN_13",
                                "identifier": TEST_ISBN,
                            }
                        ],
                    },
                },
                {
                    "id": "volume456",
                    "volumeInfo": {
                        "title": "Another Book",
                        "industryIdentifiers": [
                            {
                                "type": "ISBN_13",
                                "identifier": TEST_ISBN,
                            }
                        ],
                    },
                },
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
            "library_tracker.googlebooks.time.sleep"
        ),
    ):
        result = client.resolve_isbns(
            [TEST_ISBN]
        )

    assert result == [
        {
            "isbn13": TEST_ISBN,
            "status": "ambiguous",
            "volume_id": None,
            "title": None,
            "authors": [],
            "language": None,
            "publisher": None,
            "published_date": None,
            "identifiers": [],
            "error_message": (
                "ISBN matched multiple "
                "Google Books volumes."
            ),
        }
    ]


def test_resolve_isbn_raises_on_request_error() -> None:
    client = GoogleBooksClient("test-api-key")

    with (
        patch.object(
            client.session,
            "get",
            side_effect=requests.Timeout,
        ),
        patch(
            "library_tracker.googlebooks.time.sleep"
        ),
        pytest.raises(
            GoogleBooksError,
            match="Google Books request failed",
        ),
    ):
        client.resolve_isbns(
            [TEST_ISBN]
        )