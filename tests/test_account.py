from library_tracker.account import parse_loans, parse_loan_dates


SAMPLE_ROW_HTML = """
<div class="row border-bottom">
   <div class="d-none d-xl-inline-block col-xl-auto my-2"></div>
   <div class="col-2 col-xl-1 my-2"></div>
   <div class="col-8 col-md-7 my-2">
    <span class="d-block"><strong>Medea</strong></span>
    <span class="d-block">Hewlett, Rosie [VerfasserIn]</span>
    <span class="d-block">2090411478</span>
    <span class="d-block">&nbsp;/&nbsp;S Hewl Fantasy</span>
    <span class="d-block"><span class="textgruen">Eine Verlängerung ist noch nicht möglich.</span></span>
    <div class="d-block d-md-none">
      11.08.2026 - 01.09.2026
      <br />
      10-Zentralbibliothek&nbsp;/&nbsp;Zentralbibliothek
    </div>
   </div>
   <div class="d-none d-md-block col-md-3 my-2">
    11.08.2026 - 01.09.2026
    <br />
    10-Zentralbibliothek&nbsp;/&nbsp;Zentralbibliothek
   </div>
  </div>
"""


def test_parse_loans_extracts_all_fields():
    loans = parse_loans(SAMPLE_ROW_HTML)

    assert len(loans) == 1
    loan = loans[0]

    assert loan["title"] == "Medea"
    assert loan["author"] == "Hewlett, Rosie [VerfasserIn]"
    assert loan["media_number"] == "2090411478"
    assert loan["signature"] == "S Hewl Fantasy"
    assert loan["branch"] == "10-Zentralbibliothek / Zentralbibliothek"
    assert loan["borrowed_since"] == "11.08.2026"
    assert loan["due_date"] == "01.09.2026"
    assert loan["renewal_note"] == "Eine Verlängerung ist noch nicht möglich."


def test_parse_loans_empty_html_returns_empty_list():
    assert parse_loans("<html><body></body></html>") == []


def test_parse_loan_dates_both_dates_present():
    text = "11.08.2026 - 01.09.2026\n10-Zentralbibliothek / Zentralbibliothek"
    borrowed_since, due_date, branch = parse_loan_dates(text)

    assert borrowed_since == "11.08.2026"
    assert due_date == "01.09.2026"
    assert branch == "10-Zentralbibliothek / Zentralbibliothek"


def test_parse_loan_dates_no_dates():
    borrowed_since, due_date, branch = parse_loan_dates("keine Daten hier")
    assert borrowed_since is None
    assert due_date is None
