import requests
from urllib.parse import urljoin

WISHLIST_URL = (
    "https://opac.stabi-hb.de/webOPACClient/"
    "memorizelist.do?methodToCall=show"
)
BASE_URL = "https://opac.stabi-hb.de"


def get_wishlist(session: requests.Session):
    response = session.get(WISHLIST_URL)
    response.raise_for_status()

    print(f"Status: {response.status_code}")
    print(f"URL: {response.url}")

    return response.text


def get_availability_page(session, href):
    url = urljoin(BASE_URL, href)
    response = session.get(url)
    response.raise_for_status()

    print(f"Status: {response.status_code}")
    print(f"URL: {response.url}")

    return response.text