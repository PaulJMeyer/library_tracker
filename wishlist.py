from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://opac.stabi-hb.de"
WISHLIST_URL = f"{BASE_URL}/webOPACClient/memorizelist.do"


def get_wishlist_page(session: requests.Session, cur_pos: int = 1) -> str:
    params = {
        "methodToCall": "pos" if cur_pos > 1 else "show",
    }

    if cur_pos > 1:
        params["curPos"] = cur_pos

    response = session.get(WISHLIST_URL, params=params)
    response.raise_for_status()
    return response.text


def extract_availability_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")

    links = []
    for a in soup.find_all("a"):
        href = a.get("href", "")
        if "runMemorizeAvailability" in href:
            links.append(urljoin(BASE_URL, href))

    return links