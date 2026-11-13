from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Iterable

import requests

from library_tracker.isbn import normalize_isbn
from library_tracker.models import (
    EditionLanguage,
    OpenLibraryEdition,
    OpenLibraryEditionIdentifier,
    OpenLibraryResolution,
    OpenLibraryResolutionStatus,
    PrintStatus,
)

OPENLIBRARY_BASE_URL = "https://openlibrary.org"
OPENLIBRARY_SEARCH_URL = f"{OPENLIBRARY_BASE_URL}/search.json"
DEFAULT_BATCH_SIZE = 25
EDITION_PAGE_SIZE = 100

TARGET_LANGUAGES: dict[str, EditionLanguage] = {
    "/languages/ger": "de",
    "/languages/deu": "de",
    "/languages/eng": "en",
}
NON_PRINT_FORMAT_MARKERS = (
    "ebook",
    "e-book",
    "kindle",
    "epub",
    "pdf",
    "audiobook",
    "audio book",
    "audio cd",
    "mp3",
)
PRINT_FORMAT_MARKERS = (
    "hardcover",
    "hardback",
    "paperback",
    "softcover",
    "mass market",
    "trade paperback",
    "library binding",
    "board book",
)


class OpenLibraryError(RuntimeError):
    """Raised when Open Library cannot be queried reliably."""


def _resolution(
    isbn: str,
    status: OpenLibraryResolutionStatus,
    *,
    work_key: str | None = None,
    title: str | None = None,
    error_message: str | None = None,
) -> OpenLibraryResolution:
    return {
        "isbn13": isbn,
        "status": status,
        "work_key": work_key,
        "title": title,
        "error_message": error_message,
    }


def _normalize_work_key(key: str) -> str:
    return key.removeprefix("/works/")


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index:index + size]


class OpenLibraryClient:
    def __init__(self, contact_email: str, *, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        self.batch_size = batch_size
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": f"library-tracker/1.0 ({contact_email})",
                "Accept": "application/json",
            }
        )

    def resolve_isbns(self, isbns: list[str]) -> list[OpenLibraryResolution]:
        results: list[OpenLibraryResolution] = []
        for batch in _chunks(isbns, self.batch_size):
            for result in self._resolve_batch(batch):
                if result["status"] in {"not_found", "ambiguous"}:
                    time.sleep(0.5)
                    result = self._resolve_exact_isbn(result["isbn13"])
                results.append(result)
            time.sleep(0.5)
        return results

    def _resolve_exact_isbn(self, isbn: str) -> OpenLibraryResolution:
        try:
            response = self.session.get(
                f"{OPENLIBRARY_BASE_URL}/isbn/{isbn}.json",
                timeout=30,
            )
            if response.status_code == 404:
                return _resolution(isbn, "not_found")
            response.raise_for_status()
        except requests.RequestException as exc:
            raise OpenLibraryError("Open Library ISBN request failed.") from exc

        payload = response.json()
        raw_works = payload.get("works", [])
        works = raw_works if isinstance(raw_works, list) else []
        work_keys = {
            _normalize_work_key(key)
            for work in works
            if isinstance(work, dict)
            and isinstance((key := work.get("key")), str)
        }

        if not work_keys:
            return _resolution(
                isbn,
                "not_found",
                error_message="ISBN exists but has no linked Open Library work.",
            )
        if len(work_keys) > 1:
            return _resolution(
                isbn,
                "ambiguous",
                error_message="ISBN is linked to multiple Open Library works.",
            )

        title = payload.get("title")
        if not isinstance(title, str):
            return _resolution(
                isbn,
                "failed",
                error_message="Open Library edition has no usable title.",
            )

        return _resolution(
            isbn,
            "resolved",
            work_key=next(iter(work_keys)),
            title=title,
        )

    def _resolve_batch(self, isbns: list[str]) -> list[OpenLibraryResolution]:
        params: dict[str, str | int] = {
            "q": "isbn:(" + " OR ".join(isbns) + ")",
            "fields": "key,title,isbn",
            "limit": 100,
        }
        try:
            response = self.session.get(OPENLIBRARY_SEARCH_URL, params=params, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise OpenLibraryError("Open Library request failed.") from exc

        payload = response.json()
        docs = payload.get("docs", [])
        if not isinstance(docs, list):
            docs = []

        requested = set(isbns)
        matches: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            key = doc.get("key")
            title = doc.get("title")
            doc_isbns = doc.get("isbn", [])
            if not isinstance(key, str) or not isinstance(title, str) or not isinstance(doc_isbns, list):
                continue

            for isbn in requested.intersection(str(value) for value in doc_isbns):
                matches[isbn].append((_normalize_work_key(key), title))

        resolutions: list[OpenLibraryResolution] = []
        for isbn in isbns:
            unique = dict(matches[isbn])
            if not unique:
                resolutions.append(_resolution(isbn, "not_found"))
            elif len(unique) > 1:
                resolutions.append(
                    _resolution(
                        isbn,
                        "ambiguous",
                        error_message="ISBN matched multiple Open Library works.",
                    )
                )
            else:
                work_key, title = next(iter(unique.items()))
                resolutions.append(
                    _resolution(isbn, "resolved", work_key=work_key, title=title)
                )
        return resolutions

    def get_work_editions(self, work_key: str) -> list[OpenLibraryEdition]:
        editions: list[OpenLibraryEdition] = []
        offset = 0

        while True:
            try:
                response = self.session.get(
                    f"{OPENLIBRARY_BASE_URL}/works/{work_key}/editions.json",
                    params={"limit": EDITION_PAGE_SIZE, "offset": offset},
                    timeout=30,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                raise OpenLibraryError(
                    f"Open Library editions request failed for {work_key}."
                ) from exc

            payload = response.json()
            raw_entries = payload.get("entries", [])
            if not isinstance(raw_entries, list):
                raise OpenLibraryError("Open Library editions response has invalid entries.")

            editions.extend(
                edition
                for raw_entry in raw_entries
                if (edition := _parse_edition(work_key, raw_entry)) is not None
            )

            offset += len(raw_entries)
            size = payload.get("size")
            if (
                not raw_entries
                or (isinstance(size, int) and offset >= size)
                or len(raw_entries) < EDITION_PAGE_SIZE
            ):
                break
            time.sleep(0.5)

        return editions


def _get_target_languages(raw_languages: object) -> list[EditionLanguage]:
    if not isinstance(raw_languages, list):
        return []

    languages: set[EditionLanguage] = set()
    for raw_language in raw_languages:
        if not isinstance(raw_language, dict):
            continue
        key = raw_language.get("key")
        if isinstance(key, str) and (language := TARGET_LANGUAGES.get(key)) is not None:
            languages.add(language)
    return sorted(languages)


def _get_identifiers(entry: dict[str, object]) -> list[OpenLibraryEditionIdentifier]:
    identifiers: list[OpenLibraryEditionIdentifier] = []
    for field_name, identifier_type in (("isbn_13", "ISBN_13"), ("isbn_10", "ISBN_10")):
        values = entry.get(field_name, [])
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, str) and (identifier := normalize_isbn(value)):
                identifiers.append({"type": identifier_type, "identifier": identifier})
    return identifiers


def _classify_print_format(physical_format: str | None) -> PrintStatus | None:
    if physical_format is None:
        return "unknown"

    normalized = physical_format.casefold()
    if any(marker in normalized for marker in NON_PRINT_FORMAT_MARKERS):
        return None
    if any(marker in normalized for marker in PRINT_FORMAT_MARKERS):
        return "confirmed"
    return "unknown"


def _parse_edition(work_key: str, entry: object) -> OpenLibraryEdition | None:
    if not isinstance(entry, dict):
        return None

    raw_key = entry.get("key")
    title = entry.get("title")
    if not isinstance(raw_key, str) or not isinstance(title, str):
        return None

    languages = _get_target_languages(entry.get("languages"))
    identifiers = _get_identifiers(entry)
    if not languages or not identifiers:
        return None

    raw_format = entry.get("physical_format")
    physical_format = raw_format if isinstance(raw_format, str) else None
    print_status = _classify_print_format(physical_format)
    if print_status is None:
        return None

    return {
        "edition_key": raw_key.removeprefix("/books/"),
        "work_key": work_key,
        "title": title,
        "languages": languages,
        "physical_format": physical_format,
        "print_status": print_status,
        "identifiers": identifiers,
    }
