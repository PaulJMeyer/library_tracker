from library_tracker.output import format_copy_line, format_status_summary
from library_tracker.models import Copy, Item


def make_copy(status_text: str, due_date: str | None) -> Copy:
    return {
        "media_number": "1",
        "signature": "sig",
        "branch": "10-Zentralbibliothek",
        "status_text": status_text,
        "status": "entliehen",
        "due_date": due_date,
        "is_central": True,
    }


def test_format_copy_line_no_due_date():
    copy = make_copy("ausleihbar", due_date=None)
    assert format_copy_line(copy) == "10-Zentralbibliothek | ausleihbar"


def test_format_copy_line_due_date_not_in_status_text():
    # due_date liegt separat vor, status_text enthält es noch nicht
    copy = make_copy("entliehen", due_date="20.08.2026")
    assert format_copy_line(copy) == "10-Zentralbibliothek | entliehen (fällig bis 20.08.2026)"


def test_format_copy_line_due_date_already_in_status_text():
    # status_text enthält das Datum schon -> keine Dopplung
    copy = make_copy("entliehen bis 16.08.2026", due_date="16.08.2026")
    assert format_copy_line(copy) == "10-Zentralbibliothek | entliehen bis 16.08.2026"


# --- format_status_summary ------------------------------------------------

def make_item(title: str, status: str) -> Item:
    return {"title": title, "overall_status": status, "copies": []}


def test_format_status_summary_counts_and_lists_titles():
    items = [
        make_item("Buch A", "ausleihbar"),
        make_item("Buch B", "bestellbar"),
        make_item("Buch C", "ausleihbar"),
        make_item("Buch D", "entliehen"),  # nicht Teil der Summary
    ]
    lines = format_status_summary(items)

    assert "Ausleihbar (2):" in lines
    assert "  - Buch A" in lines
    assert "  - Buch C" in lines
    assert "Bestellbar (1):" in lines
    assert "  - Buch B" in lines
    assert "Buch D" not in "\n".join(lines)


def test_format_status_summary_empty_status_shows_placeholder():
    items = [make_item("Buch A", "entliehen")]
    lines = format_status_summary(items)

    assert "Ausleihbar (0):" in lines
    assert "  - (keine)" in lines
