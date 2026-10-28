from __future__ import annotations

import re
from typing import cast
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from library_tracker.models import ReadoWishlistEntry


READO_BASE_URL = "https://reado.app"
BOOK_PATH_PATTERN = re.compile(
    r"^/(?:de|en)/book/[^/?#]+/(?P<isbn>97[89]\d{10})/?$"
)


class ReadoWishlistError(RuntimeError):
    """Raised when a READO wishlist cannot be read reliably."""


def parse_reado_book_href(href: str) -> ReadoWishlistEntry | None:
    """Convert a READO book link into a wishlist entry."""
    absolute_url = urljoin(READO_BASE_URL, href)
    parsed = urlparse(absolute_url)

    if parsed.scheme != "https" or parsed.netloc != "reado.app":
        return None

    match = BOOK_PATH_PATTERN.match(parsed.path)
    if match is None:
        return None

    return {
        "isbn13": match.group("isbn"),
        "reado_url": f"{READO_BASE_URL}{parsed.path}",
    }


def entries_from_hrefs(hrefs: list[str]) -> list[ReadoWishlistEntry]:
    """Extract unique READO book entries from raw anchor hrefs."""
    entries_by_isbn: dict[str, ReadoWishlistEntry] = {}

    for href in hrefs:
        entry = parse_reado_book_href(href)
        if entry is None:
            continue

        entries_by_isbn.setdefault(entry["isbn13"], entry)

    return sorted(
        entries_by_isbn.values(),
        key=lambda entry: entry["isbn13"],
    )


def _collect_entries(page: Page) -> list[ReadoWishlistEntry]:
    locator = page.locator('a[href*="/book/"]')
    hrefs = cast(
        list[str],
        locator.evaluate_all(
            """
            elements => elements
                .map(element => element.getAttribute("href"))
                .filter(href => href !== null)
            """
        ),
    )
    return entries_from_hrefs(hrefs)


def read_reado_wishlist(
    wishlist_url: str,
    *,
    headless: bool = True,
    max_scrolls: int = 120,
    stable_rounds: int = 4,
    scroll_wait_ms: int = 700,
) -> list[ReadoWishlistEntry]:
    """
    Load a public READO wishlist and extract all ISBN-bearing book links.

    READO loads wishlist entries dynamically, so the page is scrolled until
    the number of discovered ISBNs has remained unchanged for several rounds.
    """
    parsed_url = urlparse(wishlist_url)
    if (
        parsed_url.scheme != "https"
        or parsed_url.netloc != "reado.app"
        or "/lists/_wishlist" not in parsed_url.path
    ):
        raise ReadoWishlistError(
            "Expected a public READO wishlist URL "
            "(https://reado.app/.../lists/_wishlist?...)."
        )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        page = browser.new_page(
            viewport={"width": 1280, "height": 900},
        )

        try:
            page.goto(
                wishlist_url,
                wait_until="domcontentloaded",
                timeout=45_000,
            )

            try:
                page.wait_for_selector(
                    'a[href*="/book/"]',
                    timeout=20_000,
                )
            except PlaywrightTimeoutError as exc:
                raise ReadoWishlistError(
                    "No book links appeared on the READO wishlist. "
                    "Check that the list is public and the URL is correct."
                ) from exc

            previous_count = -1
            unchanged_rounds = 0
            entries: list[ReadoWishlistEntry] = []

            for _ in range(max_scrolls):
                entries = _collect_entries(page)
                current_count = len(entries)

                if current_count == previous_count:
                    unchanged_rounds += 1
                else:
                    unchanged_rounds = 0
                    previous_count = current_count

                if unchanged_rounds >= stable_rounds:
                    break

                page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight)"
                )
                page.mouse.wheel(0, 8_000)
                page.wait_for_timeout(scroll_wait_ms)

            return entries
        finally:
            browser.close()
