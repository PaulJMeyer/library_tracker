def normalize_isbn(value: str) -> str:
    """Return an ISBN containing only digits and a possible ISBN-10 X."""
    return "".join(
        character
        for character in value.upper()
        if character.isdigit() or character == "X"
    )


def isbn10_to_isbn13(value: str) -> str | None:
    """Convert a valid ISBN-10 to its 978-prefixed ISBN-13, else return None."""
    isbn10 = normalize_isbn(value)
    if len(isbn10) != 10 or not isbn10[:9].isdigit():
        return None
    check = sum((10 - index) * (10 if c == "X" else int(c)) for index, c in enumerate(isbn10))
    if check % 11 != 0:
        return None
    body = "978" + isbn10[:9]
    total = sum(int(c) * (1 if index % 2 == 0 else 3) for index, c in enumerate(body))
    return body + str((10 - total % 10) % 10)


def is_german_language_isbn(isbn13: str) -> bool:
    """ISBN group 978-3 covers the German-speaking countries (DE, AT, CH)."""
    return normalize_isbn(isbn13).startswith("9783")
