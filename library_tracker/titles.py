"""Title helpers: catalog sort markers and keys for comparing titles."""
from __future__ import annotations

import re

SORT_MARKERS = ("¬", "\u0098", "\u009c")


def strip_sort_markers(title: str) -> str:
    """Remove the non-sorting markers catalogs put around leading articles."""
    for marker in SORT_MARKERS:
        title = title.replace(marker, "")
    return " ".join(title.split())


def normalize_title(title: str) -> str:
    """Casefold, drop subtitles and punctuation for loose title comparison."""
    title = strip_sort_markers(title)
    main = re.split(r"\s[:\-–]\s|:", title, maxsplit=1)[0]
    words = re.findall(r"\w+", main.casefold())
    return " ".join(words)


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
