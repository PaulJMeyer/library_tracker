from collections.abc import Iterator
from pathlib import Path
import sqlite3

import pytest

from library_tracker.database import get_connection, initialize_database


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = get_connection(tmp_path / "data" / "library_tracker.db")
    initialize_database(connection)
    try:
        yield connection
    finally:
        connection.close()
