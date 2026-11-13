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
        "isbn13": "9783423449229",
        "reado_url": "https://reado.app/de/book/a/9783423449229",
    }
    result = sync_reado_list(connection, [entry], "wishlist", "t1")
    sync_reado_list(connection, [entry], "tbr", "t2")
    removed = sync_reado_list(connection, [], "wishlist", "t3")

    assert len(result["new_entries"]) == 1
    assert removed["removed_isbns"] == ["9783423449229"]
    assert connection.execute(
        "SELECT is_active FROM reado_list_memberships WHERE isbn13=? AND list_type='tbr'",
        (entry["isbn13"],),
    ).fetchone() == (1,)


def test_metadata_resolution_queries(connection: sqlite3.Connection) -> None:
    insert_reado_book(connection)
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
