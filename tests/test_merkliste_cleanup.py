from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from library_tracker.clients.library import LibraryClient, LibraryClientError
from library_tracker.database import get_connection, initialize_database
from library_tracker.models import MemorizePage, MerklisteEntry
from library_tracker.repositories.library_matches import save_library_match, save_memorize_result

BASE = "https://opac.stabi-hb.de/webOPACClient/singleHit.do"
PAGE: MemorizePage = {
    "cur_pos": "1",
    "cs_id": "cs",
    "display_type": "d",
    "selected_memorize_list": "m",
    "entries": [],
}
SINGLE_HIT = '<h2>¬Der Fremde</h2><a href="memorizeHitList.do?methodToCall=addToMemorizeList">x</a>'


def _entry(title: str, uuid: str) -> MerklisteEntry:
    return {"title": title, "uuid": uuid, "page": PAGE}


def _add_book(connection, isbn: str, *lists: str) -> None:  # type: ignore[no-untyped-def]
    connection.execute("INSERT INTO reado_books VALUES (?, 'url', 'f', 'l')", (isbn,))
    for list_type in lists:
        connection.execute(
            "INSERT INTO reado_list_memberships VALUES (?, ?, 'f', 'l', 1)", (isbn, list_type)
        )
    connection.commit()


@pytest.fixture
def db(tmp_path: Path):  # type: ignore[no-untyped-def]
    path = tmp_path / "db.sqlite"
    connection = get_connection(path)
    initialize_database(connection)
    _add_book(connection, "9781111111111", "completed")  # auto-added earlier
    save_library_match(connection, "9781111111111", "9783000000001", "dnb", "now")
    save_memorize_result(connection, "9781111111111", "added", "Babel", "now")
    _add_book(connection, "9782222222222", "abandoned")  # added by hand, no stored title
    _add_book(connection, "9783333333333", "wishlist")  # still wanted
    _add_book(connection, "9784444444444", "reading")  # not on the Merkliste
    save_library_match(connection, "9784444444444", "9784444444444", "reado", "now")
    save_memorize_result(connection, "9784444444444", "added", "Anderes Buch", "now")
    connection.close()
    with patch(
        "library_tracker.database.get_connection",
        side_effect=lambda: get_connection(path),
    ):
        yield path


def test_removes_finished_books_once(db: Path) -> None:
    from library_tracker.services.merkliste_cleanup import remove_finished_from_merkliste

    client = Mock(spec=LibraryClient)
    client.search_catalog_by_isbn.return_value = ["https://opac/hit"]
    client.get_page.return_value = (SINGLE_HIT, BASE)
    client.remove_entries.return_value = True
    entries = [_entry("Babel", "u1"), _entry("Der Fremde", "u2"), _entry("Wunschbuch", "u3")]

    results = remove_finished_from_merkliste(entries, client, progress=lambda _: None)

    assert results == [
        ("9781111111111", "Babel", "removed"),
        ("9782222222222", "Der Fremde", "removed"),
        ("9784444444444", "Anderes Buch", "not_on_merkliste"),
    ]
    # Stored title used for the auto-added book; one catalog lookup for the other.
    client.search_catalog_by_isbn.assert_called_once_with("9782222222222")
    assert [call.args[1] for call in client.remove_entries.call_args_list] == [["u1"], ["u2"]]
    # Checked books are not looked at again.
    assert remove_finished_from_merkliste(entries, client, progress=lambda _: None) == []


def test_failed_removal_is_retried_and_lookups_are_limited(db: Path) -> None:
    from library_tracker.services.merkliste_cleanup import remove_finished_from_merkliste

    client = Mock(spec=LibraryClient)
    client.remove_entries.side_effect = LibraryClientError("down")
    entries = [_entry("Babel", "u1")]

    first = remove_finished_from_merkliste(entries, client, lookup_limit=0, progress=lambda _: None)
    assert first == [
        ("9781111111111", "Babel", "failed"),
        ("9784444444444", "Anderes Buch", "not_on_merkliste"),
    ]
    client.search_catalog_by_isbn.assert_not_called()

    client.remove_entries.side_effect = None
    client.remove_entries.return_value = True
    second = remove_finished_from_merkliste(entries, client, lookup_limit=0, progress=lambda _: None)
    assert second == [("9781111111111", "Babel", "removed")]


def test_book_back_on_wishlist_can_be_removed_again(db: Path) -> None:
    from library_tracker.services.merkliste_cleanup import remove_finished_from_merkliste

    client = Mock(spec=LibraryClient)
    client.remove_entries.return_value = True
    remove_finished_from_merkliste([_entry("Babel", "u1")], client, lookup_limit=0, progress=lambda _: None)

    connection = get_connection(db)
    connection.execute("INSERT INTO reado_list_memberships VALUES ('9781111111111', 'wishlist', 'f', 'l', 1)")
    connection.commit()
    # On the wishlist again: not touched, and its old removal is forgotten.
    assert remove_finished_from_merkliste([_entry("Babel", "u9")], client, lookup_limit=0, progress=lambda _: None) == []
    connection.execute("UPDATE reado_list_memberships SET is_active = 0 WHERE list_type = 'wishlist'")
    connection.commit()
    connection.close()

    results = remove_finished_from_merkliste([_entry("Babel", "u9")], client, lookup_limit=0, progress=lambda _: None)
    assert results == [("9781111111111", "Babel", "removed")]


def test_book_back_on_wishlist_is_put_on_the_merkliste_again(db: Path) -> None:
    from library_tracker.repositories.library_matches import (
        get_editions_to_memorize,
        save_catalog_edition,
        save_edition_memorize_result,
    )
    from library_tracker.services.merkliste_cleanup import remove_finished_from_merkliste

    connection = get_connection(db)
    save_catalog_edition(connection, "9781111111111", "9783000000001", "dnb", "now")
    save_edition_memorize_result(connection, "9781111111111", "9783000000001", "added", "Babel", [], "now")
    connection.close()
    client = Mock(spec=LibraryClient)
    client.remove_entries.return_value = True
    remove_finished_from_merkliste([_entry("Babel", "u1")], client, lookup_limit=0, progress=lambda _: None)

    connection = get_connection(db)
    connection.execute("INSERT INTO reado_list_memberships VALUES ('9781111111111', 'second_wishlist', 'f', 'l', 1)")
    connection.commit()
    remove_finished_from_merkliste([], client, lookup_limit=0, progress=lambda _: None)

    # The Merkliste step adds the removed edition again.
    assert get_editions_to_memorize(connection) == [("9781111111111", "9783000000001")]
    connection.close()


def test_keeps_entries_of_a_wishlist_book_with_the_same_title(db: Path) -> None:
    """Another edition of a finished book can still be on a wishlist (e.g. the second one)."""
    from library_tracker.repositories.library_matches import (
        save_catalog_edition,
        save_edition_memorize_result,
    )
    from library_tracker.services.merkliste_cleanup import remove_finished_from_merkliste

    connection = get_connection(db)
    _add_book(connection, "9785555555555", "second_wishlist")
    save_catalog_edition(connection, "9785555555555", "9783000000009", "dnb", "now")
    save_edition_memorize_result(connection, "9785555555555", "9783000000009", "added", "Babel", ["M9"], "now")
    connection.close()
    client = Mock(spec=LibraryClient)
    client.remove_entries.return_value = True
    entries: list[MerklisteEntry] = [{"title": "Babel", "uuid": "u1", "page": PAGE, "media_numbers": ["M9"]}]

    results = remove_finished_from_merkliste(entries, client, lookup_limit=0, progress=lambda _: None)

    assert ("9781111111111", "Babel", "not_on_merkliste") in results
    client.remove_entries.assert_not_called()


def test_removes_every_edition_of_a_finished_book(db: Path) -> None:
    from library_tracker.repositories.library_matches import (
        save_catalog_edition,
        save_edition_memorize_result,
    )
    from library_tracker.services.merkliste_cleanup import remove_finished_from_merkliste

    connection = get_connection(db)
    save_catalog_edition(connection, "9781111111111", "9783000000002", "dnb", "now")
    save_edition_memorize_result(
        connection, "9781111111111", "9783000000002", "added", "Babel (Taschenbuch)", ["M7"], "now"
    )
    connection.close()

    client = Mock(spec=LibraryClient)
    client.remove_entries.return_value = True
    entries: list[MerklisteEntry] = [
        _entry("Babel", "u1"),
        {"title": "Babel - Roman", "uuid": "u2", "page": PAGE, "media_numbers": ["M7", "M8"]},
        _entry("Wunschbuch", "u3"),
    ]

    results = remove_finished_from_merkliste(entries, client, lookup_limit=0, progress=lambda _: None)

    assert results[:2] == [
        ("9781111111111", "Babel", "removed"),
        ("9781111111111", "Babel - Roman", "removed"),
    ]
    assert [call.args[1] for call in client.remove_entries.call_args_list] == [["u1"], ["u2"]]


def test_removes_ebook_entries() -> None:
    from library_tracker.services.merkliste_cleanup import remove_ebooks_from_merkliste

    client = Mock(spec=LibraryClient)
    client.remove_entries.return_value = True
    ebook: MerklisteEntry = {"title": "Ein E-Book", "uuid": "u1", "page": PAGE, "ebook": True}

    results = remove_ebooks_from_merkliste([ebook, _entry("Buch", "u2")], client, progress=lambda _: None)

    assert results == [("", "Ein E-Book", "removed")]
    client.remove_entries.assert_called_once_with(PAGE, ["u1"])
