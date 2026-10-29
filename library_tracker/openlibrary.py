from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Iterable

import requests

from library_tracker.models import OpenLibraryResolution


OPENLIBRARY_BASE_URL = "https://openlibrary.org"
OPENLIBRARY_SEARCH_URL = (
    f"{OPENLIBRARY_BASE_URL}/search.json"
)
DEFAULT_BATCH_SIZE = 25


class OpenLibraryError(RuntimeError):
    """Raised when Open Library cannot be queried reliably."""


def _normalize_work_key(key: str) -> str:
    return key.removeprefix("/works/")


def _chunks(
    values: list[str],
    size: int,
) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index:index + size]


class OpenLibraryClient:
    def __init__(
        self,
        contact_email: str,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self.batch_size = batch_size

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "library-tracker/1.0 "
                    f"({contact_email})"
                ),
                "Accept": "application/json",
            }
        )

    def resolve_isbns(
        self,
        isbns: list[str],
    ) -> list[OpenLibraryResolution]:
        results: list[OpenLibraryResolution] = []

        for batch in _chunks(
            isbns,
            self.batch_size,
        ):
            batch_results = self._resolve_batch(
                batch
            )

            for result in batch_results:
                if result["status"] in {
                    "not_found",
                    "ambiguous",
                }:
                    time.sleep(0.5)

                    result = (
                        self._resolve_exact_isbn(
                            result["isbn13"]
                        )
                    )

                results.append(result)

            time.sleep(0.5)
            
        return results

    def _resolve_exact_isbn(
        self,
        isbn: str,
    ) -> OpenLibraryResolution:
        try:
            response = self.session.get(
                (
                    f"{OPENLIBRARY_BASE_URL}"
                    f"/isbn/{isbn}.json"
                ),
                timeout=30,
            )

            if response.status_code == 404:
                return {
                    "isbn13": isbn,
                    "status": "not_found",
                    "work_key": None,
                    "title": None,
                    "error_message": None,
                }

            response.raise_for_status()

        except requests.RequestException as exc:
            raise OpenLibraryError(
                "Open Library ISBN request failed."
            ) from exc

        payload = response.json()

        title = payload.get("title")
        works = payload.get("works", [])

        if not isinstance(works, list):
            works = []

        work_keys = {
            _normalize_work_key(key)
            for work in works
            if isinstance(work, dict)
            and isinstance(
                (key := work.get("key")),
                str,
            )
        }

        if not work_keys:
            return {
                "isbn13": isbn,
                "status": "not_found",
                "work_key": None,
                "title": None,
                "error_message": (
                    "ISBN exists but has no linked "
                    "Open Library work."
                ),
            }

        if len(work_keys) > 1:
            return {
                "isbn13": isbn,
                "status": "ambiguous",
                "work_key": None,
                "title": None,
                "error_message": (
                    "ISBN is linked to multiple "
                    "Open Library works."
                ),
            }

        if not isinstance(title, str):
            return {
                "isbn13": isbn,
                "status": "failed",
                "work_key": None,
                "title": None,
                "error_message": (
                    "Open Library edition has "
                    "no usable title."
                ),
            }

        work_key = next(iter(work_keys))

        return {
            "isbn13": isbn,
            "status": "resolved",
            "work_key": work_key,
            "title": title,
            "error_message": None,
        }

    def _resolve_batch(
        self,
        isbns: list[str],
    ) -> list[OpenLibraryResolution]:
        query = "isbn:(" + " OR ".join(isbns) + ")"

        params: dict[str, str | int] = {
            "q": query,
            "fields": "key,title,isbn",
            "limit": 100,
        }

        try:
            response = self.session.get(
                OPENLIBRARY_SEARCH_URL,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise OpenLibraryError(
                "Open Library request failed."
            ) from exc

        payload = response.json()
        docs = payload.get("docs", [])

        matches: dict[
            str,
            list[tuple[str, str]],
        ] = defaultdict(list)

        requested = set(isbns)

        for doc in docs:
            key = doc.get("key")
            title = doc.get("title")
            doc_isbns = doc.get("isbn", [])

            if not isinstance(key, str):
                continue

            if not isinstance(title, str):
                continue

            if not isinstance(doc_isbns, list):
                continue

            work_key = _normalize_work_key(key)

            for isbn in requested.intersection(
                str(value)
                for value in doc_isbns
            ):
                matches[isbn].append(
                    (work_key, title)
                )

        resolutions: list[OpenLibraryResolution] = []

        for isbn in isbns:
            isbn_matches = matches[isbn]

            if not isbn_matches:
                resolutions.append(
                    {
                        "isbn13": isbn,
                        "status": "not_found",
                        "work_key": None,
                        "title": None,
                        "error_message": None,
                    }
                )
                continue

            unique_matches = {
                work_key: title
                for work_key, title in isbn_matches
            }

            if len(unique_matches) > 1:
                resolutions.append(
                    {
                        "isbn13": isbn,
                        "status": "ambiguous",
                        "work_key": None,
                        "title": None,
                        "error_message": (
                            "ISBN matched multiple "
                            "Open Library works."
                        ),
                    }
                )
                continue

            work_key, title = next(
                iter(unique_matches.items())
            )

            resolutions.append(
                {
                    "isbn13": isbn,
                    "status": "resolved",
                    "work_key": work_key,
                    "title": title,
                    "error_message": None,
                }
            )

        return resolutions