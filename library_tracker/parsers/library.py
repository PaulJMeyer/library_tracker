from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from library_tracker.config import LIBRARY_BASE_URL
from library_tracker.models import (
    Copy,
    CopyStatus,
    Item,
    Loan,
    MemorizeEntry,
    MemorizePage,
)

CENTRAL_BRANCH_KEYWORD = "10-Zentralbibliothek"
# Locations whose copies cannot be borrowed or ordered: the prison library and
# reference-only collections ("Präsenzbestand").
NOT_LENDABLE_BRANCH_KEYWORDS = ("JVA", "nicht online", "Präsenzbestand")


def is_lendable_location(copy: Copy) -> bool:
    return not any(keyword in copy["branch"] for keyword in NOT_LENDABLE_BRANCH_KEYWORDS)
DATE_PATTERN = re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b")
# Extent as printed in catalog records: "347 S.", "XII, 347 Seiten", "347 pages".
PAGES_PATTERN = re.compile(
    r"(?:\b[IVXLC]+\s*,\s*)?\b(\d{2,4})\s*(?:S\.|Seiten\b|p\.|pages\b)", re.IGNORECASE
)


def clean_text(text: str) -> str:
    return " ".join(text.split())


def extract_due_date(status_text: str) -> str | None:
    match = DATE_PATTERN.search(status_text)
    return match.group(0) if match else None


def normalize_copy_status(status_text: str) -> CopyStatus:
    text = status_text.lower()
    if "bereits bestellt" in text:
        return "bestellt"
    if "bereits ausgeliehen" in text:
        return "entliehen"
    if "bestellbar" in text:
        return "bestellbar"
    if "ausleihbar" in text or "verfügbar" in text:
        return "ausleihbar"
    if "entliehen" in text:
        return "entliehen"
    return "unbekannt"


def parse_copies(soup: BeautifulSoup) -> list[Copy]:
    copies: list[Copy] = []

    for row in soup.find_all("div", class_=lambda c: c and "row" in c and "py-1" in c):
        cols = row.find_all("div", class_=lambda c: c and "col-12" in c)
        if len(cols) < 4:
            continue

        media_number = clean_text(cols[0].get_text(" ", strip=True))
        if not media_number:
            continue

        status_cell = cols[3]
        raw_status = status_cell.get_text(" ", strip=True)
        for link in status_cell.find_all("a"):
            link.decompose()

        status_text = clean_text(status_cell.get_text(" ", strip=True))
        status_text = re.sub(r"\(gesamte Vormerkungen:.*?\)", "", status_text).strip()
        if not status_text:
            due_date = extract_due_date(raw_status)
            status_text = f"entliehen bis {due_date}" if due_date else "entliehen"

        branch = clean_text(cols[2].get_text(" ", strip=True))
        copies.append(
            {
                "media_number": media_number,
                "signature": clean_text(cols[1].get_text(" ", strip=True)),
                "branch": branch,
                "status_text": status_text,
                "status": normalize_copy_status(status_text),
                "due_date": extract_due_date(raw_status),
                "is_central": CENTRAL_BRANCH_KEYWORD in branch,
            }
        )

    return copies


def is_orderable(copy: Copy) -> bool:
    """A free copy in another branch that can be ordered to the central library."""
    return (
        not copy["is_central"]
        and copy["status"] in {"bestellbar", "ausleihbar"}
        and is_lendable_location(copy)
    )


def classify_item(copies: list[Copy]) -> CopyStatus:
    if not copies:
        return "unbekannt"
    if any(copy["status"] == "bestellt" for copy in copies):
        return "bestellt"
    if any(
        copy["is_central"] and copy["status"] == "ausleihbar" and is_lendable_location(copy)
        for copy in copies
    ):
        return "ausleihbar"
    if any(is_orderable(copy) for copy in copies):
        return "bestellbar"
    return "entliehen"


def parse_page_count(html: str) -> int | None:
    """Number of pages from a catalog title page, preferring the 'Umfang' field."""
    text = clean_text(BeautifulSoup(html, "html.parser").get_text(" "))
    umfang = text.find("Umfang")
    for part in ([text[umfang : umfang + 120]] if umfang >= 0 else []) + [text]:
        match = PAGES_PATTERN.search(part)
        if match:
            return int(match.group(1))
    return None


def parse_title(soup: BeautifulSoup) -> str:
    ignored = {
        "Verfügbarkeit aus Merkliste",
        "Menu Closed Menu Open Exemplare",
        "Menu Closed Menu Open Bestellung (kostenlos)/Vormerkung (1,- Euro)",
        "Menu Closed Menu Open mehr zum Titel",
    }
    for heading in soup.find_all(["h1", "h2", "h3"]):
        text = clean_text(heading.get_text(" ", strip=True))
        if text and text not in ignored:
            return text
    return "(Titel unbekannt)"


def parse_availability_page(html: str) -> Item:
    soup = BeautifulSoup(html, "html.parser")
    copies = parse_copies(soup)
    return {
        "title": parse_title(soup),
        "overall_status": classify_item(copies),
        "copies": copies,
    }


def parse_loan_dates(text: str) -> tuple[str | None, str | None, str]:
    dates = DATE_PATTERN.findall(text)
    borrowed_since = dates[0] if dates else None
    due_date = dates[1] if len(dates) >= 2 else None
    branch = text.rsplit(dates[-1], 1)[-1] if dates else text
    return borrowed_since, due_date, clean_text(branch)


def parse_loans(html: str) -> list[Loan]:
    soup = BeautifulSoup(html, "html.parser")
    loans: list[Loan] = []

    for row in soup.find_all("div", class_=lambda c: c and "row" in c and "border-bottom" in c):
        spans = row.find_all("span", class_="d-block")
        if len(spans) < 4:
            continue

        date_branch = row.find("div", class_=lambda c: c and "col-md-3" in c and "d-none" in c)
        if date_branch is None:
            continue

        title = clean_text(spans[0].get_text(" ", strip=True))
        if not title:
            continue

        borrowed_since, due_date, branch = parse_loan_dates(
            date_branch.get_text("\n", strip=True)
        )
        loans.append(
            {
                "title": title,
                "author": clean_text(spans[1].get_text(" ", strip=True)),
                "media_number": clean_text(spans[2].get_text(" ", strip=True)),
                "signature": clean_text(spans[3].get_text(" ", strip=True)).lstrip("/ ").strip(),
                "branch": branch,
                "borrowed_since": borrowed_since,
                "due_date": due_date,
                "renewal_note": (
                    clean_text(spans[4].get_text(" ", strip=True))
                    if len(spans) >= 5
                    else ""
                ),
            }
        )

    return loans


def _tag_value(tag: Tag, attr: str) -> str:
    value = tag.get(attr, "")
    if isinstance(value, list):
        return value[0] if value else ""
    return str(value)


def parse_memorize_page(html: str, cur_pos: int) -> MemorizePage:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", id="MemorizeBean")
    hidden: dict[str, str] = {}

    if isinstance(form, Tag):
        for name in ("selectedMemorizeList", "displayType", "CSId"):
            tag = form.find("input", attrs={"name": name})
            hidden[name] = _tag_value(tag, "value") if isinstance(tag, Tag) else ""

    entries: list[MemorizeEntry] = []
    for row in soup.select("div.row.border-bottom"):
        checkbox = row.find("input", type="checkbox")
        link = row.find(
            "a",
            href=lambda href: isinstance(href, str) and "runMemorizeAvailability" in href,
        )
        if not isinstance(checkbox, Tag) or not isinstance(link, Tag):
            continue
        entries.append(
            {
                "uuid": _tag_value(checkbox, "value"),
                "availability_link": urljoin(
                    LIBRARY_BASE_URL,
                    _tag_value(link, "href"),
                ),
            }
        )

    return {
        "cur_pos": str(cur_pos),
        "cs_id": hidden.get("CSId", ""),
        "display_type": hidden.get("displayType", ""),
        "selected_memorize_list": hidden.get("selectedMemorizeList", ""),
        "entries": entries,
    }


def extract_csid(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("input", {"name": "CSId"})
    if not isinstance(tag, Tag):
        raise ValueError("CSId wurde nicht gefunden.")
    return _tag_value(tag, "value")


def _extract_identifier(url: str) -> str | None:
    values = parse_qs(urlparse(url).query).get("identifier")
    return values[0] if values else None


def parse_catalog_hit_urls(html: str, response_url: str) -> list[str]:
    if "singleHit.do" in urlparse(response_url).path:
        return [response_url]

    soup = BeautifulSoup(html, "html.parser")
    hits: dict[str, str] = {}
    direct_hit_url: str | None = None

    for link in soup.select('a[href*="singleHit.do"]'):
        href = link.get("href")
        if not isinstance(href, str):
            continue

        absolute_url = urljoin(response_url, href)
        identifier = _extract_identifier(absolute_url)
        if identifier is not None:
            hits.setdefault(identifier, absolute_url)
        elif "methodToCall=activateTab" in href and "tab=showTitleActive" in href:
            direct_hit_url = absolute_url

    return list(hits.values()) or ([direct_hit_url] if direct_hit_url else [])


def parse_single_hit(html: str, page_url: str) -> tuple[str, str | None]:
    """Return (title, absolute 'in die Merkliste' URL or None) of a catalog single-hit page."""
    soup = BeautifulSoup(html, "html.parser")
    title = "(Titel unbekannt)"
    for heading in soup.find_all("h2"):
        text = clean_text(heading.get_text(" ", strip=True))
        if text and not text.startswith("Menu Closed") and "Vormerkung" not in text and "Bestellung" not in text:
            title = text
            break
    link = soup.find(
        "a",
        href=lambda href: isinstance(href, str) and "methodToCall=addToMemorizeList" in href,
    )
    memorize_url = urljoin(page_url, _tag_value(link, "href")) if isinstance(link, Tag) else None
    return title, memorize_url
