"""Title keys for comparing catalog titles of Merkliste entries."""
from __future__ import annotations

import re

from library_tracker.clients.openlibrary import strip_sort_markers

LEADING_ARTICLES = frozenset({"der", "die", "das", "ein", "eine", "the", "a", "an"})


def merkliste_title_key(title: str) -> str:
    """Key under which two catalog titles count as the same book.

    Stricter than `normalize_title`: series titles such as
    "Red Rising - Das dunkle Zeitalter, Teil 1" keep everything after the dash,
    so different books of a series stay apart. Only a subtitle after ':' and a
    leading article are dropped ("Der Krieg der Welten" = "Krieg der Welten").
    """
    stripped = strip_sort_markers(title)
    words = re.findall(r"\w+", stripped.split(":", 1)[0].casefold())
    if len(words) > 1 and words[0] in LEADING_ARTICLES:
        words = words[1:]
    return " ".join(words) or stripped.casefold()
