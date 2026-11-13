from __future__ import annotations

import sqlite3

from library_tracker.models import LibraryIsbnCandidate, LibraryIsbnCandidateSource


def get_wishlist_isbn_candidates(
    connection: sqlite3.Connection,
    reado_isbn: str,
) -> list[LibraryIsbnCandidate]:
    active = connection.execute(
        """
        SELECT 1
        FROM reado_list_memberships
        WHERE isbn13 = ? AND list_type = 'wishlist' AND is_active = 1
        """,
        (reado_isbn,),
    ).fetchone()
    if active is None:
        return []

    candidates: list[LibraryIsbnCandidate] = [
        {"isbn": reado_isbn, "source": "reado"}
    ]
    seen = {reado_isbn}
    rows = connection.execute(
        """
        SELECT DISTINCT oei.isbn, oe.print_status
        FROM bibliographic_resolutions br
        JOIN openlibrary_editions oe ON oe.work_key = br.work_key
        JOIN openlibrary_edition_languages oel ON oel.edition_key = oe.edition_key
        JOIN openlibrary_edition_isbns oei ON oei.edition_key = oe.edition_key
        WHERE br.isbn13 = ?
          AND br.source = 'openlibrary'
          AND br.status = 'resolved'
          AND oel.language = 'de'
          AND UPPER(oei.isbn_type) = 'ISBN_13'
        ORDER BY CASE oe.print_status WHEN 'confirmed' THEN 0 ELSE 1 END, oei.isbn
        """,
        (reado_isbn,),
    ).fetchall()

    for isbn, print_status in rows:
        isbn = str(isbn)
        if isbn in seen:
            continue
        source: LibraryIsbnCandidateSource = (
            "openlibrary_confirmed" if print_status == "confirmed" else "openlibrary_unknown"
        )
        candidates.append({"isbn": isbn, "source": source})
        seen.add(isbn)

    return candidates
