import pytest

from library_tracker.reado import (
    ReadoWishlistError,
    entries_from_hrefs,
    parse_reado_book_href,
    read_reado_wishlist,
)


def test_parse_reado_book_href_relative_german_url() -> None:
    entry = parse_reado_book_href(
        "/de/book/pause-lena-kupke/9783423449229"
    )

    assert entry == {
        "isbn13": "9783423449229",
        "reado_url": (
            "https://reado.app/de/book/"
            "pause-lena-kupke/9783423449229"
        ),
    }


def test_parse_reado_book_href_absolute_english_url() -> None:
    entry = parse_reado_book_href(
        "https://reado.app/en/book/example-book/9798987380420"
    )

    assert entry == {
        "isbn13": "9798987380420",
        "reado_url": (
            "https://reado.app/en/book/"
            "example-book/9798987380420"
        ),
    }


@pytest.mark.parametrize(
    "href",
    [
        "https://example.com/de/book/test/9783423449229",
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
            "/de/book/book-a/9783423449229",
            "/de/book/book-a/9783423449229?source=list",
            "/de/book/book-b/9798987380420",
            "/de/profile/user",
        ]
    )

    assert entries == [
        {
            "isbn13": "9783423449229",
            "reado_url": (
                "https://reado.app/de/book/book-a/9783423449229"
            ),
        },
        {
            "isbn13": "9798987380420",
            "reado_url": (
                "https://reado.app/de/book/book-b/9798987380420"
            ),
        },
    ]


def test_read_reado_wishlist_rejects_wrong_url() -> None:
    with pytest.raises(
        ReadoWishlistError,
        match="Expected a public READO wishlist URL",
    ):
        read_reado_wishlist(
            "https://example.com/wishlist",
        )
