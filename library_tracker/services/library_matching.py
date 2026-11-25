from __future__ import annotations

import re
import sys
from collections.abc import Callable

from library_tracker.clients.library import LibraryClient, LibraryClientError
from library_tracker.database import get_connection, initialize_database
from library_tracker.models import (
    LibraryIsbnCandidate,
    LibraryMatchAttempt,
    LibraryMatchResult,
    MatchReportRow,
)
from library_tracker.repositories.matching import (
    get_wishlist_isbn_candidates,
    get_wishlist_metadata_states,
)


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


def _print_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def build_match_report(
    *,
    search: bool = True,
    client: LibraryClient | None = None,
    progress: Callable[[str], None] = _print_progress,
) -> list[MatchReportRow]:
    connection = get_connection()
    try:
        initialize_database(connection)
        states = get_wishlist_metadata_states(connection)
        candidate_counts = {
            str(state["isbn13"]): len(
                limit_candidates(get_wishlist_isbn_candidates(connection, str(state["isbn13"])))
            )
            for state in states
        }
    finally:
        connection.close()

    if search and states:
        client = client or LibraryClient.login()

    rows: list[MatchReportRow] = []
    for index, state in enumerate(states, start=1):
        isbn = str(state["isbn13"])
        metadata, reason = describe_metadata(state)
        count = candidate_counts[isbn]
        if reason is None and count <= 1:
            reason = (
                "DNB-Abfrage ausstehend (dnb-editions)"
                if state.get("dnb_status") is None
                else "Keine weiteren deutschen oder englischen Ausgaben bekannt"
            )
        match = None
        catalog_error: str | None = None
        if client is not None:
            progress(f"[{index}/{len(states)}] {isbn}: {count} ISBN(s) im Katalog suchen")
            try:
                match = match_wishlist_book(isbn, client)["match"]
            except LibraryClientError as exc:
                catalog_error = str(exc)
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
                "candidate_count": count,
                "catalog_checked": client is not None and catalog_error is None,
                "catalog_error": catalog_error,
                "match": match,
            }
        )
    return rows
