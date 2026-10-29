import pytest

from library_tracker.reado import   (ReadoWishlistError,
                                     entries_from_hrefs,
                                     parse_reado_book_href,
                                     read_reado_list)


def test_parse_reado_book_href_relative_german_url() -> None:
    entry = parse_reado_book_href(
        "/de/book/pause-lena-kupke/9780000000106"
    )

    assert entry == {
        "isbn13": "9780000000106",
        "reado_url": (
            "https://reado.app/de/book/"
            "pause-lena-kupke/9780000000106"
        ),
    }


def test_parse_reado_book_href_absolute_english_url() -> None:
    entry = parse_reado_book_href(
        "https://reado.app/en/book/example-book/9790000000107"
    )

    assert entry == {
        "isbn13": "9790000000107",
        "reado_url": (
            "https://reado.app/en/book/"
            "example-book/9790000000107"
        ),
    }


@pytest.mark.parametrize(
    "href",
    [
        "https://example.com/de/book/test/9780000000106",
        "/de/profile/test",
        "/de/book/test/1234567890",
        "/de/book/test/not-an-isbn",
    ],
)
def test_parse_reado_book_href_rejects_non_book_links(
    href: str,
) -> None:
    assert parse_reado_book_href(href) is None


def test_entries_from_hrefs_deduplicates_same_isbn() -> None:
    entries = entries_from_hrefs(
        [
            "/de/book/book-a/9780000000106",
            "/de/book/book-a/9780000000106?source=list",
            "/de/book/book-b/9790000000107",
            "/de/profile/user",
        ]
    )

    assert entries == [
        {
            "isbn13": "9780000000106",
            "reado_url": (
                "https://reado.app/de/book/book-a/9780000000106"
            ),
        },
        {
            "isbn13": "9790000000107",
            "reado_url": (
                "https://reado.app/de/book/book-b/9790000000107"
            ),
        },
    ]


def test_read_reado_list_rejects_wrong_url() -> None:
    with pytest.raises(
        ReadoWishlistError,
        match="Expected a public READO URL",
    ):
        read_reado_list(
            "https://example.com/list",
        )
