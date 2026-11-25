"""Daily pipeline: READO wishlist -> metadata -> catalog matches -> Merkliste -> overview."""
from __future__ import annotations

import sys
from collections.abc import Callable
from typing import TypeVar

from library_tracker.clients.dnb import DnbError
from library_tracker.clients.googlebooks import GoogleBooksError
from library_tracker.clients.library import LibraryClient, LibraryClientError
from library_tracker.clients.openlibrary import OpenLibraryError
from library_tracker.clients.reado import ReadoError
from library_tracker.config import ConfigurationError, configured_reado_list_types
from library_tracker.models import ScrapeResult
from library_tracker.services.library_matching import (
    add_matches_to_merkliste,
    match_wishlist_books,
)
from library_tracker.services.library_scrape import scrape_library
from library_tracker.services.metadata import (
    link_googlebooks_titles,
    lookup_dnb_editions,
    resolve_googlebooks,
    resolve_openlibrary,
    sync_openlibrary_editions,
)
from library_tracker.services.reado_sync import sync_lists

EXPECTED_ERRORS = (
    ConfigurationError,
    ReadoError,
    OpenLibraryError,
    GoogleBooksError,
    DnbError,
    LibraryClientError,
)
T = TypeVar("T")


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


class SyncReport:
    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.added_titles: list[str] = []
        self.scrape: ScrapeResult | None = None

    def step(self, name: str, action: Callable[[], T]) -> T | None:
        _log(f"== {name}")
        try:
            return action()
        except EXPECTED_ERRORS as exc:
            _log(f"   Fehler: {exc}")
            self.warnings.append(f"{name} fehlgeschlagen")
            return None


def run_sync(*, client: LibraryClient | None = None, log: Callable[[str], None] = _log) -> SyncReport:
    report = SyncReport()

    report.step(
        "READO-Listen",
        lambda: sync_lists(headless=True, list_types=configured_reado_list_types()),
    )
    report.step("Open Library", resolve_openlibrary)
    report.step("Google Books", resolve_googlebooks)
    report.step("Titelsuche Open Library", link_googlebooks_titles)
    report.step("Open-Library-Ausgaben", sync_openlibrary_editions)
    report.step("DNB", lookup_dnb_editions)

    library = report.step("Bibliothek-Login", lambda: client or LibraryClient.login())
    if library is None:
        return report

    summary = report.step("Katalogsuche", lambda: match_wishlist_books(library))
    if summary:
        log(f"   {summary['new_matches']} neue Treffer, {summary['searched']} ISBNs gesucht")
        if summary["errors"]:
            report.warnings.append(f"Katalogsuche: {summary['errors']} Fehler")

    report.scrape = report.step("Merkliste lesen", lambda: scrape_library(library))
    if report.scrape is None:
        return report

    existing = report.scrape["all_titles"]
    results = report.step("Merkliste ergänzen", lambda: add_matches_to_merkliste(existing, library))
    if results:
        report.added_titles = [title for _, title, status in results if status == "added"]
        failed = sum(status == "failed" for _, _, status in results)
        if failed:
            report.warnings.append(f"{failed} Titel nicht auf die Merkliste gesetzt")
        if report.added_titles:
            rescrape = report.step("Merkliste neu lesen", lambda: scrape_library(library))
            if rescrape is not None:
                report.scrape = rescrape
    return report
