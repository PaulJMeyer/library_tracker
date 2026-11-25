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
    client.get_availability_page.side_effect = ["loaned-html", "available-html"]
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
    assert result["removed_count"] == 1
    assert [item["title"] for item in result["items"]] == ["Available"]
    client.remove_entries.assert_called_once_with(page, ["loaned"])
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
        "Weder Open Library noch Google Books kennen die ISBN"
    )
    assert "openlibrary-link-titles" in str(
        describe_metadata(_state(ol_status="not_found", gb_status="found"))[1]
    )


def test_build_match_report_without_catalog_search() -> None:
    from library_tracker.services.library_matching import build_match_report

    connection = Mock(spec=sqlite3.Connection)
    states = [
        _state(ol_status="resolved", ol_source="openlibrary", ol_title="Example Book", editions="synced"),
        _state(isbn13="9782222222222", reado_url="https://reado.app/de/book/other-book/9782222222222"),
    ]
    with (
        patch("library_tracker.services.library_matching.get_connection", return_value=connection),
        patch("library_tracker.services.library_matching.initialize_database"),
        patch(
            "library_tracker.services.library_matching.get_wishlist_metadata_states",
            return_value=states,
        ),
        patch(
            "library_tracker.services.library_matching.get_wishlist_isbn_candidates",
            return_value=[{"isbn": "x", "source": "reado"}],
        ),
        patch("library_tracker.services.library_matching.LibraryClient") as client_class,
    ):
        rows = build_match_report(search=False)

    client_class.login.assert_not_called()
    assert [row["title"] for row in rows] == ["Example Book", "other book"]
    assert rows[0]["reason"] == "Keine weiteren deutschen oder englischen Ausgaben bekannt"
    assert rows[1]["metadata"] == "nicht abgefragt"
    assert not rows[0]["catalog_checked"]


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


def test_build_match_report_continues_after_catalog_error() -> None:
    from library_tracker.clients.library import LibraryClientError
    from library_tracker.services.library_matching import build_match_report

    connection = Mock(spec=sqlite3.Connection)
    states = [
        _state(ol_status="resolved", ol_source="openlibrary", ol_title="Broken", editions="synced"),
        _state(isbn13="9782222222222", ol_status="resolved", ol_source="openlibrary", ol_title="Works", editions="synced"),
    ]
    client = Mock(spec=LibraryClient)
    with (
        patch("library_tracker.services.library_matching.get_connection", return_value=connection),
        patch("library_tracker.services.library_matching.initialize_database"),
        patch(
            "library_tracker.services.library_matching.get_wishlist_metadata_states",
            return_value=states,
        ),
        patch(
            "library_tracker.services.library_matching.get_wishlist_isbn_candidates",
            return_value=[{"isbn": "x", "source": "reado"}],
        ),
        patch(
            "library_tracker.services.library_matching.match_wishlist_book",
            side_effect=[
                LibraryClientError("Library request failed (Timeout)"),
                {"reado_isbn": "9782222222222", "attempts": [], "match": {"isbn": "x", "source": "reado"}},
            ],
        ),
    ):
        rows = build_match_report(client=client, progress=lambda _: None)

    assert rows[0]["catalog_error"] == "Library request failed (Timeout)"
    assert not rows[0]["catalog_checked"]
    assert rows[1]["match"] == {"isbn": "x", "source": "reado"}
