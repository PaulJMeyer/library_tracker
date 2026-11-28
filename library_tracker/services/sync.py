"""Daily pipeline: READO lists -> metadata -> catalog matches -> Merkliste -> overview."""
from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import TypeVar

from library_tracker.clients.dnb import DnbError
from library_tracker.clients.googlebooks import GoogleBooksError
from library_tracker.clients.library import LibraryClient, LibraryClientError
from library_tracker.clients.openlibrary import OpenLibraryError
from library_tracker.clients.reado import ReadoError
from library_tracker.config import (
    READO_LIST_LABELS,
    ConfigurationError,
    configured_reado_list_types,
)
from library_tracker.database import open_database
from library_tracker.progress import log
from library_tracker.titles import merkliste_title_key
from library_tracker.models import ReadoListType, ScrapeResult
from library_tracker.repositories.library_matches import get_wishlist_catalog_titles
from library_tracker.services.library_matching import (
    add_matches_to_merkliste,
    match_wishlist_books,
)
from library_tracker.services.library_scrape import scrape_library
from library_tracker.services.merkliste_cleanup import (
    remove_ebooks_from_merkliste,
    remove_finished_from_merkliste,
)
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


class SyncReport:
    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.added_titles: list[str] = []
        self.review_titles: list[str] = []
        self.removed_titles: list[str] = []
        self.scrape: ScrapeResult | None = None
        # None: no second wishlist configured, so the overview has no extra section.
        self.second_wishlist_titles: list[str] | None = None
        self.own_wishlist_titles: list[str] = []

    def step(self, name: str, action: Callable[[], T]) -> T | None:
        log(f"== {name}")
        try:
            return action()
        except EXPECTED_ERRORS as exc:
            log(f"   Fehler: {exc}")
            self.warnings.append(f"{name} fehlgeschlagen")
            return None


def _sync_list(list_type: ReadoListType) -> None:
    sync_lists(headless=True, list_types=(list_type,))


def _wishlist_titles() -> tuple[list[str], list[str]]:
    """Catalog titles on the own and on the second wishlist."""
    with open_database() as connection:
        return (
            get_wishlist_catalog_titles(connection, "wishlist"),
            get_wishlist_catalog_titles(connection, "second_wishlist"),
        )


def _clean_up_merkliste(scrape: ScrapeResult, library: LibraryClient) -> list[tuple[str, str, str]]:
    """E-books first, then books on a finished READO list."""
    ebooks = remove_ebooks_from_merkliste(scrape["entries"], library)
    others = [entry for entry in scrape["entries"] if not entry.get("ebook")]
    return ebooks + remove_finished_from_merkliste(others, library)


def run_sync(
    *,
    client: LibraryClient | None = None,
    fresh_login: Callable[[], LibraryClient] = LibraryClient.login,
    log: Callable[[str], None] = log,
) -> SyncReport:
    report = SyncReport()

    # Each list on its own: one failing list (for example an empty one) must not
    # keep the others from being updated.
    for list_type in configured_reado_list_types():
        report.step(f"READO-Liste {READO_LIST_LABELS[list_type]}", partial(_sync_list, list_type))
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
        log(
            f"   {summary['new_matches']} neue Treffer, {summary.get('new_editions', 0)} neue Ausgaben, "
            f"{summary['searched']} ISBNs gesucht"
        )
        if summary["errors"]:
            report.warnings.append(f"Katalogsuche: {summary['errors']} Fehler")

    report.scrape = report.step("Merkliste lesen", lambda: scrape_library(library))
    if report.scrape is None:
        return report

    # Removing first keeps the Merkliste page data from the scrape valid.
    scrape = report.scrape
    removals = report.step("Merkliste aufräumen", lambda: _clean_up_merkliste(scrape, library))
    if removals:
        report.removed_titles = [title for _, title, status in removals if status == "removed"]
        failed_removals = sum(status == "failed" for _, _, status in removals)
        if failed_removals:
            report.warnings.append(f"{failed_removals} Titel nicht von der Merkliste entfernt")

    removed = {merkliste_title_key(title) for title in report.removed_titles}
    existing = [title for title in scrape["all_titles"] if merkliste_title_key(title) not in removed]
    existing_media = [
        number
        for entry in scrape["entries"]
        if merkliste_title_key(entry["title"]) not in removed
        for number in entry.get("media_numbers", [])
    ]
    results = report.step(
        "Merkliste ergänzen",
        lambda: add_matches_to_merkliste(existing, library, existing_media_numbers=existing_media),
    )
    if results:
        report.added_titles = [title for _, title, status in results if status == "added"]
        report.review_titles = [title for _, title, status in results if status == "needs_review"]
        failed = sum(status == "failed" for _, _, status in results)
        if failed:
            report.warnings.append(f"{failed} Titel nicht auf die Merkliste gesetzt")

    if report.added_titles or report.removed_titles:
        # A fresh session: after adding or removing entries, paging through the
        # Merkliste in the same OPAC session only returned the first page.
        rescrape = report.step("Merkliste neu lesen", lambda: scrape_library(fresh_login()))
        expected = scrape["total_entries"] - len(report.removed_titles) + len(report.added_titles)
        if rescrape is not None and rescrape["total_entries"] >= expected:
            report.scrape = rescrape
        elif rescrape is not None:
            log(
                f"   Nur {rescrape['total_entries']} von mindestens {expected} Einträgen gelesen, "
                "verwende die erste Lesung."
            )
            report.warnings.append("Merkliste nach dem Ergänzen unvollständig gelesen")

    if "second_wishlist" in configured_reado_list_types():
        titles = report.step("Zweite Wunschliste zuordnen", _wishlist_titles)
        if titles is not None:
            report.own_wishlist_titles, report.second_wishlist_titles = titles
    return report
