import re

from bs4 import BeautifulSoup
from requests import Session

from library_tracker.client import build_url, get
from library_tracker.library_parser import clean_text
from library_tracker.models import Loan


ACCOUNT_URL = build_url("/webOPACClient/userAccount.do?methodToCall=show")

DATE_PATTERN = re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b")


def get_account_page(session: Session) -> str:
    response = get(session, ACCOUNT_URL)
    return response.text


def parse_loan_dates(date_branch_text: str) -> tuple[str | None, str | None, str]:
    """
    Erwartet Text in der Form:
    "11.08.2026 - 01.09.2026\n10-Zentralbibliothek / Zentralbibliothek"
    Gibt (borrowed_since, due_date, branch) zurück.
    """
    dates = DATE_PATTERN.findall(date_branch_text)
    borrowed_since = dates[0] if len(dates) >= 1 else None
    due_date = dates[1] if len(dates) >= 2 else None

    # Branch = Text nach dem letzten gefundenen Datum
    branch = date_branch_text
    if dates:
        branch = date_branch_text.rsplit(dates[-1], 1)[-1]
    branch = clean_text(branch)

    return borrowed_since, due_date, branch


def parse_loans(html: str) -> list[Loan]:
    soup = BeautifulSoup(html, "html.parser")
    loans: list[Loan] = []

    for row in soup.find_all("div", class_=lambda c: c and "row" in c and "border-bottom" in c):
        spans = row.find_all("span", class_="d-block")

        if len(spans) < 4:
            continue

        title = clean_text(spans[0].get_text(" ", strip=True))
        author = clean_text(spans[1].get_text(" ", strip=True))
        media_number = clean_text(spans[2].get_text(" ", strip=True))
        signature = clean_text(spans[3].get_text(" ", strip=True)).lstrip("/ ").strip()

        renewal_note = ""
        if len(spans) >= 5:
            renewal_note = clean_text(spans[4].get_text(" ", strip=True))

        date_branch_div = row.find("div", class_=lambda c: c and "col-md-3" in c and "d-none" in c)
        if date_branch_div is None:
            continue

        borrowed_since, due_date, branch = parse_loan_dates(
            date_branch_div.get_text("\n", strip=True)
        )

        if not title:
            continue

        loans.append({
            "title": title,
            "author": author,
            "media_number": media_number,
            "signature": signature,
            "branch": branch,
            "borrowed_since": borrowed_since,
            "due_date": due_date,
            "renewal_note": renewal_note,
        })

    return loans
