from __future__ import annotations

import re
import sys
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import cast

from library_tracker.clients.library import LibraryClient, LibraryClientError
from library_tracker.database import get_connection, initialize_database
from library_tracker.models import (
    LibraryIsbnCandidate,
    LibraryIsbnCandidateSource,
    LibraryMatchAttempt,
    LibraryMatchResult,
    MatchReportRow,
)
from library_tracker.clients.openlibrary import normalize_title, strip_sort_markers
from library_tracker.parsers.library import (
    parse_exemplar_tab_url,
    parse_media_numbers,
    parse_single_hit,
)
from library_tracker.repositories.library_matches import (
    get_catalog_hits,
    get_edition_isbns,
    get_editions_to_memorize,
    get_match_states,
    get_recent_misses,
    get_searched_isbns,
    get_wishlist_isbns_for_search,
    save_catalog_edition,
    save_catalog_search,
    save_edition_memorize_result,
    save_library_match,
)
from library_tracker.repositories.matching import (
    get_wishlist_isbn_candidates,
    get_wishlist_metadata_states,
)

PER_BOOK_SEARCH_LIMIT = 15
# A single volume of a multi-volume edition ("Faust ..., Band 3") is usually not the
# wanted book, so such hits are reported for manual review instead of being added.
VOLUME_PATTERN = re.compile(r"\b(?:band|bd|vol|volume|teilband)\.?\s*\d+\b", re.IGNORECASE)


def is_single_volume(title: str) -> bool:
    return VOLUME_PATTERN.search(title) is not None

RECHECK_MISSES_AFTER_DAYS = 30
# Books that already have a catalog hit keep looking for further editions, but
# books without any hit get the catalog searches first.
EXTRA_EDITION_SEARCHES_PER_RUN = 150


def _now() -> datetime:
    return datetime.now(UTC)


def _print_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def search_catalog(isbn: str, client: LibraryClient | None = None) -> list[str]:
    return (client or LibraryClient.login()).search_catalog_by_isbn(isbn)


MAX_GERMAN_CANDIDATES = 12
MAX_ENGLISH_CANDIDATES = 3


def limit_candidates(candidates: list[LibraryIsbnCandidate]) -> list[LibraryIsbnCandidate]:
    """Keep catalog searches per book bounded; popular works have hundreds of editions."""
    german = [c for c in candidates if c["source"] != "openlibrary_english"]
    english = [c for c in candidates if c["source"] == "openlibrary_english"]
    return german[:MAX_GERMAN_CANDIDATES] + english[:MAX_ENGLISH_CANDIDATES]


def match_wishlist_book(
    reado_isbn: str,
    client: LibraryClient | None = None,
) -> LibraryMatchResult:
    connection = get_connection()
    try:
        initialize_database(connection)
        candidates = limit_candidates(get_wishlist_isbn_candidates(connection, reado_isbn))
    finally:
        connection.close()

    if not candidates:
        return {"reado_isbn": reado_isbn, "attempts": [], "match": None}

    client = client or LibraryClient.login()
    attempts: list[LibraryMatchAttempt] = []
    for candidate in candidates:
        hits = client.search_catalog_by_isbn(candidate["isbn"])
        attempts.append({**candidate, "hit_count": len(hits)})
        if hits:
            return {
                "reado_isbn": reado_isbn,
                "attempts": attempts,
                "match": candidate,
            }

    return {"reado_isbn": reado_isbn, "attempts": attempts, "match": None}


def _title_from_reado_url(url: str | None) -> str:
    match = re.search(r"/book/([^/]+)/", url or "")
    return match.group(1).replace("-", " ") if match else "?"


def describe_metadata(state: dict[str, str | None]) -> tuple[str, str | None]:
    """Return (metadata source label, reason why no alternative editions exist)."""
    ol_status, ol_source = state["ol_status"], state["ol_source"]
    dnb_found = state.get("dnb_status") == "found"
    dnb_pending = state.get("dnb_status") is None

    if ol_status is None:
        return "nicht abgefragt", "Metadaten noch nicht abgefragt (openlibrary-resolve)"
    if ol_status == "resolved":
        label = "Open Library (über Titel)" if ol_source == "openlibrary_title" else "Open Library"
        if dnb_found:
            label += " + DNB"
        if state["editions"] is None:
            return label, "Ausgaben noch nicht geladen (openlibrary-editions)"
        return label, None
    if dnb_found:
        return "DNB", None
    if ol_status in {"ambiguous", "failed"}:
        label, reason = "Open Library", f"Open Library: {ol_status}"
    elif state["gb_status"] is None:
        return "nicht gefunden", "Google-Books-Abfrage ausstehend (googlebooks-resolve)"
    elif state["gb_status"] != "found":
        label, reason = "nicht gefunden", "Weder Open Library, Google Books noch DNB kennen die ISBN"
    elif state["title_link"] is None:
        return "nur Google Books", "Titelsuche ausstehend (openlibrary-link-titles)"
    else:
        label, reason = "nur Google Books", "Kein passendes Open-Library-Werk über Titel/Autor"
    if dnb_pending:
        return label, "DNB-Abfrage ausstehend (dnb-editions)"
    return label, reason


def match_wishlist_books(
    client: LibraryClient | None = None,
    *,
    per_book_limit: int = PER_BOOK_SEARCH_LIMIT,
    recheck_days: int = RECHECK_MISSES_AFTER_DAYS,
    extra_edition_searches: int = EXTRA_EDITION_SEARCHES_PER_RUN,
    progress: Callable[[str], None] = _print_progress,
) -> dict[str, int]:
    """Search the catalog for every known edition of the wishlist books, a bounded batch
    of ISBNs per book and run.

    Books without any hit come first. Books that already have a hit keep searching for
    further editions, limited to `extra_edition_searches` ISBNs per run in total.
    ISBNs without a hit are remembered and skipped for `recheck_days`, found ISBNs
    are never searched again, so each run continues with the next candidates.
    """
    summary = {"books": 0, "searched": 0, "new_matches": 0, "new_editions": 0, "errors": 0}
    connection = get_connection()
    try:
        initialize_database(connection)
        since = (_now() - timedelta(days=recheck_days)).isoformat(timespec="seconds")
        books = get_wishlist_isbns_for_search(connection)
        summary["books"] = len(books)
        extra_budget = extra_edition_searches
        for index, (reado_isbn, matched) in enumerate(books, start=1):
            misses = get_recent_misses(connection, since)
            known_hits = get_catalog_hits(connection)
            editions = get_edition_isbns(connection, reado_isbn)

            def record_hit(candidate: LibraryIsbnCandidate) -> None:
                nonlocal matched
                now = _now().isoformat(timespec="seconds")
                save_catalog_edition(connection, reado_isbn, candidate["isbn"], candidate["source"], now)
                summary["new_editions"] += 1
                if not matched:
                    save_library_match(connection, reado_isbn, candidate["isbn"], candidate["source"], now)
                    summary["new_matches"] += 1
                    matched = True

            todo: list[LibraryIsbnCandidate] = []
            for candidate in get_wishlist_isbn_candidates(connection, reado_isbn):
                if candidate["isbn"] in editions:
                    continue
                if candidate["isbn"] in known_hits:
                    record_hit(candidate)  # found before, no new search needed
                elif candidate["isbn"] not in misses:
                    todo.append(candidate)
            todo = todo[: per_book_limit if not matched else min(per_book_limit, extra_budget)]
            if matched:
                extra_budget -= len(todo)
            if not todo:
                continue
            client = client or LibraryClient.login()
            progress(f"[{index}/{len(books)}] {reado_isbn}: {len(todo)} ISBN(s) im Katalog suchen")
            for candidate in todo:
                try:
                    hits = client.search_catalog_by_isbn(candidate["isbn"])
                except LibraryClientError as exc:
                    summary["errors"] += 1
                    progress(f"  Fehler: {exc}")
                    break
                summary["searched"] += 1
                now = _now().isoformat(timespec="seconds")
                save_catalog_search(connection, candidate["isbn"], hits[0] if hits else None, now)
                if hits:
                    record_hit(candidate)
        return summary
    finally:
        connection.close()


def _hit_media_numbers(
    client: LibraryClient, hit_url: str, html: str, page_url: str
) -> tuple[list[str], str]:
    """Copy numbers of a catalog hit and the (possibly re-read) hit page.

    If the hit page itself lists no copies, its copies tab is opened; the hit page
    is then read again so that its 'in die Merkliste' link belongs to the hit.
    """
    media_numbers = parse_media_numbers(html)
    if media_numbers:
        return media_numbers, html
    tab_url = parse_exemplar_tab_url(html, page_url)
    if tab_url is None:
        return [], html
    tab_html, _ = client.get_page(tab_url)
    media_numbers = parse_media_numbers(tab_html)
    html, _ = client.get_page(hit_url)
    return media_numbers, html


def add_matches_to_merkliste(
    existing_titles: list[str],
    client: LibraryClient | None = None,
    *,
    existing_media_numbers: Iterable[str] = (),
    progress: Callable[[str], None] = _print_progress,
) -> list[tuple[str, str, str]]:
    """Put every catalog edition of the wishlist books on the library Merkliste.

    Uses only the catalog's 'in die Merkliste' link (never orders or paid reservations).
    An edition counts as already listed when one of its copy numbers is on the Merkliste
    (same catalog record); without copy numbers the title is compared instead.
    Returns [(reado_isbn, catalog_title, status)] with status added/already_listed/failed/
    needs_review (an alternative edition that is a single volume of a multi-volume
    edition, not added).
    """
    known_titles = {normalize_title(title) for title in existing_titles}
    known_media = set(existing_media_numbers)
    results: list[tuple[str, str, str]] = []
    connection = get_connection()
    try:
        initialize_database(connection)
        for reado_isbn, edition_isbn in get_editions_to_memorize(connection):
            client = client or LibraryClient.login()
            title: str | None = None
            media_numbers: list[str] = []
            try:
                hits = client.search_catalog_by_isbn(edition_isbn)
                if not hits:
                    status = "failed"
                else:
                    html, page_url = client.get_page(hits[0])
                    media_numbers, html = _hit_media_numbers(client, hits[0], html, page_url)
                    raw_title, memorize_url = parse_single_hit(html, page_url)
                    title = strip_sort_markers(raw_title)
                    if media_numbers:
                        listed = not known_media.isdisjoint(media_numbers)
                    else:
                        listed = normalize_title(title) in known_titles
                    if listed:
                        status = "already_listed"
                    elif memorize_url is None:
                        status = "failed"
                    elif edition_isbn != reado_isbn and is_single_volume(title):
                        # Only alternative editions are checked: the exact READO ISBN
                        # (e.g. "Band 1" of a series) is what the user asked for.
                        status = "needs_review"
                    else:
                        client.add_to_memorize_list(memorize_url)
                        known_titles.add(normalize_title(title))
                        known_media.update(media_numbers)
                        status = "added"
            except LibraryClientError as exc:
                progress(f"  Merkliste-Fehler bei {edition_isbn}: {exc}")
                status = "failed"
            save_edition_memorize_result(
                connection,
                reado_isbn,
                edition_isbn,
                status,
                title,
                media_numbers,
                _now().isoformat(timespec="seconds"),
            )
            results.append((reado_isbn, title or edition_isbn, status))
        return results
    finally:
        connection.close()


def build_match_report() -> list[MatchReportRow]:
    """Per active wishlist book: metadata state, candidates, stored catalog result."""
    connection = get_connection()
    try:
        initialize_database(connection)
        states = get_wishlist_metadata_states(connection)
        matches = get_match_states(connection)
        searched = get_searched_isbns(connection)
        candidates = {
            str(state["isbn13"]): get_wishlist_isbn_candidates(connection, str(state["isbn13"]))
            for state in states
        }
    finally:
        connection.close()

    rows: list[MatchReportRow] = []
    for state in states:
        isbn = str(state["isbn13"])
        metadata, reason = describe_metadata(state)
        book_candidates = candidates[isbn]
        if reason is None and len(book_candidates) <= 1:
            reason = (
                "DNB-Abfrage ausstehend (dnb-editions)"
                if state.get("dnb_status") is None
                else "Keine weiteren deutschen oder englischen Ausgaben bekannt"
            )
        stored = matches.get(isbn)
        rows.append(
            {
                "isbn13": isbn,
                "title": (
                    state["ol_title"]
                    or state["gb_title"]
                    or state.get("dnb_title")
                    or _title_from_reado_url(state["reado_url"])
                ),
                "metadata": metadata,
                "reason": reason,
                "candidate_count": len(book_candidates),
                "searched_count": sum(c["isbn"] in searched for c in book_candidates),
                "match": (
                    {"isbn": stored[0], "source": cast(LibraryIsbnCandidateSource, stored[1])}
                    if stored
                    else None
                ),
                "memorize_status": stored[2] if stored else None,
            }
        )
    return rows
