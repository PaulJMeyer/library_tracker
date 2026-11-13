from library_tracker.isbn import normalize_isbn


def test_normalize_isbn() -> None:
    assert normalize_isbn("978-3-423-44922-9") == "9783423449229"
    assert normalize_isbn("0-306-40615-X") == "030640615X"
