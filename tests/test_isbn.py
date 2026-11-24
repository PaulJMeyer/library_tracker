from library_tracker.isbn import normalize_isbn


def test_normalize_isbn() -> None:
    assert normalize_isbn("978-0-000-00010-6") == "9780000000106"
    assert normalize_isbn("0-306-40615-X") == "030640615X"


def test_isbn10_to_isbn13() -> None:
    from library_tracker.isbn import isbn10_to_isbn13

    assert isbn10_to_isbn13("0-306-40615-2") == "9780306406157"
    assert isbn10_to_isbn13("3-499-62602-0") == "9783499626029"
    assert isbn10_to_isbn13("0-306-40615-3") is None  # wrong check digit
    assert isbn10_to_isbn13("12345") is None


def test_is_german_language_isbn() -> None:
    from library_tracker.isbn import is_german_language_isbn

    assert is_german_language_isbn("978-3-499-62602-9")
    assert not is_german_language_isbn("9780306406157")
