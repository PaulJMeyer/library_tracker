from client import get
from login import login
from parser import parse_availability_page
from wishlist import get_all_availability_links


STATUS_ORDER = {
    "ausleihbar": 0,
    "bestellbar": 1,
    "entliehen": 2,
    "unbekannt": 3,
}


def main():
    session = login()

    links = get_all_availability_links(session)
    print(f"Gefundene Medien: {len(links)}")

    items = []

    for link in links:
        response = get(session, link)
        item = parse_availability_page(response.text)
        items.append(item)

    items = sorted(
        items,
        key=lambda item: STATUS_ORDER.get(item["overall_status"], 99)
    )

    for item in items:
        print(f"\n[{item['overall_status'].upper()}] {item['title']}")

        for copy in item["copies"]:
            print(
                f"  - {copy['branch']} | "
                f"{copy['status_text']}"
            )


if __name__ == "__main__":
    main()