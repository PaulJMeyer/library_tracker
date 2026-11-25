from pathlib import Path

import pytest

from library_tracker.models import Copy, CopyStatus, Item, Loan
from library_tracker.output import (
    format_copy_line,
    format_results_markdown,
    format_status_summary,
    print_loans_console,
    print_results_console,
    write_results_markdown,
)


def make_copy(
    status_text: str,
    due_date: str | None,
    *,
    status: CopyStatus = "entliehen",
    branch: str = "10-Zentralbibliothek",
) -> Copy:
    return {
        "media_number": "1",
        "signature": "sig",
        "branch": branch,
        "status_text": status_text,
        "status": status,
        "due_date": due_date,
        "is_central": "10-Zentralbibliothek" in branch,
    }


def make_item(
    title: str,
    status: CopyStatus,
    copies: list[Copy] | None = None,
) -> Item:
    return {
        "title": title,
        "overall_status": status,
        "copies": copies or [],
    }


def test_format_copy_line_no_due_date() -> None:
    copy = make_copy(
        "ausleihbar",
        due_date=None,
        status="ausleihbar",
    )

    assert format_copy_line(copy) == "10-Zentralbibliothek | ausleihbar"


def test_format_copy_line_due_date_not_in_status_text() -> None:
    copy = make_copy("entliehen", due_date="20.08.2026")

    assert (
        format_copy_line(copy)
        == "10-Zentralbibliothek | entliehen (fällig bis 20.08.2026)"
    )


def test_format_copy_line_due_date_already_in_status_text() -> None:
    copy = make_copy(
        "entliehen bis 16.08.2026",
        due_date="16.08.2026",
    )

    assert (
        format_copy_line(copy)
        == "10-Zentralbibliothek | entliehen bis 16.08.2026"
    )


def test_format_status_summary_counts_and_lists_titles() -> None:
    items: list[Item] = [
        make_item("Buch A", "ausleihbar"),
        make_item("Buch B", "bestellbar"),
        make_item("Buch C", "ausleihbar"),
        make_item("Buch D", "entliehen"),
    ]

    lines = format_status_summary(items)

    assert "Ausleihbar (2):" in lines
    assert "  - Buch A" in lines
    assert "  - Buch C" in lines
    assert "Bestellbar (1):" in lines
    assert "  - Buch B" in lines
    assert "Buch D" not in "\n".join(lines)


def test_format_status_summary_empty_status_shows_placeholder() -> None:
    items: list[Item] = [make_item("Buch A", "entliehen")]

    lines = format_status_summary(items)

    assert "Ausleihbar (0):" in lines
    assert "Bestellbar (0):" in lines
    assert lines.count("  - (keine)") == 2


def test_format_results_markdown_contains_summary_and_details() -> None:
    available_copy = make_copy(
        "ausleihbar",
        due_date=None,
        status="ausleihbar",
    )
    items: list[Item] = [
        make_item("Buch A", "ausleihbar", [available_copy]),
        make_item("Buch B", "bestellbar"),
    ]

    result = format_results_markdown(items)

    assert "# Merkliste – Verfügbarkeit" in result
    assert "## Übersicht" in result
    assert "**Ausleihbar (1):**" in result
    assert "- Buch A" in result
    assert "**Bestellbar (1):**" in result
    assert "- Buch B" in result
    assert "## Details" in result
    assert "## [Ausleihbar] Buch A" in result
    assert "- 10-Zentralbibliothek | ausleihbar" in result


def test_format_results_markdown_empty_items() -> None:
    result = format_results_markdown([])

    assert "**Ausleihbar (0):**" in result
    assert "**Bestellbar (0):**" in result
    assert result.count("- (keine)") == 2


def test_write_results_markdown(tmp_path: Path) -> None:
    path = tmp_path / "results.md"

    write_results_markdown([], path)

    result = path.read_text(encoding="utf-8")
    assert "# Merkliste – Verfügbarkeit" in result


def test_print_results_console(
    capsys: pytest.CaptureFixture[str],
) -> None:
    copy = make_copy(
        "ausleihbar",
        due_date=None,
        status="ausleihbar",
    )
    items: list[Item] = [
        make_item("Testbuch", "ausleihbar", [copy]),
    ]

    print_results_console(items)

    output = capsys.readouterr().out
    assert "=== Übersicht ===" in output
    assert "Testbuch" in output
    assert "=== Details ===" in output
    assert "[AUSLEIHBAR] Testbuch" in output
    assert "10-Zentralbibliothek | ausleihbar" in output


def test_print_loans_console(
    capsys: pytest.CaptureFixture[str],
) -> None:
    loans: list[Loan] = [
        {
            "title": "Beispielroman",
            "author": "Erika Muster",
            "media_number": "123",
            "signature": "S Hewl",
            "branch": "Zentralbibliothek",
            "borrowed_since": "11.08.2026",
            "due_date": "01.09.2026",
            "renewal_note": "Verlängerung noch nicht möglich.",
        },
        {
            "title": "Unbekannte Daten",
            "author": "Autor",
            "media_number": "456",
            "signature": "ABC",
            "branch": "Vegesack",
            "borrowed_since": None,
            "due_date": None,
            "renewal_note": "",
        },
    ]

    print_loans_console(loans)

    output = capsys.readouterr().out
    assert "Kontoübersicht: Ausgeliehene Medien (2)" in output
    assert "Beispielroman (Erika Muster)" in output
    assert "Ausgeliehen seit: 11.08.2026 | Fällig: 01.09.2026" in output
    assert "Ausgeliehen seit: ? | Fällig: ?" in output


def test_format_telegram_message_lists_only_available_and_orderable() -> None:
    import datetime

    from library_tracker.output import format_telegram_message

    items = [
        make_item(
            "¬Die Zeitmaschine",
            "ausleihbar",
            [
                make_copy(
                    "ausleihbar",
                    None,
                    status="ausleihbar",
                    branch="10-Zentralbibliothek / 1.OG Romane A-Z",
                ),
                make_copy(
                    "entliehen bis 01.12.2026",
                    "01.12.2026",
                    branch="10-Zentralbibliothek / 1.OG Romane nach Themen",
                ),
            ],
        ),
        make_item(
            "Krieg & Frieden",
            "bestellbar",
            [
                make_copy("entliehen", None, branch="10-Zentralbibliothek / 1.OG"),
                make_copy(
                    "andere Zweigstelle (ausleihbar)",
                    None,
                    status="ausleihbar",
                    branch="21-Vahr / Romane",
                ),
                make_copy(
                    "andere Zweigstelle (entliehen)",
                    None,
                    branch="60-Vegesack / Romane",
                ),
            ],
        ),
    ]

    message = format_telegram_message(items, today=datetime.date(2026, 11, 24))

    assert message == "\n".join(
        [
            "<b>📚 Merkliste – 24.11.2026</b>",
            "",
            "<b>Ausleihbar in der Zentralbibliothek (1)</b>",
            "• Die Zeitmaschine <i>(1.OG Romane A-Z)</i>",
            "",
            "<b>Bestellbar aus anderen Zweigstellen (1)</b>",
            "• Krieg &amp; Frieden <i>(Vahr)</i>",
        ]
    )


def test_format_telegram_message_marks_empty_sections() -> None:
    import datetime

    from library_tracker.output import format_telegram_message

    message = format_telegram_message([], today=datetime.date(2026, 11, 24))

    assert message.count("– keine –") == 2


def test_format_match_report_summarizes_reasons() -> None:
    from library_tracker.output import format_match_report

    report = format_match_report(
        [
            {
                "isbn13": "9781111111111",
                "title": "¬Der gefundene Roman",
                "metadata": "Open Library",
                "reason": None,
                "candidate_count": 3,
                "searched_count": 2,
                "match": {"isbn": "9783333333333", "source": "openlibrary_confirmed"},
                "memorize_status": "added",
            },
            {
                "isbn13": "9782222222222",
                "title": "Missing Book",
                "metadata": "nicht gefunden",
                "reason": "Weder Open Library, Google Books noch DNB kennen die ISBN",
                "candidate_count": 1,
                "searched_count": 1,
                "match": None,
                "memorize_status": None,
            },
            {
                "isbn13": "9783333333333",
                "title": "Faust",
                "metadata": "Open Library + DNB",
                "reason": None,
                "candidate_count": 40,
                "searched_count": 15,
                "match": None,
                "memorize_status": None,
            },
        ]
    )

    assert "9781111111111 | Der gefundene Roman" in report
    assert "Katalog: gefunden mit 9783333333333 (deutsche Druckausgabe)" in report
    assert "Merkliste: von library-tracker hinzugefügt" in report
    assert "Katalog: nicht gefunden" in report
    assert "Katalog: noch nicht gefunden, 25 ISBN(s) offen (match-books)" in report
    assert "Im Katalog gefunden: 1/3" in report
    assert "Noch ISBNs offen: 1 Bücher" in report
    assert "1x Weder Open Library, Google Books noch DNB kennen die ISBN" in report


def test_format_telegram_message_lists_added_titles_and_warnings() -> None:
    import datetime

    from library_tracker.output import format_telegram_message

    message = format_telegram_message(
        [],
        today=datetime.date(2026, 11, 25),
        added_titles=["¬Der Adept"],
        warnings=["DNB fehlgeschlagen"],
        review_titles=["Faust, Band 3"],
        removed_titles=["¬Der Fremde"],
    )

    assert "<b>Neu auf der Merkliste (1)</b>\n• Der Adept" in message
    assert "<b>Von der Merkliste entfernt (1)</b>\n• Der Fremde" in message
    assert "<b>Bitte prüfen, nicht hinzugefügt (1)</b>\n• Faust, Band 3" in message
    assert message.endswith("⚠️ <i>DNB fehlgeschlagen</i>")
