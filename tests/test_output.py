from library_tracker.output import format_copy_line
from library_tracker.models import Copy


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
