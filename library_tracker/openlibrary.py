from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Iterable

import requests

from library_tracker.models import (OpenLibraryResolution,
                                    EditionLanguage,
                                    OpenLibraryEdition,
                                    OpenLibraryEditionIdentifier,
                                    PrintStatus)


OPENLIBRARY_BASE_URL = "https://openlibrary.org"

OPENLIBRARY_SEARCH_URL = (
    f"{OPENLIBRARY_BASE_URL}/search.json"
)

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
    def get_work_editions(
        self,
        work_key: str,
    ) -> list[OpenLibraryEdition]:
        editions: list[
            OpenLibraryEdition
        ] = []

        offset = 0

        while True:
            params: dict[str, int] = {
                "limit": EDITION_PAGE_SIZE,
                "offset": offset,
            }

            try:
                response = self.session.get(
                    (
                        f"https://openlibrary.org/"
                        f"works/{work_key}/"
                        "editions.json"
                    ),
                    params=params,
                    timeout=30,
                )
                response.raise_for_status()

            except requests.RequestException as exc:
                raise OpenLibraryError(
                    "Open Library editions "
                    f"request failed for {work_key}."
                ) from exc

            payload = response.json()

            raw_entries = payload.get(
                "entries",
                []
            )

            if not isinstance(
                raw_entries,
                list,
            ):
                raise OpenLibraryError(
                    "Open Library editions "
                    "response has invalid entries."
                )

            for raw_entry in raw_entries:
                edition = _parse_edition(
                    work_key,
                    raw_entry,
                )

                if edition is not None:
                    editions.append(edition)

            size = payload.get("size")

            offset += len(raw_entries)

            if not raw_entries:
                break

            if (
                isinstance(size, int)
                and offset >= size
            ):
                break

            if len(raw_entries) < EDITION_PAGE_SIZE:
                break

            time.sleep(0.5)

        return editions


def _normalize_isbn(value: str) -> str:
    return "".join(
        character
        for character in value.upper()
        if character.isdigit()
        or character == "X"
    )


def _get_target_languages(
    raw_languages: object,
) -> list[EditionLanguage]:
    if not isinstance(raw_languages, list):
        return []

    languages: set[EditionLanguage] = set()

    for raw_language in raw_languages:
        if not isinstance(raw_language, dict):
            continue

        key = raw_language.get("key")

        if not isinstance(key, str):
            continue

        language = TARGET_LANGUAGES.get(key)

        if language is not None:
            languages.add(language)

    return sorted(languages)


def _get_identifiers(
    entry: dict[str, object],
) -> list[OpenLibraryEditionIdentifier]:
    identifiers: list[
        OpenLibraryEditionIdentifier
    ] = []

    for field_name, identifier_type in (
        ("isbn_13", "ISBN_13"),
        ("isbn_10", "ISBN_10"),
    ):
        raw_values = entry.get(
            field_name,
            [],
        )

        if not isinstance(raw_values, list):
            continue

        for raw_value in raw_values:
            if not isinstance(raw_value, str):
                continue

            identifier = _normalize_isbn(
                raw_value
            )

            if identifier:
                identifiers.append(
                    {
                        "type": identifier_type,
                        "identifier": identifier,
                    }
                )

    return identifiers


def _classify_print_format(
    physical_format: str | None,
) -> PrintStatus | None:
    if physical_format is None:
        return "unknown"

    normalized = physical_format.casefold()

    if any(
        marker in normalized
        for marker in NON_PRINT_FORMAT_MARKERS
    ):
        return None

    if any(
        marker in normalized
        for marker in PRINT_FORMAT_MARKERS
    ):
        return "confirmed"

    return "unknown"


def _parse_edition(
    work_key: str,
    entry: object,
) -> OpenLibraryEdition | None:
    if not isinstance(entry, dict):
        return None

    raw_key = entry.get("key")
    title = entry.get("title")

    if not isinstance(raw_key, str):
        return None

    if not isinstance(title, str):
        return None

    languages = _get_target_languages(
        entry.get("languages")
    )

    if not languages:
        return None

    identifiers = _get_identifiers(entry)

    if not identifiers:
        return None

    raw_format = entry.get(
        "physical_format"
    )

    physical_format = (
        raw_format
        if isinstance(raw_format, str)
        else None
    )

    print_status = _classify_print_format(
        physical_format
    )

    if print_status is None:
        return None

    edition_key = raw_key.removeprefix(
        "/books/"
    )

    return {
        "edition_key": edition_key,
        "work_key": work_key,
        "title": title,
        "languages": languages,
        "physical_format": physical_format,
        "print_status": print_status,
        "identifiers": identifiers,
    }