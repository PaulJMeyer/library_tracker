from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from library_tracker.clients.library import LibraryClient, LibraryClientError
from library_tracker.database import get_connection, initialize_database
from library_tracker.parsers.library import parse_single_hit
from library_tracker.repositories.metadata import save_dnb_lookup

SINGLE_HIT = """
<html><body>
<h1>Medienbestand (1/3)</h1>
<h2>¬Der Adept des Assassinen</h2>
<a href="/webOPACClient/memorizeHitList.do?methodToCall=addToMemorizeList&amp;curPos=1&amp;forward=singlehit&amp;identifier=-1_FT_1">in die Merkliste</a>
<h2>Menu Closed Menu Open Exemplare</h2>
<a href="/webOPACClient/singleHit.do?methodToCall=activateTab&amp;tab=showAvailabilityActive">Bestellung (kostenlos)/Vormerkung (1,- Euro)</a>
</body></html>
"""
BASE = "https://opac.stabi-hb.de/webOPACClient/singleHit.do?methodToCall=showHit&curPos=1"


def _copies_html(media_number: str) -> str:
    return (
        '<div class="row py-1">'
        f'<div class="col-12">{media_number}</div><div class="col-12">Sig</div>'
        '<div class="col-12">10-Zentralbibliothek</div><div class="col-12">ausleihbar</div>'
        "</div>"
    )


def test_parse_single_hit_finds_title_and_merkliste_link() -> None:
    title, url = parse_single_hit(SINGLE_HIT, BASE)

    assert title == "¬Der Adept des Assassinen"
    assert url == (
        "https://opac.stabi-hb.de/webOPACClient/memorizeHitList.do?methodToCall=addToMemorizeList"
        "&curPos=1&forward=singlehit&identifier=-1_FT_1"
    )


def test_add_to_memorize_list_refuses_other_actions() -> None:
    client = LibraryClient(Mock(spec=requests.Session), "csid")
    with pytest.raises(LibraryClientError):
        client.add_to_memorize_list(
            "https://opac.stabi-hb.de/webOPACClient/singleHit.do?methodToCall=activateTab&tab=showAvailabilityActive"
        )


@pytest.fixture
def db(tmp_path: Path):  # type: ignore[no-untyped-def]
    path = tmp_path / "db.sqlite"
    connection = get_connection(path)
    initialize_database(connection)
    for isbn in ("9781111111111", "9782222222222"):
        connection.execute("INSERT INTO reado_books VALUES (?, 'url', 'f', 'l')", (isbn,))
        connection.execute(
            "INSERT INTO reado_list_memberships VALUES (?, 'wishlist', 'f', 'l', 1)", (isbn,)
        )
    connection.commit()
    save_dnb_lookup(
        connection,
        "9781111111111",
        title="Viele Ausgaben",
        authors=["Muster, Erika"],
        editions=[(f"97830000{i:05d}", "Viele Ausgaben") for i in range(20)],
        found=True,
        searched_at="now",
    )
    connection.close()
    with (
        patch("library_tracker.services.library_matching.get_connection", side_effect=lambda: get_connection(path)),
    ):
        yield path


def test_match_wishlist_books_continues_with_next_isbns_each_run(db: Path) -> None:
    from library_tracker.services.library_matching import match_wishlist_books

    client = Mock(spec=LibraryClient)
    client.search_catalog_by_isbn.return_value = []

    first = match_wishlist_books(client, progress=lambda _: None)
    # Book 1: READO ISBN + 14 of 20 DNB editions; book 2: only its READO ISBN.
    assert first == {"books": 2, "searched": 16, "new_matches": 0, "new_editions": 0, "errors": 0}

    searched_first = {call.args[0] for call in client.search_catalog_by_isbn.call_args_list}
    client.search_catalog_by_isbn.reset_mock()
    client.search_catalog_by_isbn.side_effect = lambda isbn: (
        ["https://opac/hit"] if isbn in {"9783000000016", "9783000000018"} else []
    )

    second = match_wishlist_books(client, progress=lambda _: None)

    searched_second = [call.args[0] for call in client.search_catalog_by_isbn.call_args_list]
    assert not searched_first & set(searched_second)
    # The search goes on after the first hit to find every edition.
    assert searched_second == [f"978300000001{i}" for i in range(4, 10)]
    assert second["new_matches"] == 1
    assert second["new_editions"] == 2

    connection = get_connection(db)
    assert connection.execute("SELECT reado_isbn, matched_isbn, source FROM library_matches").fetchall() == [
        ("9781111111111", "9783000000016", "dnb")
    ]
    assert connection.execute(
        "SELECT reado_isbn, isbn FROM catalog_editions ORDER BY isbn"
    ).fetchall() == [("9781111111111", "9783000000016"), ("9781111111111", "9783000000018")]
    connection.close()

    # Found ISBNs are not searched again; nothing new to search until misses expire.
    client.search_catalog_by_isbn.reset_mock()
    assert match_wishlist_books(client, progress=lambda _: None)["searched"] == 0


def test_matched_books_search_further_editions_within_budget(db: Path) -> None:
    from library_tracker.repositories.library_matches import save_library_match
    from library_tracker.services.library_matching import match_wishlist_books

    connection = get_connection(db)
    save_library_match(connection, "9781111111111", "9781111111111", "reado", "now")
    connection.close()

    client = Mock(spec=LibraryClient)
    client.search_catalog_by_isbn.return_value = []

    summary = match_wishlist_books(client, extra_edition_searches=5, progress=lambda _: None)

    searched = [call.args[0] for call in client.search_catalog_by_isbn.call_args_list]
    # Unmatched book 2 first, then 5 further editions of the already matched book 1.
    assert searched == ["9782222222222"] + [f"97830000{i:05d}" for i in range(5)]
    assert summary["searched"] == 6


def test_all_editions_are_added_but_same_record_only_once(db: Path) -> None:
    from library_tracker.repositories.library_matches import save_catalog_edition, save_library_match
    from library_tracker.services.library_matching import add_matches_to_merkliste

    connection = get_connection(db)
    save_library_match(connection, "9781111111111", "9781111111111", "reado", "now")
    for isbn in ("9783000000001", "9783000000002", "9783000000003"):
        save_catalog_edition(connection, "9781111111111", isbn, "dnb", "now")
    save_catalog_edition(connection, "9781111111111", "9780000000001", "openlibrary_english", "now")
    connection.close()

    # Same title for every edition; the copy numbers tell the catalog records apart.
    # ...002 is the same record as ...001, ...003 is already on the Merkliste.
    copies = {
        "9781111111111": "A1",
        "9783000000001": "B1",
        "9783000000002": "B1",
        "9783000000003": "C1",
    }
    client = Mock(spec=LibraryClient)
    client.search_catalog_by_isbn.side_effect = lambda isbn: [f"https://opac/hit/{isbn}"]
    client.get_page.side_effect = lambda url: (
        SINGLE_HIT + _copies_html(copies[url.rsplit("/", 1)[1]]),
        BASE,
    )

    results = add_matches_to_merkliste(
        ["Der Adept des Assassinen"], client, existing_media_numbers=["C1"], progress=lambda _: None
    )

    assert results == [
        ("9781111111111", "Der Adept des Assassinen", "added"),
        ("9781111111111", "Der Adept des Assassinen", "added"),
        ("9781111111111", "Der Adept des Assassinen", "already_listed"),
        ("9781111111111", "Der Adept des Assassinen", "already_listed"),
    ]
    assert client.add_to_memorize_list.call_count == 2
    # The English edition is skipped because German editions exist.
    assert "9780000000001" not in [c.args[0] for c in client.search_catalog_by_isbn.call_args_list]

    connection = get_connection(db)
    assert connection.execute(
        "SELECT isbn, media_numbers, memorize_status FROM catalog_editions "
        "WHERE source != 'openlibrary_english' ORDER BY isbn"
    ).fetchall() == [
        ("9781111111111", "A1", "added"),
        ("9783000000001", "B1", "added"),
        ("9783000000002", "B1", "already_listed"),
        ("9783000000003", "C1", "already_listed"),
    ]
    connection.close()


def test_copy_numbers_are_read_from_the_copies_tab(db: Path) -> None:
    from library_tracker.repositories.library_matches import save_library_match
    from library_tracker.services.library_matching import add_matches_to_merkliste

    connection = get_connection(db)
    save_library_match(connection, "9781111111111", "9781111111111", "reado", "now")
    connection.close()

    tab_link = (
        '<a href="/webOPACClient/singleHit.do?methodToCall=activateTab'
        '&amp;tab=showExemplarActive">Exemplare</a>'
    )
    pages = {
        "https://opac/hit/9781111111111": SINGLE_HIT + tab_link,
        "https://opac.stabi-hb.de/webOPACClient/singleHit.do?methodToCall=activateTab&tab=showExemplarActive": _copies_html("X1"),
    }
    client = Mock(spec=LibraryClient)
    client.search_catalog_by_isbn.side_effect = lambda isbn: [f"https://opac/hit/{isbn}"]
    client.get_page.side_effect = lambda url: (pages[url], BASE)

    # Same title on the Merkliste, but another catalog record: added.
    results = add_matches_to_merkliste(
        ["Der Adept des Assassinen"], client, existing_media_numbers=["Z9"], progress=lambda _: None
    )

    assert results == [("9781111111111", "Der Adept des Assassinen", "added")]
    # Hit page, copies tab, hit page again before following its Merkliste link.
    assert [c.args[0] for c in client.get_page.call_args_list] == [
        "https://opac/hit/9781111111111",
        "https://opac.stabi-hb.de/webOPACClient/singleHit.do?methodToCall=activateTab&tab=showExemplarActive",
        "https://opac/hit/9781111111111",
    ]


def test_misses_are_rechecked_after_the_waiting_period(db: Path) -> None:
    from library_tracker.services.library_matching import match_wishlist_books

    client = Mock(spec=LibraryClient)
    client.search_catalog_by_isbn.return_value = []
    match_wishlist_books(client, progress=lambda _: None)
    match_wishlist_books(client, progress=lambda _: None)
    client.search_catalog_by_isbn.reset_mock()

    assert match_wishlist_books(client, progress=lambda _: None)["searched"] == 0
    assert match_wishlist_books(client, recheck_days=-1, progress=lambda _: None)["searched"] == 16


def test_add_matches_to_merkliste_adds_skips_and_retries(db: Path) -> None:
    from library_tracker.repositories.library_matches import save_library_match
    from library_tracker.services.library_matching import add_matches_to_merkliste

    connection = get_connection(db)
    save_library_match(connection, "9781111111111", "9783000000001", "dnb", "now")
    save_library_match(connection, "9782222222222", "9782222222222", "reado", "now")
    connection.close()

    client = Mock(spec=LibraryClient)
    client.search_catalog_by_isbn.side_effect = lambda isbn: [f"https://opac/hit/{isbn}"]
    client.get_page.side_effect = lambda url: (
        SINGLE_HIT if url.endswith("9783000000001") else SINGLE_HIT.replace("Der Adept des Assassinen", "Schon da"),
        BASE,
    )

    results = add_matches_to_merkliste(["Schon da"], client, progress=lambda _: None)

    assert results == [
        ("9781111111111", "Der Adept des Assassinen", "added"),
        ("9782222222222", "Schon da", "already_listed"),
    ]
    client.add_to_memorize_list.assert_called_once()
    # Both are done now; nothing left to add on the next run.
    assert add_matches_to_merkliste([], client, progress=lambda _: None) == []


def test_failed_merkliste_add_is_retried(db: Path) -> None:
    from library_tracker.repositories.library_matches import save_library_match
    from library_tracker.services.library_matching import add_matches_to_merkliste

    connection = get_connection(db)
    save_library_match(connection, "9781111111111", "9783000000001", "dnb", "now")
    connection.close()

    client = Mock(spec=LibraryClient)
    client.search_catalog_by_isbn.side_effect = LibraryClientError("down")
    assert add_matches_to_merkliste([], client, progress=lambda _: None) == [
        ("9781111111111", "9783000000001", "failed")
    ]
    assert len(add_matches_to_merkliste([], client, progress=lambda _: None)) == 1


def test_match_report_uses_stored_results(db: Path) -> None:
    from library_tracker.repositories.library_matches import save_catalog_search, save_library_match
    from library_tracker.services.library_matching import build_match_report

    connection = get_connection(db)
    save_catalog_search(connection, "9781111111111", None, "now")
    save_catalog_search(connection, "9782222222222", "https://opac/hit", "now")
    save_library_match(connection, "9782222222222", "9782222222222", "reado", "now")
    connection.close()

    rows = {row["isbn13"]: row for row in build_match_report()}

    assert rows["9781111111111"]["candidate_count"] == 21
    assert rows["9781111111111"]["searched_count"] == 1
    assert rows["9781111111111"]["match"] is None
    assert rows["9782222222222"]["match"] == {"isbn": "9782222222222", "source": "reado"}


def test_single_volume_of_multi_volume_edition_is_not_added(db: Path) -> None:
    from library_tracker.repositories.library_matches import save_library_match
    from library_tracker.services.library_matching import add_matches_to_merkliste

    connection = get_connection(db)
    save_library_match(connection, "9781111111111", "9783000000001", "dnb", "now")
    connection.close()

    client = Mock(spec=LibraryClient)
    client.search_catalog_by_isbn.return_value = ["https://opac/hit/1"]
    client.get_page.return_value = (
        SINGLE_HIT.replace("Der Adept des Assassinen", "Faust - Der Tragödie erster Teil, Band 3"),
        BASE,
    )

    results = add_matches_to_merkliste([], client, progress=lambda _: None)

    assert results == [
        ("9781111111111", "Faust - Der Tragödie erster Teil, Band 3", "needs_review")
    ]
    client.add_to_memorize_list.assert_not_called()
    # Reported once, not retried on every run.
    assert add_matches_to_merkliste([], client, progress=lambda _: None) == []


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Faust - Der Tragödie erster Teil, Band 3", True),
        ("Werke Bd. 2", True),
        ("Collected Works, Vol. 1", True),
        ("Red Rising - Asche zu Asche", False),
        ("Faust - Der Tragödie erster Teil", False),
        ("Die Bandbreite der Dinge", False),
    ],
)
def test_is_single_volume(title: str, expected: bool) -> None:
    from library_tracker.services.library_matching import is_single_volume

    assert is_single_volume(title) is expected


def test_old_library_matches_table_is_migrated(tmp_path: Path) -> None:
    connection = get_connection(tmp_path / "old.sqlite")
    initialize_database(connection)
    connection.executescript(
        """
        INSERT INTO reado_books VALUES ('978', 'url', 'f', 'l');
        DROP TABLE library_matches;
        CREATE TABLE library_matches (
            reado_isbn TEXT PRIMARY KEY,
            matched_isbn TEXT NOT NULL,
            source TEXT NOT NULL,
            matched_at TEXT NOT NULL,
            catalog_title TEXT,
            memorize_status TEXT CHECK (memorize_status IN ('added', 'already_listed', 'failed')),
            memorize_checked_at TEXT
        );
        INSERT INTO library_matches VALUES ('978', '979', 'dnb', 'now', 'T', 'added', 'now');
        """
    )
    initialize_database(connection)
    connection.execute("UPDATE library_matches SET memorize_status = 'needs_review'")
    assert connection.execute(
        "SELECT reado_isbn, catalog_title, memorize_status FROM library_matches"
    ).fetchall() == [("978", "T", "needs_review")]
    connection.close()


def test_exact_reado_isbn_is_added_even_if_it_is_a_volume(db: Path) -> None:
    from library_tracker.repositories.library_matches import save_library_match
    from library_tracker.services.library_matching import add_matches_to_merkliste

    connection = get_connection(db)
    save_library_match(connection, "9782222222222", "9782222222222", "reado", "now")
    connection.close()

    client = Mock(spec=LibraryClient)
    client.search_catalog_by_isbn.return_value = ["https://opac/hit/1"]
    client.get_page.return_value = (
        SINGLE_HIT.replace("Der Adept des Assassinen", "Die Weitseher, Band 1"),
        BASE,
    )

    results = add_matches_to_merkliste([], client, progress=lambda _: None)

    assert results == [("9782222222222", "Die Weitseher, Band 1", "added")]
    client.add_to_memorize_list.assert_called_once()


def test_ebook_only_hits_are_not_added(db: Path) -> None:
    from library_tracker.repositories.library_matches import save_library_match
    from library_tracker.services.library_matching import add_matches_to_merkliste

    connection = get_connection(db)
    save_library_match(connection, "9781111111111", "9783000000001", "dnb", "now")
    connection.close()
    ebook_hit = SINGLE_HIT + _copies_html("E1").replace("10-Zentralbibliothek", "80-Online-Zweigstelle")
    client = Mock(spec=LibraryClient)
    client.search_catalog_by_isbn.return_value = ["https://opac/hit"]
    client.get_page.return_value = (ebook_hit, BASE)

    results = add_matches_to_merkliste([], client, progress=lambda _: None)

    assert results == [("9781111111111", "Der Adept des Assassinen", "ebook")]
    client.add_to_memorize_list.assert_not_called()
    # Not tried again on the next run.
    assert add_matches_to_merkliste([], client, progress=lambda _: None) == []


def test_old_catalog_editions_table_gets_the_ebook_status(tmp_path: Path) -> None:
    connection = get_connection(tmp_path / "old.sqlite")
    initialize_database(connection)
    connection.executescript(
        """
        INSERT INTO reado_books VALUES ('978', 'url', 'f', 'l');
        DROP TABLE catalog_editions;
        CREATE TABLE catalog_editions (
            reado_isbn TEXT NOT NULL,
            isbn TEXT NOT NULL,
            source TEXT NOT NULL,
            found_at TEXT NOT NULL,
            catalog_title TEXT,
            media_numbers TEXT,
            memorize_status TEXT CHECK (
                memorize_status IN ('added', 'already_listed', 'failed', 'needs_review')
            ),
            memorize_checked_at TEXT,
            PRIMARY KEY (reado_isbn, isbn)
        );
        INSERT INTO catalog_editions VALUES ('978', '979', 'dnb', 'now', 'T', 'M1', 'added', 'now');
        """
    )
    initialize_database(connection)
    connection.execute("UPDATE catalog_editions SET memorize_status = 'ebook'")
    assert connection.execute(
        "SELECT isbn, catalog_title, media_numbers, memorize_status FROM catalog_editions"
    ).fetchall() == [("979", "T", "M1", "ebook")]
    connection.close()
