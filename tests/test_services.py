import sqlite3
from unittest.mock import Mock, patch

from library_tracker.clients.library import LibraryClient
from library_tracker.models import Item, MemorizePage
from library_tracker.services.library_matching import match_wishlist_book, search_catalog
from library_tracker.services.library_scrape import scrape_library


def test_library_scrape_orchestrates_client_and_persistence() -> None:
    client = Mock(spec=LibraryClient)
    page: MemorizePage = {
        "cur_pos": "1",
        "cs_id": "csid",
        "display_type": "short",
        "selected_memorize_list": "",
        "entries": [
            {"uuid": "loaned", "availability_link": "a"},
            {"uuid": "available", "availability_link": "b"},
        ],
    }
    client.get_all_memorize_pages.return_value = [page]
    client.get_availability_pages.side_effect = [
        ("loaned-details", "loaned-html"),
        ("<p>Umfang: 320 S.</p>", "available-html"),
    ]
    client.remove_entries.return_value = True
    client.get_account_page.return_value = "account-html"

    loaned: Item = {"title": "Loaned", "overall_status": "entliehen", "copies": []}
    available: Item = {"title": "Available", "overall_status": "ausleihbar", "copies": []}
    connection = Mock(spec=sqlite3.Connection)

    with (
        patch(
            "library_tracker.services.library_scrape.parse_availability_page",
            side_effect=[loaned, available],
        ),
        patch("library_tracker.services.library_scrape.parse_loans", return_value=[]),
        patch("library_tracker.services.library_scrape.get_connection", return_value=connection),
        patch("library_tracker.services.library_scrape.initialize_database"),
        patch("library_tracker.services.library_scrape.persist_items") as persist,
    ):
        result = scrape_library(client)

    assert result["total_entries"] == 2
    assert result["all_titles"] == ["Loaned", "Available"]
    assert [entry["title"] for entry in result["entries"]] == ["Loaned", "Available"]
    assert [item["title"] for item in result["items"]] == ["Available"]
    assert result["items"][0]["pages"] == 320
    client.remove_entries.assert_not_called()
    persist.assert_called_once_with(connection, [loaned, available])
    connection.close.assert_called_once_with()


def test_library_matching_stops_at_first_hit() -> None:
    client = Mock(spec=LibraryClient)
    client.search_catalog_by_isbn.side_effect = [[], ["hit"]]
    connection = Mock(spec=sqlite3.Connection)

    candidates = [
        {"isbn": "1", "source": "reado"},
        {"isbn": "2", "source": "openlibrary_confirmed"},
        {"isbn": "3", "source": "openlibrary_unknown"},
    ]
    with (
        patch("library_tracker.services.library_matching.get_connection", return_value=connection),
        patch("library_tracker.services.library_matching.initialize_database"),
        patch(
            "library_tracker.services.library_matching.get_wishlist_isbn_candidates",
            return_value=candidates,
        ),
    ):
        result = match_wishlist_book("1", client)

    assert result["match"] == candidates[1]
    assert [attempt["isbn"] for attempt in result["attempts"]] == ["1", "2"]
    assert client.search_catalog_by_isbn.call_count == 2


def test_search_catalog_uses_supplied_client() -> None:
    client = Mock(spec=LibraryClient)
    client.search_catalog_by_isbn.return_value = ["hit"]
    assert search_catalog("123", client) == ["hit"]


def _state(**overrides: str | None) -> dict[str, str | None]:
    state: dict[str, str | None] = {
        "isbn13": "9781111111111",
        "reado_url": "https://reado.app/de/book/example-book/9781111111111",
        "ol_status": None,
        "ol_source": None,
        "ol_title": None,
        "editions": None,
        "gb_status": None,
        "gb_title": None,
        "title_link": None,
        "dnb_status": "not_found",
        "dnb_title": None,
    }
    state.update(overrides)
    return state


def test_describe_metadata_explains_missing_steps() -> None:
    from library_tracker.services.library_matching import describe_metadata

    assert describe_metadata(_state())[0] == "nicht abgefragt"
    assert describe_metadata(_state(ol_status="resolved", ol_source="openlibrary", editions="synced")) == (
        "Open Library",
        None,
    )
    assert "openlibrary-editions" in str(
        describe_metadata(_state(ol_status="resolved", ol_source="openlibrary"))[1]
    )
    assert describe_metadata(_state(ol_status="not_found", gb_status="not_found"))[1] == (
        "Weder Open Library, Google Books noch DNB kennen die ISBN"
    )
    assert describe_metadata(
        _state(ol_status="not_found", gb_status="not_found", dnb_status=None)
    )[1] == "DNB-Abfrage ausstehend (dnb-editions)"
    assert describe_metadata(
        _state(ol_status="not_found", gb_status="not_found", dnb_status="found")
    ) == ("DNB", None)
    assert "openlibrary-link-titles" in str(
        describe_metadata(_state(ol_status="not_found", gb_status="found"))[1]
    )


def test_limit_candidates_caps_german_and_english() -> None:
    from library_tracker.services.library_matching import limit_candidates

    candidates = (
        [{"isbn": "r", "source": "reado"}]
        + [{"isbn": f"de{i}", "source": "openlibrary_unknown"} for i in range(20)]
        + [{"isbn": f"en{i}", "source": "openlibrary_english"} for i in range(10)]
    )
    limited = limit_candidates(candidates)  # type: ignore[arg-type]

    assert len(limited) == 15
    assert limited[0]["isbn"] == "r"
    assert [c["isbn"] for c in limited[-3:]] == ["en0", "en1", "en2"]


def test_lookup_dnb_editions_combines_isbn_and_title_search(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from library_tracker.clients.dnb import DnbClient, DnbError, DnbRecord
    from library_tracker.database import get_connection, initialize_database
    from library_tracker.services.metadata import lookup_dnb_editions

    db_path = tmp_path / "db.sqlite"
    connection = get_connection(db_path)
    initialize_database(connection)
    for isbn in ("9781111111111", "9782222222222", "9783333333333"):
        connection.execute("INSERT INTO reado_books VALUES (?, 'url', 'f', 'l')", (isbn,))
        connection.execute(
            "INSERT INTO reado_list_memberships VALUES (?, 'wishlist', 'f', 'l', 1)", (isbn,)
        )
    connection.commit()
    connection.close()

    client = Mock(spec=DnbClient)
    client.lookup_isbn.side_effect = [
        DnbRecord("Beispielroman", ["Muster, Erika"], ["ger"], ["9781111111111"]),
        None,
        DnbError("down"),
    ]
    client.find_german_print_editions.return_value = [
        DnbRecord("Beispielroman", ["Muster, Erika"], ["ger"], ["9783499626029"])
    ]

    with patch(
        "library_tracker.services.metadata.get_connection",
        side_effect=lambda: get_connection(db_path),
    ):
        results, failed = lookup_dnb_editions(client)

    assert results == [("9781111111111", True, 1), ("9782222222222", False, 0)]
    assert failed == ["9783333333333"]
    client.find_german_print_editions.assert_called_once_with("Beispielroman", ["Muster, Erika"])


def test_run_sync_continues_after_failed_steps() -> None:
    from library_tracker.clients.dnb import DnbError
    from library_tracker.clients.reado import ReadoError
    from library_tracker.services import sync

    def fake_sync_lists(*, headless: bool, list_types: tuple[str, ...]) -> None:
        if list_types == ("abandoned",):
            raise ReadoError("No book links appeared on the READO list.")

    scrape_result = {
        "total_entries": 2,
        "items": [],
        "loans": [],
        "all_titles": ["Old", "Finished"],
        "entries": [],
    }
    client = Mock(spec=LibraryClient)
    with (
        patch.object(sync, "configured_reado_list_types", return_value=("wishlist", "abandoned")),
        patch.object(sync, "sync_lists", side_effect=fake_sync_lists) as reado,
        patch.object(sync, "resolve_openlibrary"),
        patch.object(sync, "resolve_googlebooks"),
        patch.object(sync, "link_googlebooks_titles"),
        patch.object(sync, "sync_openlibrary_editions"),
        patch.object(sync, "lookup_dnb_editions", side_effect=DnbError("down")),
        patch.object(
            sync,
            "match_wishlist_books",
            return_value={"books": 1, "searched": 1, "new_matches": 1, "errors": 0},
        ),
        patch.object(sync, "scrape_library", return_value=scrape_result) as scrape,
        patch.object(
            sync,
            "remove_finished_from_merkliste",
            return_value=[("2", "Finished", "removed")],
        ) as remove,
        patch.object(
            sync, "add_matches_to_merkliste", return_value=[("1", "New", "added")]
        ) as add,
        patch.object(sync, "_log"),
    ):
        report = sync.run_sync(client=client, fresh_login=lambda: client, log=lambda _: None)

    # The failing READO list does not stop the wishlist from being synced.
    assert [call.kwargs["list_types"] for call in reado.call_args_list] == [("wishlist",), ("abandoned",)]
    assert report.warnings == ["READO-Liste Abgebrochen fehlgeschlagen", "DNB fehlgeschlagen"]
    assert report.added_titles == ["New"]
    assert report.removed_titles == ["Finished"]
    remove.assert_called_once_with([], client)
    add.assert_called_once_with(["Old"], client)
    assert scrape.call_count == 2  # one re-read after removing and adding


def test_configured_reado_list_types(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from library_tracker.config import configured_reado_list_types

    for name in (
        "READO_SECOND_WISHLIST_URL",
        "READO_TBR_URL",
        "READO_READING_URL",
        "READO_COMPLETED_URL",
        "READO_ABANDONED_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("READO_READING_URL", "https://reado.app/x")

    assert configured_reado_list_types() == ("wishlist", "reading")

    monkeypatch.setenv("READO_SECOND_WISHLIST_URL", "https://reado.app/y")
    assert configured_reado_list_types() == ("wishlist", "second_wishlist", "reading")


def test_second_wishlist_heading(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from library_tracker.config import second_wishlist_heading

    monkeypatch.delenv("READO_SECOND_WISHLIST_NAME", raising=False)
    assert second_wishlist_heading() == "Von der zweiten Wunschliste:"
    monkeypatch.setenv("READO_SECOND_WISHLIST_NAME", "Anna")
    assert second_wishlist_heading() == "Von Annas Wunschliste:"
    monkeypatch.setenv("READO_SECOND_WISHLIST_NAME", " Hans ")
    assert second_wishlist_heading() == "Von Hans' Wunschliste:"


def test_run_sync_assigns_second_wishlist_titles() -> None:
    from library_tracker.services import sync

    scrape_result = {"total_entries": 1, "items": [], "loans": [], "all_titles": ["A"], "entries": []}
    client = Mock(spec=LibraryClient)
    with (
        patch.object(
            sync, "configured_reado_list_types", return_value=("wishlist", "second_wishlist")
        ),
        patch.object(sync, "sync_lists") as reado,
        patch.object(sync, "resolve_openlibrary"),
        patch.object(sync, "resolve_googlebooks"),
        patch.object(sync, "link_googlebooks_titles"),
        patch.object(sync, "sync_openlibrary_editions"),
        patch.object(sync, "lookup_dnb_editions"),
        patch.object(sync, "match_wishlist_books", return_value=None),
        patch.object(sync, "scrape_library", return_value=scrape_result),
        patch.object(sync, "remove_finished_from_merkliste", return_value=[]),
        patch.object(sync, "add_matches_to_merkliste", return_value=[]),
        patch.object(sync, "_second_wishlist_titles", return_value=["A"]),
        patch.object(sync, "_log"),
    ):
        report = sync.run_sync(client=client, log=lambda _: None)

    assert [call.kwargs["list_types"] for call in reado.call_args_list] == [
        ("wishlist",),
        ("second_wishlist",),
    ]
    assert report.second_wishlist_titles == ["A"]
    assert report.warnings == []


def test_run_sync_keeps_first_read_when_reread_is_incomplete() -> None:
    from library_tracker.services import sync

    full = {"total_entries": 30, "items": [], "loans": [], "all_titles": ["Old"], "entries": []}
    partial = {"total_entries": 10, "items": [], "loans": [], "all_titles": ["New"], "entries": []}
    client = Mock(spec=LibraryClient)
    fresh = Mock(spec=LibraryClient)
    with (
        patch.object(sync, "configured_reado_list_types", return_value=("wishlist",)),
        patch.object(sync, "sync_lists"),
        patch.object(sync, "resolve_openlibrary"),
        patch.object(sync, "resolve_googlebooks"),
        patch.object(sync, "link_googlebooks_titles"),
        patch.object(sync, "sync_openlibrary_editions"),
        patch.object(sync, "lookup_dnb_editions"),
        patch.object(
            sync,
            "match_wishlist_books",
            return_value={"books": 1, "searched": 1, "new_matches": 1, "errors": 0},
        ),
        patch.object(sync, "scrape_library", side_effect=[full, partial]) as scrape,
        patch.object(sync, "remove_finished_from_merkliste", return_value=[]),
        patch.object(sync, "add_matches_to_merkliste", return_value=[("1", "New", "added")]),
        patch.object(sync, "_log"),
    ):
        report = sync.run_sync(client=client, fresh_login=lambda: fresh, log=lambda _: None)

    assert scrape.call_args_list[1].args == (fresh,)  # re-read in a new session
    assert report.scrape is full
    assert report.warnings == ["Merkliste nach dem Ergänzen unvollständig gelesen"]
