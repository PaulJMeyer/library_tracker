from __future__ import annotations

import time
from urllib.parse import urljoin

import requests

from library_tracker.config import LIBRARY_BASE_URL, require_env
from library_tracker.isbn import normalize_isbn
from library_tracker.models import MemorizePage
from library_tracker.parsers.library import (
    extract_csid,
    parse_catalog_hit_urls,
    parse_memorize_page,
)
from collections.abc import Mapping

REQUEST_TIMEOUT = 20
REQUEST_DELAY = 1.0
MAX_MEMORIZE_PAGES = 50
RETRY_DELAYS = (2.0, 5.0)
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

LOGIN_PAGE_URL = urljoin(LIBRARY_BASE_URL, "/webOPACClient/start.do?StartPage=UserAccount")
LOGIN_URL = urljoin(LIBRARY_BASE_URL, "/webOPACClient/login.do")
WISHLIST_URL = urljoin(LIBRARY_BASE_URL, "/webOPACClient/memorizelist.do")
ACCOUNT_URL = urljoin(LIBRARY_BASE_URL, "/webOPACClient/userAccount.do?methodToCall=show")
EXEMPLAR_TAB_URL = urljoin(
    LIBRARY_BASE_URL,
    "/webOPACClient/singleHit.do?methodToCall=activateTab&tab=showExemplarMemorizeActive",
)
CATALOG_SEARCH_URL = urljoin(LIBRARY_BASE_URL, "/webOPACClient/search.do")


class LibraryClientError(RuntimeError):
    """Raised when the Bremen library catalog cannot be used reliably."""


class LibraryClient:
    def __init__(self, session: requests.Session, cs_id: str) -> None:
        self.session = session
        self.cs_id = cs_id

    @classmethod
    def login(cls) -> LibraryClient:
        session = requests.Session()
        login_page = _get(session, LOGIN_PAGE_URL, delay=False)
        cs_id = extract_csid(login_page.text)
        payload = {
            "methodToCall": "submit",
            "CSId": cs_id,
            "username": require_env("LIBRARY_USERNAME"),
            "password": require_env("LIBRARY_PASSWORD"),
            "login_action": "Login",
        }
        response = _post(session, LOGIN_URL, data=payload, delay=False)
        if "methodToCall=logout" not in response.text:
            raise LibraryClientError("Login wahrscheinlich fehlgeschlagen.")
        return cls(session, cs_id)

    def get_all_memorize_pages(self) -> list[MemorizePage]:
        pages: list[MemorizePage] = []
        seen: set[str] = set()
        cur_pos = 1
        for _ in range(MAX_MEMORIZE_PAGES):
            response = _get(self.session, self._wishlist_page_url(cur_pos))
            page = parse_memorize_page(response.text, cur_pos)
            new_entries = [entry for entry in page["entries"] if entry["uuid"] not in seen]
            # Past the last page the OPAC shows the last page again (for example
            # when the Merkliste holds exactly 10, 20, ... titles), so stop on repeats.
            if not new_entries:
                break
            page["entries"] = new_entries
            seen.update(entry["uuid"] for entry in new_entries)
            pages.append(page)
            if len(page["entries"]) < 10:
                break
            cur_pos += 10
        else:
            raise LibraryClientError(
                f"Merkliste hat mehr als {MAX_MEMORIZE_PAGES} Seiten, Lesen abgebrochen."
            )
        return pages

    def remove_entries(self, page: MemorizePage, uuids: list[str]) -> bool:
        if not uuids:
            return True

        params = {
            "methodToCall": "deleteSelectedEntries",
            "selectedMemorizeList": page["selected_memorize_list"],
            "displayType": page["display_type"],
            "curPos": page["cur_pos"],
            "CSId": page["cs_id"],
            **{
                f"selectedMemListentries[{index}]": uuid
                for index, uuid in enumerate(uuids)
            },
        }
        return _get(self.session, WISHLIST_URL, params=params).status_code == 200

    def get_availability_page(self, availability_link: str) -> str:
        _get(self.session, availability_link)
        return _get(self.session, EXEMPLAR_TAB_URL).text

    def get_account_page(self) -> str:
        return _get(self.session, ACCOUNT_URL).text

    def search_catalog_by_isbn(self, isbn: str) -> list[str]:
        params: dict[str, str] = {
            "methodToCall": "submit",
            "CSId": self.cs_id,
            "methodToCallParameter": "submitSearch",
            "searchCategories[0]": "540",
            "searchString[0]": normalize_isbn(isbn),
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
            response = _get(self.session, CATALOG_SEARCH_URL, params=params)
        except LibraryClientError:
            # Long runs can outlive the OPAC session; log in again once and retry.
            self._relogin()
            params["CSId"] = self.cs_id
            response = _get(self.session, CATALOG_SEARCH_URL, params=params)
        return parse_catalog_hit_urls(response.text, response.url)

    def get_page(self, url: str) -> tuple[str, str]:
        """Fetch a catalog page in this session; returns (html, final url)."""
        response = _get(self.session, url)
        return response.text, response.url

    def add_to_memorize_list(self, memorize_url: str) -> None:
        """Follow a catalog 'in die Merkliste' link. Never used for orders/reservations."""
        if "methodToCall=addToMemorizeList" not in memorize_url or "Vormerkung" in memorize_url:
            raise LibraryClientError("Refusing to call a non-Merkliste catalog action.")
        _get(self.session, memorize_url)

    def _relogin(self) -> None:
        fresh = LibraryClient.login()
        self.session = fresh.session
        self.cs_id = fresh.cs_id

    @staticmethod
    def _wishlist_page_url(cur_pos: int) -> str:
        method = "show" if cur_pos == 1 else f"pos&curPos={cur_pos}"
        return f"{WISHLIST_URL}?methodToCall={method}"


def _get(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, str] | None = None,
    delay: bool = True,
) -> requests.Response:
    if delay:
        time.sleep(REQUEST_DELAY)
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if response.status_code in RETRYABLE_STATUS_CODES and attempt < len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt])
                continue
            response.raise_for_status()
            return response
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt < len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt])
                continue
            raise LibraryClientError(
                f"Library request failed ({type(exc).__name__}): {url.split('?')[0]}"
            ) from exc
        except requests.RequestException as exc:
            raise LibraryClientError(
                f"Library request failed ({_describe(exc)}): {url.split('?')[0]}"
            ) from exc
    raise LibraryClientError(f"Library request failed after retries: {url.split('?')[0]}")


def _describe(exc: requests.RequestException) -> str:
    if exc.response is not None:
        return f"HTTP {exc.response.status_code}"
    return type(exc).__name__


def _post(
    session: requests.Session,
    url: str,
    *,
    data: Mapping[str, object],
    delay: bool = True,
) -> requests.Response:
    if delay:
        time.sleep(REQUEST_DELAY)
    try:
        response = session.post(url, data=data, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response
    except requests.RequestException as exc:
        raise LibraryClientError(f"Library request failed: {url}") from exc
