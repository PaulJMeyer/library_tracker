import pytest

from library_tracker.clients.reado import ReadoError, entries_from_hrefs, parse_book_href, read_list


def test_parse_book_href() -> None:
    assert parse_book_href("/de/book/pause-lena-kupke/9783423449229") == {
        "isbn13": "9783423449229",
        "reado_url": "https://reado.app/de/book/pause-lena-kupke/9783423449229",
    }
    assert parse_book_href("https://example.com/de/book/test/9783423449229") is None


def test_entries_from_hrefs_deduplicates() -> None:
    entries = entries_from_hrefs(
        [
            "/de/book/a/9783423449229",
            "/de/book/a/9783423449229?source=list",
            "/en/book/b/9798987380420",
        ]
    )
    assert [entry["isbn13"] for entry in entries] == ["9783423449229", "9798987380420"]


def test_read_list_rejects_wrong_url() -> None:
    with pytest.raises(ReadoError, match="Expected a public READO URL"):
        read_list("https://example.com/list")
