from __future__ import annotations

from datetime import UTC, datetime

from library_tracker.clients.reado import read_list
from library_tracker.config import READO_LIST_TYPES, get_reado_list_url
from library_tracker.database import get_connection, initialize_database
from library_tracker.models import ReadoListEntry, ReadoListSyncResult, ReadoListType
from library_tracker.repositories.reado import sync_reado_list


def sync_lists(
    *,
    headless: bool = False,
    list_types: tuple[ReadoListType, ...] = READO_LIST_TYPES,
) -> tuple[
    dict[ReadoListType, list[ReadoListEntry]],
    dict[ReadoListType, ReadoListSyncResult],
]:
    entries_by_list = {
        list_type: read_list(get_reado_list_url(list_type), headless=headless)
        for list_type in list_types
    }
    checked_at = datetime.now(UTC).isoformat(timespec="seconds")

    connection = get_connection()
    try:
        initialize_database(connection)
        results = {
            list_type: sync_reado_list(
                connection,
                entries_by_list[list_type],
                list_type,
                checked_at,
            )
            for list_type in list_types
        }
    finally:
        connection.close()

    return entries_by_list, results
