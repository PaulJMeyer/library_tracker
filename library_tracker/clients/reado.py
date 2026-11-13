from __future__ import annotations

import re
from typing import cast
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from library_tracker.config import READO_BASE_URL
from library_tracker.models import ReadoListEntry

BOOK_PATH_PATTERN = re.compile(r"^/(?:de|en)/book/[^/?#]+/(?P<isbn>97[89]\d{10})/?$")


class ReadoError(RuntimeError):
    """Raised when a public READO list cannot be read reliably."""


def parse_book_href(href: str) -> ReadoListEntry | None:
    parsed = urlparse(urljoin(READO_BASE_URL, href))
    if parsed.scheme != "https" or parsed.netloc != "reado.app":
        return None

    match = BOOK_PATH_PATTERN.match(parsed.path)
    if match is None:
        return None

    return {
        "isbn13": match.group("isbn"),
        "reado_url": f"{READO_BASE_URL}{parsed.path}",
    }


def entries_from_hrefs(hrefs: list[str]) -> list[ReadoListEntry]:
    entries: dict[str, ReadoListEntry] = {}
    for href in hrefs:
        entry = parse_book_href(href)
        if entry is not None:
            entries.setdefault(entry["isbn13"], entry)
    return sorted(entries.values(), key=lambda entry: entry["isbn13"])


def _collect_entries(page: Page) -> list[ReadoListEntry]:
    hrefs = cast(
        list[str],
        page.locator('a[href*="/book/"]').evaluate_all(
            """
            elements => elements
                .map(element => element.getAttribute("href"))
                .filter(href => href !== null)
            """
        ),
    )
    return entries_from_hrefs(hrefs)


def read_list(
    list_url: str,
    *,
    headless: bool = False,
    max_scrolls: int = 120,
    stable_rounds: int = 4,
    scroll_wait_ms: int = 700,
) -> list[ReadoListEntry]:
    parsed = urlparse(list_url)
    if parsed.scheme != "https" or parsed.netloc != "reado.app":
        raise ReadoError("Expected a public READO URL.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless, channel="chromium")
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(list_url, wait_until="domcontentloaded", timeout=45_000)
            try:
                page.wait_for_selector('a[href*="/book/"]', timeout=20_000)
            except PlaywrightTimeoutError as exc:
                raise ReadoError("No book links appeared on the READO list.") from exc

            previous_count = -1
            unchanged_rounds = 0
            entries: list[ReadoListEntry] = []

            for _ in range(max_scrolls):
                entries = _collect_entries(page)
                current_count = len(entries)
                if current_count == previous_count:
                    unchanged_rounds += 1
                else:
                    previous_count = current_count
                    unchanged_rounds = 0

                if unchanged_rounds >= stable_rounds:
                    break

                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.mouse.wheel(0, 8_000)
                page.wait_for_timeout(scroll_wait_ms)

            return entries
        finally:
            browser.close()
