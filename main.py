from client import get, build_url
from login import login
from parser import parse_availability_page
from wishlist import get_all_availability_links
from dotenv import load_dotenv
from models import Item

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

    for item in items:
        print(f"\n[{item['overall_status'].upper()}] {item['title']}")

        for copy in item["copies"]:
            print(f"  - {copy['branch']} | {copy['status_text']}")


if __name__ == "__main__":
    main()