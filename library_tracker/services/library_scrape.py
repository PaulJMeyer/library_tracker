from __future__ import annotations

import sys

from library_tracker.clients.library import LibraryClient
from library_tracker.database import get_connection, initialize_database
from library_tracker.models import Item, MerklisteEntry, ScrapeResult
from library_tracker.parsers.library import (
    parse_availability_page,
    parse_loans,
    parse_page_count,
)
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
    print(f"   Merkliste: {total_entries} Einträge", file=sys.stderr, flush=True)

    visible_items: list[Item] = []
    scraped_items: list[Item] = []
    entries: list[MerklisteEntry] = []

    # Titles stay on the Merkliste even when every copy is checked out: the READO
    # wishlist decides what is monitored, and the overview only shows available ones.
    for page in pages:
        for entry in page["entries"]:
            details_html, copies_html = client.get_availability_pages(entry["availability_link"])
            item = parse_availability_page(copies_html)
            item["pages"] = parse_page_count(details_html) or parse_page_count(copies_html)
            scraped_items.append(item)
            if len(scraped_items) % 10 == 0:
                print(
                    f"   {len(scraped_items)}/{total_entries} Verfügbarkeiten gelesen",
                    file=sys.stderr,
                    flush=True,
                )
            entries.append({"title": item["title"], "uuid": entry["uuid"], "page": page})
            if item["overall_status"] != "entliehen":
                visible_items.append(item)

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
        "all_titles": [item["title"] for item in scraped_items],
        "entries": entries,
        "items": visible_items,
        "loans": loans,
    }
