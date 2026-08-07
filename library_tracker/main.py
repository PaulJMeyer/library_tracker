from library_tracker.client import get, build_url
from library_tracker.login import login
from library_tracker.library_parser import parse_availability_page
from library_tracker.wishlist import get_all_availability_links
from dotenv import load_dotenv
from library_tracker.models import Item

load_dotenv()

STATUS_ORDER = {
    "ausleihbar": 0,
    "bestellbar": 1,
    "entliehen":  2,
    "bestellt":   3,
    "unbekannt":  4,
}

EXEMPLAR_TAB_URL = build_url(
    "/webOPACClient/singleHit.do"
    "?methodToCall=activateTab"
    "&tab=showExemplarMemorizeActive"
)

def main() -> None:
    session = login()

    links = get_all_availability_links(session)
    print(f"Gefundene Medien: {len(links)}")

    items: list[Item] = []

    for link in links:
        get(session, link)                                    # Kontext setzen
        response = get(session, EXEMPLAR_TAB_URL)            # Tabelle abrufen
        item = parse_availability_page(response.text)
        items.append(item)

    items = sorted(
        items,
        key=lambda item: STATUS_ORDER.get(item["overall_status"], 99)
    )

    for entry in items:
        print(f"\n[{entry['overall_status'].upper()}] {entry['title']}")

        for copy in entry["copies"]:
            print(f"  - {copy['branch']} | {copy['status_text']}")