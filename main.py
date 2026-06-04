from bs4 import BeautifulSoup

from login import login
from wishlist import get_wishlist, get_availability_page
from parser import parse_availability_page

session = login()

html = get_wishlist(session)
soup = BeautifulSoup(html, "html.parser")

availability_links = []

for a in soup.find_all("a"):
    href = a.get("href", "")
    if "runMemorizeAvailability" in href:
        availability_links.append(href)

print(f"Gefundene Verfügbarkeitslinks: {len(availability_links)}")

first_html = get_availability_page(session, availability_links[0])
result = parse_availability_page(first_html)

print(result)