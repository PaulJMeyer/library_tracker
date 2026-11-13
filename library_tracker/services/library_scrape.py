from __future__ import annotations

from library_tracker.clients.library import LibraryClient
from library_tracker.database import get_connection, initialize_database
from library_tracker.models import Item, ScrapeResult
from library_tracker.parsers.library import parse_availability_page, parse_loans
from library_tracker.repositories.availability import persist_items

STATUS_ORDER = {
    "ausleihbar": 0,
    "bestellbar": 1,
    "entliehen": 2,
    "bestellt": 3,
    "unbekannt": 4,
}


def scrape_library(client: LibraryClient | None = None) -> ScrapeResult:
    client = client or LibraryClient.login()
    pages = client.get_all_memorize_pages()
    total_entries = sum(len(page["entries"]) for page in pages)

    visible_items: list[Item] = []
    scraped_items: list[Item] = []
    removed_count = 0
    removal_success = True

    for page in pages:
        loaned_uuids: list[str] = []
        for entry in page["entries"]:
            item = parse_availability_page(
                client.get_availability_page(entry["availability_link"])
            )
            scraped_items.append(item)
            if item["overall_status"] == "entliehen":
                loaned_uuids.append(entry["uuid"])
            else:
                visible_items.append(item)

        if loaned_uuids:
            removed_count += len(loaned_uuids)
            removal_success = client.remove_entries(page, loaned_uuids) and removal_success

    connection = get_connection()
    try:
        initialize_database(connection)
        persist_items(connection, scraped_items)
    finally:
        connection.close()

    visible_items.sort(key=lambda item: STATUS_ORDER.get(item["overall_status"], 99))
    loans = parse_loans(client.get_account_page())
    return {
        "total_entries": total_entries,
        "removed_count": removed_count,
        "removal_success": removal_success,
        "items": visible_items,
        "loans": loans,
    }
