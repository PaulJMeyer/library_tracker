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
        SELECT oei.isbn, oel.language, oe.print_status
        FROM bibliographic_resolutions br
        JOIN openlibrary_editions oe ON oe.work_key = br.work_key
        JOIN openlibrary_edition_languages oel ON oel.edition_key = oe.edition_key
        JOIN openlibrary_edition_isbns oei ON oei.edition_key = oe.edition_key
        WHERE br.isbn13 = ?
          AND br.source IN ('openlibrary', 'openlibrary_title')
          AND br.status = 'resolved'
          AND UPPER(oei.isbn_type) = 'ISBN_13'
        ORDER BY
            CASE oel.language WHEN 'de' THEN 0 ELSE 1 END,
            CASE oe.print_status WHEN 'confirmed' THEN 0 ELSE 1 END,
            oei.isbn
        """,
        (reado_isbn,),
    ).fetchall()

    buckets: dict[LibraryIsbnCandidateSource, list[str]] = {
        "openlibrary_confirmed": [],
        "dnb": [],
        "openlibrary_unknown": [],
        "openlibrary_english": [],
    }
    for isbn, language, print_status in rows:
        source: LibraryIsbnCandidateSource
        if language != "de":
            source = "openlibrary_english"
        elif print_status == "confirmed":
            source = "openlibrary_confirmed"
        else:
            source = "openlibrary_unknown"
        buckets[source].append(str(isbn))

    buckets["dnb"] = [
        str(row[0])
        for row in connection.execute(
            "SELECT edition_isbn FROM dnb_editions WHERE isbn13 = ? ORDER BY edition_isbn",
            (reado_isbn,),
        )
    ]

    # Priority: confirmed German print (Open Library), German print (DNB),
    # German with unknown format, English.
    for source, isbns in buckets.items():
        for isbn in isbns:
            if isbn not in seen:
                candidates.append({"isbn": isbn, "source": source})
                seen.add(isbn)

    return candidates


def get_wishlist_metadata_states(
    connection: sqlite3.Connection,
) -> list[dict[str, str | None]]:
    """One row per active READO wishlist book with its metadata resolution state."""
    cursor = connection.execute(
        """
        SELECT
            rb.isbn13,
            rb.reado_url,
            br.status AS ol_status,
            br.source AS ol_source,
            ow.title AS ol_title,
            CASE WHEN oes.work_key IS NULL THEN NULL ELSE 'synced' END AS editions,
            gbr.status AS gb_status,
            gbv.title AS gb_title,
            CASE WHEN otl.isbn13 IS NULL THEN NULL ELSE 'searched' END AS title_link,
            dl.status AS dnb_status,
            dl.title AS dnb_title
        FROM reado_list_memberships AS rlm
        JOIN reado_books AS rb ON rb.isbn13 = rlm.isbn13
        LEFT JOIN bibliographic_resolutions AS br ON br.isbn13 = rb.isbn13
        LEFT JOIN openlibrary_works AS ow ON ow.work_key = br.work_key
        LEFT JOIN openlibrary_edition_syncs AS oes ON oes.work_key = br.work_key
        LEFT JOIN google_books_resolutions AS gbr ON gbr.isbn13 = rb.isbn13
        LEFT JOIN google_books_volumes AS gbv ON gbv.volume_id = gbr.volume_id
        LEFT JOIN openlibrary_title_links AS otl ON otl.isbn13 = rb.isbn13
        LEFT JOIN dnb_lookups AS dl ON dl.isbn13 = rb.isbn13
        WHERE rlm.list_type = 'wishlist' AND rlm.is_active = 1
        ORDER BY rb.isbn13
        """
    )
    columns = [description[0] for description in cursor.description]
    return [
        {column: (None if value is None else str(value)) for column, value in zip(columns, row)}
        for row in cursor.fetchall()
    ]
