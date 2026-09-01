from bs4 import BeautifulSoup
from requests import Session

from library_tracker.client import build_url, get
from library_tracker.models import MemorizeEntry, MemorizePage


WISHLIST_URL = build_url("/webOPACClient/memorizelist.do")


def get_wishlist_page(session: Session, cur_pos: int = 1) -> str:
    if cur_pos == 1:
        url = f"{WISHLIST_URL}?methodToCall=show"
    else:
        url = f"{WISHLIST_URL}?methodToCall=pos&curPos={cur_pos}"

    response = get(session, url)
    return response.text


def extract_memorize_page(html: str, cur_pos: int) -> MemorizePage:
    soup = BeautifulSoup(html, "html.parser")

    form = soup.find("form", id="MemorizeBean")
    hidden_values: dict[str, str] = {}
    if form is not None:
        for name in ("selectedMemorizeList", "displayType", "CSId"):
            tag = form.find("input", attrs={"name": name})
            hidden_values[name] = tag.get("value", "") if tag else ""

    entries: list[MemorizeEntry] = []
    for row in soup.select("div.row.border-bottom"):
        checkbox = row.find("input", type="checkbox")
        link = row.find("a", href=lambda h: isinstance(h, str) and "runMemorizeAvailability" in h)
        if checkbox is None or link is None:
            continue
        entries.append({
            "uuid": checkbox.get("value", ""),
            "availability_link": build_url(link["href"]),
        })

    return {
        "cur_pos":                  str(cur_pos),
        "cs_id":                    hidden_values.get("CSId", ""),
        "display_type":             hidden_values.get("displayType", ""),
        "selected_memorize_list":   hidden_values.get("selectedMemorizeList", ""),
        "entries":                  entries,
    }


def get_all_memorize_pages(session: Session) -> list[MemorizePage]:
    pages: list[MemorizePage] = []
    cur_pos = 1

    while True:
        html = get_wishlist_page(session, cur_pos)
        page = extract_memorize_page(html, cur_pos)

        if not page["entries"]:
            break

        pages.append(page)

        if len(page["entries"]) < 10:
            break

        cur_pos += 10

    return pages


def remove_entries(session: Session, page: MemorizePage, uuids: list[str]) -> bool:
    if not uuids:
        return True

    params = {
        "methodToCall": "deleteSelectedEntries",
        "selectedMemorizeList": page["selected_memorize_list"],
        "displayType": page["display_type"],
        "curPos": page["cur_pos"],
        "CSId": page["cs_id"],
    }
    for index, uuid in enumerate(uuids):
        params[f"selectedMemListentries[{index}]"] = uuid

    response = get(session, WISHLIST_URL, params=params)
    return response.status_code == 200