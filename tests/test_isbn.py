from library_tracker.isbn import normalize_isbn


def test_normalize_isbn() -> None:
    assert normalize_isbn("978-0-000-00010-6") == "9780000000106"
    assert normalize_isbn("0-306-40615-X") == "030640615X"
