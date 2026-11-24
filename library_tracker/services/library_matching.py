from __future__ import annotations

from library_tracker.clients.library import LibraryClient
from library_tracker.database import get_connection, initialize_database
import re

from library_tracker.models import LibraryMatchAttempt, LibraryMatchResult, MatchReportRow
from library_tracker.repositories.matching import (
    get_wishlist_isbn_candidates,
    get_wishlist_metadata_states,
)


def search_catalog(isbn: str, client: LibraryClient | None = None) -> list[str]:
    return (client or LibraryClient.login()).search_catalog_by_isbn(isbn)


def match_wishlist_book(
    reado_isbn: str,
    client: LibraryClient | None = None,
) -> LibraryMatchResult:
    connection = get_connection()
    try:
        initialize_database(connection)
        candidates = get_wishlist_isbn_candidates(connection, reado_isbn)
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
    if ol_status is None:
        return "nicht abgefragt", "Metadaten noch nicht abgefragt (openlibrary-resolve)"
    if ol_status == "resolved":
        label = "Open Library (über Titel)" if ol_source == "openlibrary_title" else "Open Library"
        if state["editions"] is None:
            return label, "Ausgaben noch nicht geladen (openlibrary-editions)"
        return label, None
    if ol_status in {"ambiguous", "failed"}:
        return "Open Library", f"Open Library: {ol_status}"
    if state["gb_status"] is None:
        return "nicht gefunden", "Google-Books-Abfrage ausstehend (googlebooks-resolve)"
    if state["gb_status"] != "found":
        return "nicht gefunden", "Weder Open Library noch Google Books kennen die ISBN"
    if state["title_link"] is None:
        return "nur Google Books", "Titelsuche ausstehend (openlibrary-link-titles)"
    return "nur Google Books", "Kein passendes Open-Library-Werk über Titel/Autor"


def build_match_report(
    *,
    search: bool = True,
    client: LibraryClient | None = None,
) -> list[MatchReportRow]:
    connection = get_connection()
    try:
        initialize_database(connection)
        states = get_wishlist_metadata_states(connection)
        candidate_counts = {
            str(state["isbn13"]): len(get_wishlist_isbn_candidates(connection, str(state["isbn13"])))
            for state in states
        }
    finally:
        connection.close()

    if search and states:
        client = client or LibraryClient.login()

    rows: list[MatchReportRow] = []
    for state in states:
        isbn = str(state["isbn13"])
        metadata, reason = describe_metadata(state)
        count = candidate_counts[isbn]
        if reason is None and count <= 1:
            reason = "Keine weiteren deutschen oder englischen Ausgaben bekannt"
        match = match_wishlist_book(isbn, client)["match"] if client is not None else None
        rows.append(
            {
                "isbn13": isbn,
                "title": state["ol_title"] or state["gb_title"] or _title_from_reado_url(state["reado_url"]),
                "metadata": metadata,
                "reason": reason,
                "candidate_count": count,
                "catalog_checked": client is not None,
                "match": match,
            }
        )
    return rows
