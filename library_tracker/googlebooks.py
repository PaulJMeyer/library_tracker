from __future__ import annotations

import time

import requests

from library_tracker.models import (
    GoogleBooksIdentifier,
    GoogleBooksResolution,
)


GOOGLE_BOOKS_URL = (
    "https://www.googleapis.com/books/v1/volumes"
)

RETRYABLE_STATUS_CODES = {
    429,
    500,
    502,
    503,
    504,
}

MAX_RETRIES = 3


class GoogleBooksError(RuntimeError):
    """Raised when Google Books cannot be queried reliably."""


def normalize_isbn(value: str) -> str:
    return "".join(
        character
        for character in value.upper()
        if character.isdigit() or character == "X"
    )


class GoogleBooksClient:
    def __init__(
        self,
        api_key: str,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "library-tracker/1.0",
                "Accept": "application/json",
                "X-Goog-Api-Key": api_key,
            }
        )

    def resolve_isbns(
        self,
        isbns: list[str],
    ) -> list[GoogleBooksResolution]:
        results: list[GoogleBooksResolution] = []

        for isbn in isbns:
            results.append(
                self._resolve_isbn(isbn)
            )

            # This is a one-time fallback lookup.
            # There is no need to maximize request rate.
            time.sleep(0.25)

        return results

    def _resolve_isbn(
        self,
        isbn: str,
    ) -> GoogleBooksResolution:
        params: dict[str, str | int] = {
            "q": f"isbn:{isbn}",
            "printType": "books",
            "maxResults": 10,
        }

        response: requests.Response | None = None

        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(
                    GOOGLE_BOOKS_URL,
                    params=params,
                    timeout=30,
                )

                if (
                    response.status_code
                    in RETRYABLE_STATUS_CODES
                    and attempt < MAX_RETRIES - 1
                ):
                    wait_seconds = 2 ** attempt
                    time.sleep(wait_seconds)
                    continue

                response.raise_for_status()
                break

            except requests.HTTPError as exc:
                status_code = (
                    exc.response.status_code
                    if exc.response is not None
                    else "unknown"
                )

                response_text = (
                    exc.response.text[:500]
                    if exc.response is not None
                    else ""
                )

                raise GoogleBooksError(
                    f"Google Books request failed "
                    f"with HTTP {status_code}: "
                    f"{response_text}"
                ) from exc

            except requests.RequestException as exc:
                raise GoogleBooksError(
                    f"Google Books request failed: {exc}"
                ) from exc

        if response is None:
            raise GoogleBooksError(
                "Google Books request returned no response."
            )

        payload = response.json()
        items = payload.get("items", [])

        if not isinstance(items, list):
            items = []

        matching_items: list[
            tuple[
                str,
                dict[str, object],
                list[GoogleBooksIdentifier],
            ]
        ] = []

        normalized_requested = normalize_isbn(isbn)

        for item in items:
            if not isinstance(item, dict):
                continue

            volume_id = item.get("id")
            volume_info = item.get("volumeInfo")

            if not isinstance(volume_id, str):
                continue

            if not isinstance(volume_info, dict):
                continue

            raw_identifiers = volume_info.get(
                "industryIdentifiers",
                [],
            )

            identifiers: list[
                GoogleBooksIdentifier
            ] = []

            if isinstance(raw_identifiers, list):
                for raw_identifier in raw_identifiers:
                    if not isinstance(
                        raw_identifier,
                        dict,
                    ):
                        continue

                    identifier_type = (
                        raw_identifier.get("type")
                    )
                    identifier = (
                        raw_identifier.get("identifier")
                    )

                    if not isinstance(
                        identifier_type,
                        str,
                    ):
                        continue

                    if not isinstance(
                        identifier,
                        str,
                    ):
                        continue

                    identifiers.append(
                        {
                            "type": identifier_type,
                            "identifier": (
                                normalize_isbn(identifier)
                            ),
                        }
                    )

            has_requested_isbn = any(
                identifier["identifier"]
                == normalized_requested
                for identifier in identifiers
            )

            if has_requested_isbn:
                matching_items.append(
                    (
                        volume_id,
                        volume_info,
                        identifiers,
                    )
                )

        if not matching_items:
            return {
                "isbn13": isbn,
                "status": "not_found",
                "volume_id": None,
                "title": None,
                "authors": [],
                "language": None,
                "publisher": None,
                "published_date": None,
                "identifiers": [],
                "error_message": None,
            }

        unique_volume_ids = {
            item[0]
            for item in matching_items
        }

        if len(unique_volume_ids) > 1:
            return {
                "isbn13": isbn,
                "status": "ambiguous",
                "volume_id": None,
                "title": None,
                "authors": [],
                "language": None,
                "publisher": None,
                "published_date": None,
                "identifiers": [],
                "error_message": (
                    "ISBN matched multiple "
                    "Google Books volumes."
                ),
            }

        volume_id, volume_info, identifiers = (
            matching_items[0]
        )

        title = volume_info.get("title")

        if not isinstance(title, str):
            return {
                "isbn13": isbn,
                "status": "failed",
                "volume_id": None,
                "title": None,
                "authors": [],
                "language": None,
                "publisher": None,
                "published_date": None,
                "identifiers": [],
                "error_message": (
                    "Google Books volume has "
                    "no usable title."
                ),
            }

        raw_authors = volume_info.get("authors", [])

        authors = (
            [
                author
                for author in raw_authors
                if isinstance(author, str)
            ]
            if isinstance(raw_authors, list)
            else []
        )

        language = volume_info.get("language")
        publisher = volume_info.get("publisher")
        published_date = volume_info.get(
            "publishedDate"
        )

        return {
            "isbn13": isbn,
            "status": "found",
            "volume_id": volume_id,
            "title": title,
            "authors": authors,
            "language": (
                language
                if isinstance(language, str)
                else None
            ),
            "publisher": (
                publisher
                if isinstance(publisher, str)
                else None
            ),
            "published_date": (
                published_date
                if isinstance(published_date, str)
                else None
            ),
            "identifiers": identifiers,
            "error_message": None,
        }