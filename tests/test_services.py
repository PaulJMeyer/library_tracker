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
