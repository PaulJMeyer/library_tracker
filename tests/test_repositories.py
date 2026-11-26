import datetime
import sqlite3

from library_tracker.models import Copy, Item, ReadoListEntry
from library_tracker.repositories.availability import get_copy_history, get_latest_snapshot, persist_items
from library_tracker.repositories.matching import get_wishlist_isbn_candidates
from library_tracker.repositories.metadata import (
    get_googlebooks_fallback_isbns,
    get_unresolved_reado_isbns,
    get_unsynced_wishlist_work_keys,
    save_googlebooks_resolutions,
    save_openlibrary_editions,
    save_openlibrary_resolutions,
)
from library_tracker.repositories.reado import sync_reado_list


def make_item(status: str = "ausleihbar") -> Item:
    copy: Copy = {
        "media_number": "123",
        "signature": "S Test",
        "branch": "10-Zentralbibliothek",
        "status_text": status,
        "status": "ausleihbar" if status == "ausleihbar" else "entliehen",
        "due_date": None,
        "is_central": True,
    }
    return {"title": "Test", "overall_status": copy["status"], "copies": [copy]}


def insert_reado_book(connection: sqlite3.Connection, isbn: str = "9781111111111") -> None:
    connection.execute(
        "INSERT INTO reado_books VALUES (?, ?, ?, ?)",
        (isbn, "https://reado.app/book", "first", "last"),
    )


def test_availability_persistence_and_history(connection: sqlite3.Connection) -> None:
    first = datetime.datetime(2026, 9, 21, 8, tzinfo=datetime.timezone.utc)
    second = datetime.datetime(2026, 9, 22, 8, tzinfo=datetime.timezone.utc)
    persist_items(connection, [make_item("entliehen")], checked_at=first)
    persist_items(connection, [make_item("ausleihbar")], checked_at=second)

    history = get_copy_history(connection, "123")
    assert [snapshot["status"] for snapshot in history] == ["entliehen", "ausleihbar"]
    assert get_latest_snapshot(connection, "123") == history[-1]
    assert get_latest_snapshot(connection, "unknown") is None


def test_sync_reado_list_keeps_other_lists(connection: sqlite3.Connection) -> None:
    entry: ReadoListEntry = {
        "isbn13": "9780000000106",
        "reado_url": "https://reado.app/de/book/a/9780000000106",
    }
    result = sync_reado_list(connection, [entry], "wishlist", "t1")
    sync_reado_list(connection, [entry], "tbr", "t2")
    removed = sync_reado_list(connection, [], "wishlist", "t3")

    assert len(result["new_entries"]) == 1
    assert removed["removed_isbns"] == ["9780000000106"]
    assert connection.execute(
        "SELECT is_active FROM reado_list_memberships WHERE isbn13=? AND list_type='tbr'",
        (entry["isbn13"],),
    ).fetchone() == (1,)


def test_metadata_resolution_queries(connection: sqlite3.Connection) -> None:
    insert_reado_book(connection)
    connection.execute(
        "INSERT INTO reado_list_memberships VALUES ('9781111111111', 'completed', 'f', 'l', 1)"
    )
    # Only wishlist books need metadata.
    assert get_unresolved_reado_isbns(connection) == []
    connection.execute(
        "INSERT INTO reado_list_memberships VALUES ('9781111111111', 'wishlist', 'f', 'l', 1)"
    )
    assert get_unresolved_reado_isbns(connection) == ["9781111111111"]

    save_openlibrary_resolutions(
        connection,
        [{
            "isbn13": "9781111111111",
            "status": "not_found",
            "work_key": None,
            "title": None,
            "error_message": None,
        }],
        "now",
    )
    assert get_unresolved_reado_isbns(connection) == []
    assert get_googlebooks_fallback_isbns(connection) == ["9781111111111"]

    save_googlebooks_resolutions(
        connection,
        [{
            "isbn13": "9781111111111",
            "status": "not_found",
            "volume_id": None,
            "title": None,
            "authors": [],
            "language": None,
            "publisher": None,
            "published_date": None,
            "identifiers": [],
            "error_message": None,
        }],
        "now",
    )
    assert get_googlebooks_fallback_isbns(connection) == []


def test_editions_and_matching_candidates(connection: sqlite3.Connection) -> None:
    insert_reado_book(connection)
    connection.execute(
        "INSERT INTO reado_list_memberships VALUES (?, 'wishlist', 'first', 'last', 1)",
        ("9781111111111",),
    )
    save_openlibrary_resolutions(
        connection,
        [{
            "isbn13": "9781111111111",
            "status": "resolved",
            "work_key": "OL123W",
            "title": "Test Book",
            "error_message": None,
        }],
        "now",
    )
    assert get_unsynced_wishlist_work_keys(connection) == ["OL123W"]

    save_openlibrary_editions(
        connection,
        "OL123W",
        [
            {
                "edition_key": "OL1M",
                "work_key": "OL123W",
                "title": "Test Book",
                "languages": ["de"],
                "physical_format": "Paperback",
                "print_status": "confirmed",
                "identifiers": [{"type": "ISBN_13", "identifier": "9782222222222"}],
            },
            {
                "edition_key": "OL2M",
                "work_key": "OL123W",
                "title": "Test Book",
                "languages": ["de"],
                "physical_format": None,
                "print_status": "unknown",
                "identifiers": [{"type": "ISBN_13", "identifier": "9783333333333"}],
            },
        ],
        "now",
    )
    assert get_unsynced_wishlist_work_keys(connection) == []
    assert get_wishlist_isbn_candidates(connection, "9781111111111") == [
        {"isbn": "9781111111111", "source": "reado"},
        {"isbn": "9782222222222", "source": "openlibrary_confirmed"},
        {"isbn": "9783333333333", "source": "openlibrary_unknown"},
    ]


def _resolve(connection: sqlite3.Connection, isbn: str, status: str, work_key: str | None) -> None:
    save_openlibrary_resolutions(
        connection,
        [{
            "isbn13": isbn,
            "status": status,  # type: ignore[typeddict-item]
            "work_key": work_key,
            "title": "Test Book" if work_key else None,
            "error_message": None,
        }],
        "now",
    )


def test_matching_candidates_put_english_editions_last(connection: sqlite3.Connection) -> None:
    insert_reado_book(connection)
    connection.execute(
        "INSERT INTO reado_list_memberships VALUES (?, 'wishlist', 'first', 'last', 1)",
        ("9781111111111",),
    )
    _resolve(connection, "9781111111111", "resolved", "OL123W")
    save_openlibrary_editions(
        connection,
        "OL123W",
        [
            {
                "edition_key": "OL1M",
                "work_key": "OL123W",
                "title": "Test Book",
                "languages": ["en"],
                "physical_format": "Paperback",
                "print_status": "confirmed",
                "identifiers": [{"type": "ISBN_13", "identifier": "9780000000001"}],
            },
            {
                "edition_key": "OL2M",
                "work_key": "OL123W",
                "title": "Test Buch",
                "languages": ["de"],
                "physical_format": None,
                "print_status": "unknown",
                "identifiers": [{"type": "ISBN_13", "identifier": "9783333333333"}],
            },
        ],
        "now",
    )

    assert get_wishlist_isbn_candidates(connection, "9781111111111") == [
        {"isbn": "9781111111111", "source": "reado"},
        {"isbn": "9783333333333", "source": "openlibrary_unknown"},
        {"isbn": "9780000000001", "source": "openlibrary_english"},
    ]
    assert get_unsynced_wishlist_work_keys(connection) == []
    assert get_unsynced_wishlist_work_keys(connection, include_synced=True) == ["OL123W"]


def test_title_links_resolve_google_books_only_isbns(connection: sqlite3.Connection) -> None:
    from library_tracker.repositories.metadata import get_title_link_candidates, save_title_link

    insert_reado_book(connection)
    connection.execute(
        "INSERT INTO reado_list_memberships VALUES (?, 'wishlist', 'first', 'last', 1)",
        ("9781111111111",),
    )
    _resolve(connection, "9781111111111", "not_found", None)
    save_googlebooks_resolutions(
        connection,
        [{
            "isbn13": "9781111111111",
            "status": "found",
            "volume_id": "vol1",
            "title": "Example Book",
            "authors": ["Jane Doe"],
            "language": "en",
            "publisher": None,
            "published_date": None,
            "identifiers": [],
            "error_message": None,
        }],
        "now",
    )
    assert get_title_link_candidates(connection) == [
        ("9781111111111", "Example Book", ["Jane Doe"])
    ]

    save_title_link(connection, "9781111111111", ("OL9W", "Example Book"), "later")

    assert get_title_link_candidates(connection) == []
    assert get_unsynced_wishlist_work_keys(connection) == ["OL9W"]
    assert get_googlebooks_fallback_isbns(connection) == []


def test_failed_title_link_is_not_retried(connection: sqlite3.Connection) -> None:
    from library_tracker.repositories.metadata import get_title_link_candidates, save_title_link

    insert_reado_book(connection)
    _resolve(connection, "9781111111111", "not_found", None)
    save_googlebooks_resolutions(
        connection,
        [{
            "isbn13": "9781111111111",
            "status": "found",
            "volume_id": "vol1",
            "title": "Example Book",
            "authors": [],
            "language": None,
            "publisher": None,
            "published_date": None,
            "identifiers": [],
            "error_message": None,
        }],
        "now",
    )
    save_title_link(connection, "9781111111111", None, "later")
    assert get_title_link_candidates(connection) == []


def test_dnb_editions_become_candidates_after_confirmed_openlibrary(
    connection: sqlite3.Connection,
) -> None:
    from library_tracker.repositories.metadata import get_dnb_lookup_candidates, save_dnb_lookup

    insert_reado_book(connection)
    connection.execute(
        "INSERT INTO reado_list_memberships VALUES (?, 'wishlist', 'first', 'last', 1)",
        ("9781111111111",),
    )
    assert get_dnb_lookup_candidates(connection) == [("9781111111111", None, [])]

    _resolve(connection, "9781111111111", "resolved", "OL123W")
    save_openlibrary_editions(
        connection,
        "OL123W",
        [
            {
                "edition_key": "OL1M",
                "work_key": "OL123W",
                "title": "Test Buch",
                "languages": ["de"],
                "physical_format": "Paperback",
                "print_status": "confirmed",
                "identifiers": [{"type": "ISBN_13", "identifier": "9783000000001"}],
            },
            {
                "edition_key": "OL2M",
                "work_key": "OL123W",
                "title": "Test Buch",
                "languages": ["de"],
                "physical_format": None,
                "print_status": "unknown",
                "identifiers": [{"type": "ISBN_13", "identifier": "9783000000002"}],
            },
        ],
        "now",
    )
    save_dnb_lookup(
        connection,
        "9781111111111",
        title="Test Buch",
        authors=["Muster, Erika"],
        editions=[("9783000000009", "Test Buch"), ("9783000000001", "Test Buch")],
        found=True,
        searched_at="now",
    )

    assert get_dnb_lookup_candidates(connection) == []
    assert get_wishlist_isbn_candidates(connection, "9781111111111") == [
        {"isbn": "9781111111111", "source": "reado"},
        {"isbn": "9783000000001", "source": "openlibrary_confirmed"},
        {"isbn": "9783000000009", "source": "dnb"},
        {"isbn": "9783000000002", "source": "openlibrary_unknown"},
    ]
