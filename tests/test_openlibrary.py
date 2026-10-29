from unittest.mock import Mock, patch

import pytest
import requests

from library_tracker.openlibrary import (OpenLibraryClient,
                                         OpenLibraryError,
                                         OpenLibraryClient,
                                         OpenLibraryError,
                                         _parse_edition)


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


def test_parse_german_paperback_edition() -> None:
    result = _parse_edition(
        "OL123W",
        {
            "key": "/books/OL123M",
            "title": "Example Book",
            "languages": [
                {"key": "/languages/ger"},
            ],
            "physical_format": "Paperback",
            "isbn_13": [
                "9783423449229",
            ],
        },
    )

    assert result == {
        "edition_key": "OL123M",
        "work_key": "OL123W",
        "title": "Example Book",
        "languages": ["de"],
        "physical_format": "Paperback",
        "print_status": "confirmed",
        "identifiers": [
            {
                "type": "ISBN_13",
                "identifier": "9783423449229",
            }
        ],
    }


def test_parse_english_edition_without_format() -> None:
    result = _parse_edition(
        "OL123W",
        {
            "key": "/books/OL456M",
            "title": "Example Book",
            "languages": [
                {"key": "/languages/eng"},
            ],
            "isbn_13": [
                "9780000000000",
            ],
        },
    )

    assert result is not None
    assert result["languages"] == ["en"]
    assert result["print_status"] == "unknown"
    assert result["physical_format"] is None


@pytest.mark.parametrize(
    "entry",
    [
        {
            "key": "/books/OL1M",
            "title": "French Book",
            "languages": [
                {"key": "/languages/fre"},
            ],
            "physical_format": "Paperback",
            "isbn_13": ["9780000000001"],
        },
        {
            "key": "/books/OL2M",
            "title": "E-Book",
            "languages": [
                {"key": "/languages/ger"},
            ],
            "physical_format": "eBook",
            "isbn_13": ["9780000000002"],
        },
        {
            "key": "/books/OL3M",
            "title": "Audio Book",
            "languages": [
                {"key": "/languages/eng"},
            ],
            "physical_format": "Audio CD",
            "isbn_13": ["9780000000003"],
        },
        {
            "key": "/books/OL4M",
            "title": "No ISBN",
            "languages": [
                {"key": "/languages/ger"},
            ],
            "physical_format": "Hardcover",
        },
    ],
)
def test_parse_edition_ignores_irrelevant_editions(
    entry: dict[str, object],
) -> None:
    assert _parse_edition(
        "OL123W",
        entry,
    ) is None


def test_get_work_editions_handles_pagination() -> None:
    client = OpenLibraryClient(
        "test@example.com"
    )

    first_response = make_response(
        {
            "size": 3,
            "entries": [
                {
                    "key": "/books/OL1M",
                    "title": "Edition 1",
                    "languages": [
                        {"key": "/languages/ger"},
                    ],
                    "physical_format": "Paperback",
                    "isbn_13": ["9780000000001"],
                },
                {
                    "key": "/books/OL2M",
                    "title": "Edition 2",
                    "languages": [
                        {"key": "/languages/eng"},
                    ],
                    "physical_format": "Hardcover",
                    "isbn_13": ["9780000000002"],
                },
            ],
        }
    )

    second_response = make_response(
        {
            "size": 3,
            "entries": [
                {
                    "key": "/books/OL3M",
                    "title": "Edition 3",
                    "languages": [
                        {"key": "/languages/ger"},
                    ],
                    "physical_format": "Paperback",
                    "isbn_13": ["9780000000003"],
                },
            ],
        }
    )

    with (
        patch.object(
            client.session,
            "get",
            side_effect=[
                first_response,
                second_response,
            ],
        ),
        patch(
            "library_tracker.openlibrary.EDITION_PAGE_SIZE",
            2,
        ),
        patch(
            "library_tracker.openlibrary.time.sleep"
        ),
    ):
        result = client.get_work_editions(
            "OL123W"
        )

    assert len(result) == 3
    assert {
        edition["edition_key"]
        for edition in result
    } == {
        "OL1M",
        "OL2M",
        "OL3M",
    }