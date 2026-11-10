from __future__ import annotations

from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


CATALOG_BASE_URL = (
    "https://opac.stabi-hb.de/webOPACClient/"
)

CATALOG_SEARCH_URL = urljoin(
    CATALOG_BASE_URL,
    "search.do",
)


class LibraryCatalogError(RuntimeError):
    """Raised when the library catalog cannot be searched."""


def normalize_isbn(isbn: str) -> str:
    return "".join(
        character
        for character in isbn.upper()
        if character.isdigit()
        or character == "X"
    )


def _extract_identifier(url: str) -> str | None:
    parsed = urlparse(url)
    values = parse_qs(parsed.query).get(
        "identifier"
    )

    if not values:
        return None

    return values[0]


def parse_catalog_hit_urls(
    html: str,
    response_url: str,
) -> list[str]:
    if "singleHit.do" in urlparse(
        response_url
    ).path:
        return [response_url]

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    hits: dict[str, str] = {}
    direct_hit_url: str | None = None

    for link in soup.select(
        'a[href*="singleHit.do"]'
    ):
        href = link.get("href")

        if not isinstance(href, str):
            continue

        absolute_url = urljoin(
            response_url,
            href,
        )

        identifier = _extract_identifier(
            absolute_url
        )

        if identifier is not None:
            hits.setdefault(
                identifier,
                absolute_url,
            )
            continue

        if (
            "methodToCall=activateTab"
            in href
            and "tab=showTitleActive"
            in href
        ):
            direct_hit_url = absolute_url

    if hits:
        return list(hits.values())

    if direct_hit_url is not None:
        return [direct_hit_url]

    return []


def search_catalog_by_isbn(
    session: requests.Session,
    cs_id: str,
    isbn: str,
) -> list[str]:
    normalized_isbn = normalize_isbn(isbn)

    params: dict[str, str] = {
        "methodToCall": "submit",
        "CSId": cs_id,
        "methodToCallParameter": "submitSearch",
        "searchCategories[0]": "540",
        "searchString[0]": normalized_isbn,
        "combinationOperator[1]": "AND",
        "searchCategories[1]": "331",
        "searchString[1]": "",
        "combinationOperator[2]": "AND",
        "searchCategories[2]": "100",
        "searchString[2]": "",
        "combinationOperator[3]": "AND",
        "searchCategories[3]": "902",
        "searchString[3]": "",
        "searchHistoryCombinationOperator": "AND",
        "searchHistory": "",
        "submitSearch": "Suchen",
        "linguistic": "false",
        "selectedViewBranchlib": "10",
        "selectedSearchBranchlib": "",
        "searchRestrictionID[0]": "3",
        "searchRestrictionValue1[0]": "",
        "callingPage": "searchPreferences",
        "exemplarSorting": "1",
        "numberOfHits": "10",
        "rememberList": "-1",
        "timeOut": "20",
        "considerSearchRestriction": "2",
        "startPage": "1",
        "language": "de",
        "selectedDefaultProfile": "1",
    }

    try:
        response = session.get(
            CATALOG_SEARCH_URL,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise LibraryCatalogError(
            "Library catalog search failed."
        ) from exc

    return parse_catalog_hit_urls(
        response.text,
        response.url,
    )