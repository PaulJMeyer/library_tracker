import re

from bs4 import BeautifulSoup


CENTRAL_BRANCH_KEYWORD = "10-Zentralbibliothek"


def clean_text(text: str) -> str:
    return " ".join(text.split())


def extract_due_date(status_text: str) -> str | None:
    match = re.search(r"\b\d{2}\.\d{2}\.\d{4}\b", status_text)
    return match.group(0) if match else None


def normalize_copy_status(status_text: str) -> str:
    text = status_text.lower()

    if "bestellbar" in text:
        return "bestellbar"
    if "ausleihbar" in text or "verfügbar" in text:
        return "ausleihbar"
    if "entliehen" in text:
        return "entliehen"

    return "unbekannt"


def parse_copies(soup: BeautifulSoup) -> list[dict]:
    copies = []

    headers = [clean_text(th.get_text(" ", strip=True)) for th in soup.find_all("th")]

    html = str(soup)

    pos = html.find("Lokaler Bibliotheksbestand")
    print(pos)

    if pos != -1:
        print(repr(html[pos:pos+2000]))

    if not {"Mediennummer", "Signatur", "Zweigstelle", "Status"}.issubset(set(headers)):
        return copies

    for row in soup.find_all("tr"):
        cells = row.find_all("td")

        if len(cells) < 4:
            continue

        media_number = clean_text(cells[0].get_text(" ", strip=True))
        signature = clean_text(cells[1].get_text(" ", strip=True))
        branch = clean_text(cells[2].get_text(" ", strip=True))
        status_text = clean_text(cells[3].get_text(" ", strip=True))

        if not media_number:
            continue

        copies.append(
            {
                "media_number": media_number,
                "signature": signature,
                "branch": branch,
                "status_text": status_text,
                "status": normalize_copy_status(status_text),
                "due_date": extract_due_date(status_text),
                "is_central": CENTRAL_BRANCH_KEYWORD in branch,
            }
        )

    return copies


def classify_item(copies: list[dict]) -> str:
    if not copies:
        return "unbekannt"
    
    central_available = any(
        copy["is_central"] and copy["status"] == "ausleihbar"
        for copy in copies
    )

    if central_available:
        return "ausleihbar"

    other_branch_orderable = any(
        not copy["is_central"] and copy["status"] in ["bestellbar", "ausleihbar"]
        for copy in copies
    )

    if other_branch_orderable:
        return "bestellbar"

    return "entliehen"


def parse_title(soup: BeautifulSoup) -> str | None:
    ignored = {
        "Verfügbarkeit aus Merkliste",
        "Menu Closed Menu Open Exemplare",
        "Menu Closed Menu Open Bestellung (kostenlos)/Vormerkung (1,- Euro)",
        "Menu Closed Menu Open mehr zum Titel",
    }

    for h in soup.find_all(["h1", "h2", "h3"]):
        heading = clean_text(h.get_text(" ", strip=True))
        if heading and heading not in ignored:
            return heading

    return None


def parse_availability_page(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(" ", strip=True)

    status = "unbekannt"

    if "bereits bestellt" in page_text:
        status = "bestellt"
    elif "ausleihbar" in page_text:
        status = "ausleihbar"
    elif "bestellbar" in page_text or "andere Zweigstelle" in page_text:
        status = "bestellbar"
    elif "entliehen" in page_text:
        status = "entliehen"

    return {
        "title": parse_title(soup),
        "overall_status": status,
        "copies": [],
    }