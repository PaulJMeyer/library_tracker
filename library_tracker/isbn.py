def normalize_isbn(value: str) -> str:
    """Return an ISBN containing only digits and a possible ISBN-10 X."""
    return "".join(
        character
        for character in value.upper()
        if character.isdigit() or character == "X"
    )
