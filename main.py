from client import get
from login import login
from parser import parse_availability_page
from wishlist import get_all_availability_links


def main():
    session = login()

    links = get_all_availability_links(session)
    print(f"Gefundene Medien: {len(links)}")

    for link in links:
        response = get(session, link)
        item = parse_availability_page(response.text)
        print(item)


if __name__ == "__main__":
    main()