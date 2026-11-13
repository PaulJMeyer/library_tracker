from __future__ import annotations

from library_tracker.clients.library import LibraryClient
from library_tracker.database import get_connection, initialize_database
from library_tracker.models import LibraryMatchAttempt, LibraryMatchResult
from library_tracker.repositories.matching import get_wishlist_isbn_candidates


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
