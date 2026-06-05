from bs4 import BeautifulSoup

from client import build_url, get


WISHLIST_URL = build_url("/webOPACClient/memorizelist.do")


def get_wishlist_page(session, cur_pos: int = 1) -> str:
    if cur_pos == 1:
        url = f"{WISHLIST_URL}?methodToCall=show"
    else:
        url = f"{WISHLIST_URL}?methodToCall=pos&curPos={cur_pos}"

    response = get(session, url)
    return response.text


def extract_availability_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")

    links = []

    for a in soup.find_all("a"):
        href = a.get("href", "")
        if "runMemorizeAvailability" in href:
            links.append(build_url(href))

    return links


def get_all_availability_links(session) -> list[str]:
    all_links = []
    cur_pos = 1

    while True:
        html = get_wishlist_page(session, cur_pos)
        links = extract_availability_links(html)

        if not links:
            break

        all_links.extend(links)

        if len(links) < 10:
            break

        cur_pos += 10

    return all_links