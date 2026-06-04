from login import login
from parser import parse_availability_page
from wishlist import extract_availability_links, get_wishlist_page

session = login()

all_results = []

cur_pos = 1

while True:
    print(f"\nLade Merkliste ab Position {cur_pos}...")

    html = get_wishlist_page(session, cur_pos=cur_pos)
    links = extract_availability_links(html)

    print(f"Gefundene Einträge auf dieser Seite: {len(links)}")

    if not links:
        break

    for link in links:
        response = session.get(link)
        response.raise_for_status()

        result = parse_availability_page(response.text)
        all_results.append(result)

        print(result)

    if len(links) < 10:
        break

    cur_pos += 10

print(f"\nInsgesamt gefunden: {len(all_results)}")