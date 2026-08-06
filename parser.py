import re

from bs4 import BeautifulSoup
from models import Copy, Item


CENTRAL_BRANCH_KEYWORD = "10-Zentralbibliothek"

REQUIRED_HEADERS = {"Mediennummer", "Signatur", "Zweigstelle", "Status"}


def clean_text(text: str) -> str:
    return " ".join(text.split())


def extract_due_date(status_text: str) -> str | None:
    match = re.search(r"\b\d{2}\.\d{2}\.\d{4}\b", status_text)
    return match.group(0) if match else None


def normalize_copy_status(status_text: str) -> str:
    text = status_text.lower()

    if "bereits bestellt" in text:
        return "bestellt"
    if "bestellbar" in text:
        return "bestellbar"
    if "ausleihbar" in text or "verfügbar" in text:
        return "ausleihbar"
    if "entliehen" in text:
        return "entliehen"

    return "unbekannt"


def parse_copies(soup: BeautifulSoup) -> list[Copy]:
    copies: list[Copy] = []

    # Alle Datenzeilen: row border-bottom py-1
    for row in soup.find_all("div", class_=lambda c: c and "row" in c and "py-1" in c):
        cols = row.find_all("div", class_=lambda c: c and "col-12" in c)

        if len(cols) < 4:
            continue

        media_number = clean_text(cols[0].get_text(" ", strip=True))
        signature    = clean_text(cols[1].get_text(" ", strip=True))
        branch       = clean_text(cols[2].get_text(" ", strip=True))
        
        status_cell = cols[3]
        raw_status_text = status_cell.get_text(" ", strip=True)  # vor decompose
        for a in status_cell.find_all("a"):
            a.decompose()
        status_text = clean_text(status_cell.get_text(" ", strip=True))
        status_text = re.sub(r"\(gesamte Vormerkungen:.*?\)", "", status_text).strip()

        # Datum aus raw_text retten, falls status_text leer
        if not status_text:
            due = extract_due_date(raw_status_text)
            status_text = f"entliehen bis {due}" if due else "entliehen"

        if not media_number:
            continue

        copies.append({
            "media_number": media_number,
            "signature":    signature,
            "branch":       branch,
            "status_text":  status_text,
            "status":       normalize_copy_status(status_text),
            "due_date": extract_due_date(raw_status_text),
            "is_central":   CENTRAL_BRANCH_KEYWORD in branch,
        })

    return copies


def classify_item(copies: list[Copy]) -> str:
    if not copies:
        return "unbekannt"

    if any(c["status"] == "bestellt" for c in copies):
        return "bestellt"

    if any(c["is_central"] and c["status"] == "ausleihbar" for c in copies):
        return "ausleihbar"

    if any(not c["is_central"] and c["status"] in {"bestellbar", "ausleihbar"} for c in copies):
        return "bestellbar"

    return "entliehen"


def parse_title(soup: BeautifulSoup) -> str:
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

    # Punkt 5: Fallback statt None
    return "(Titel unbekannt)"


def parse_availability_page(html: str) -> Item:
    soup = BeautifulSoup(html, "html.parser")
    copies = parse_copies(soup)

    return {
        "title":          parse_title(soup),
        "overall_status": classify_item(copies),
        "copies":         copies
    }