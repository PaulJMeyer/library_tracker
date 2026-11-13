from __future__ import annotations

import time

import requests

from library_tracker.isbn import normalize_isbn
from library_tracker.models import (
    GoogleBooksIdentifier,
    GoogleBooksResolution,
    GoogleBooksResolutionStatus,
)

GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_RETRIES = 3


class GoogleBooksError(RuntimeError):
    """Raised when Google Books cannot be queried reliably."""


def _resolution(
    isbn: str,
    status: GoogleBooksResolutionStatus,
    *,
    volume_id: str | None = None,
    title: str | None = None,
    authors: list[str] | None = None,
    language: str | None = None,
    publisher: str | None = None,
    published_date: str | None = None,
    identifiers: list[GoogleBooksIdentifier] | None = None,
    error_message: str | None = None,
) -> GoogleBooksResolution:
    return {
        "isbn13": isbn,
        "status": status,
        "volume_id": volume_id,
        "title": title,
        "authors": authors or [],
        "language": language,
        "publisher": publisher,
        "published_date": published_date,
        "identifiers": identifiers or [],
        "error_message": error_message,
    }


class GoogleBooksClient:
    def __init__(self, api_key: str) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "library-tracker/1.0",
                "Accept": "application/json",
                "X-Goog-Api-Key": api_key,
            }
        )

    def resolve_isbns(self, isbns: list[str]) -> list[GoogleBooksResolution]:
        results: list[GoogleBooksResolution] = []
        for isbn in isbns:
            results.append(self._resolve_isbn(isbn))
            time.sleep(0.25)
        return results

    def _resolve_isbn(self, isbn: str) -> GoogleBooksResolution:
        response = self._request(
            {"q": f"isbn:{isbn}", "printType": "books", "maxResults": 10}
        )
        payload = response.json()
        items = payload.get("items", [])
        if not isinstance(items, list):
            items = []

        requested = normalize_isbn(isbn)
        matches: list[tuple[str, dict[str, object], list[GoogleBooksIdentifier]]] = []

        for item in items:
            if not isinstance(item, dict):
                continue
            volume_id = item.get("id")
            volume_info = item.get("volumeInfo")
            if not isinstance(volume_id, str) or not isinstance(volume_info, dict):
                continue

            identifiers = _parse_identifiers(volume_info.get("industryIdentifiers", []))
            if any(identifier["identifier"] == requested for identifier in identifiers):
                matches.append((volume_id, volume_info, identifiers))

        if not matches:
            return _resolution(isbn, "not_found")
        if len({match[0] for match in matches}) > 1:
            return _resolution(
                isbn,
                "ambiguous",
                error_message="ISBN matched multiple Google Books volumes.",
            )

        volume_id, volume_info, identifiers = matches[0]
        title = volume_info.get("title")
        if not isinstance(title, str):
            return _resolution(
                isbn,
                "failed",
                error_message="Google Books volume has no usable title.",
            )

        raw_authors = volume_info.get("authors", [])
        authors = (
            [author for author in raw_authors if isinstance(author, str)]
            if isinstance(raw_authors, list)
            else []
        )
        return _resolution(
            isbn,
            "found",
            volume_id=volume_id,
            title=title,
            authors=authors,
            language=_optional_str(volume_info.get("language")),
            publisher=_optional_str(volume_info.get("publisher")),
            published_date=_optional_str(volume_info.get("publishedDate")),
            identifiers=identifiers,
        )

    def _request(self, params: dict[str, str | int]) -> requests.Response:
        response: requests.Response | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(GOOGLE_BOOKS_URL, params=params, timeout=30)
                if (
                    response.status_code in RETRYABLE_STATUS_CODES
                    and attempt < MAX_RETRIES - 1
                ):
                    time.sleep(2 ** attempt)
                    continue
                response.raise_for_status()
                return response
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "unknown"
                body = exc.response.text[:500] if exc.response is not None else ""
                raise GoogleBooksError(
                    f"Google Books request failed with HTTP {status}: {body}"
                ) from exc
            except requests.RequestException as exc:
                raise GoogleBooksError(f"Google Books request failed: {exc}") from exc

        if response is None:
            raise GoogleBooksError("Google Books request returned no response.")
        return response


def _parse_identifiers(raw_identifiers: object) -> list[GoogleBooksIdentifier]:
    if not isinstance(raw_identifiers, list):
        return []

    identifiers: list[GoogleBooksIdentifier] = []
    for raw in raw_identifiers:
        if not isinstance(raw, dict):
            continue
        identifier_type = raw.get("type")
        identifier = raw.get("identifier")
        if isinstance(identifier_type, str) and isinstance(identifier, str):
            identifiers.append(
                {
                    "type": identifier_type,
                    "identifier": normalize_isbn(identifier),
                }
            )
    return identifiers


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None
