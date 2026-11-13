import pytest

from library_tracker.clients.reado import ReadoError, entries_from_hrefs, parse_book_href, read_list


def test_parse_book_href() -> None:
    assert parse_book_href("/de/book/pause-lena-kupke/9780000000106") == {
        "isbn13": "9780000000106",
        "reado_url": "https://reado.app/de/book/pause-lena-kupke/9780000000106",
    }
    assert parse_book_href("https://example.com/de/book/test/9780000000106") is None


def test_entries_from_hrefs_deduplicates() -> None:
    entries = entries_from_hrefs(
        [
            "/de/book/a/9780000000106",
            "/de/book/a/9780000000106?source=list",
            "/en/book/b/9790000000107",
        ]
    )
    assert [entry["isbn13"] for entry in entries] == ["9780000000106", "9790000000107"]


def test_read_list_rejects_wrong_url() -> None:
    with pytest.raises(ReadoError, match="Expected a public READO URL"):
        read_list("https://example.com/list")
