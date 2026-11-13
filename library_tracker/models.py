from __future__ import annotations

from typing import Literal, TypedDict


ReadoListType = Literal["wishlist", "tbr", "reading", "completed"]
CopyStatus = Literal["ausleihbar", "bestellbar", "entliehen", "bestellt", "unbekannt"]
OpenLibraryResolutionStatus = Literal["resolved", "not_found", "ambiguous", "failed"]
GoogleBooksResolutionStatus = Literal["found", "not_found", "ambiguous", "failed"]
EditionLanguage = Literal["de", "en"]
PrintStatus = Literal["confirmed", "unknown"]
LibraryIsbnCandidateSource = Literal[
    "reado",
    "openlibrary_confirmed",
    "openlibrary_unknown",
]


class Copy(TypedDict):
    media_number: str
    signature: str
    branch: str
    status_text: str
    status: CopyStatus
    due_date: str | None
    is_central: bool


class Item(TypedDict):
    title: str
    overall_status: CopyStatus
    copies: list[Copy]


class Loan(TypedDict):
    title: str
    author: str
    media_number: str
    signature: str
    branch: str
    borrowed_since: str | None
    due_date: str | None
    renewal_note: str


class MemorizeEntry(TypedDict):
    uuid: str
    availability_link: str


class MemorizePage(TypedDict):
    cur_pos: str
    cs_id: str
    display_type: str
    selected_memorize_list: str
    entries: list[MemorizeEntry]


class AvailabilitySnapshot(TypedDict):
    media_number: str
    checked_at: str
    status: str
    status_text: str
    due_date: str | None


class ReadoListEntry(TypedDict):
    isbn13: str
    reado_url: str


class ReadoListSyncResult(TypedDict):
    new_entries: list[ReadoListEntry]
    removed_isbns: list[str]


class OpenLibraryResolution(TypedDict):
    isbn13: str
    status: OpenLibraryResolutionStatus
    work_key: str | None
    title: str | None
    error_message: str | None


class GoogleBooksIdentifier(TypedDict):
    type: str
    identifier: str


class GoogleBooksResolution(TypedDict):
    isbn13: str
    status: GoogleBooksResolutionStatus
    volume_id: str | None
    title: str | None
    authors: list[str]
    language: str | None
    publisher: str | None
    published_date: str | None
    identifiers: list[GoogleBooksIdentifier]
    error_message: str | None


class OpenLibraryEditionIdentifier(TypedDict):
    type: str
    identifier: str


class OpenLibraryEdition(TypedDict):
    edition_key: str
    work_key: str
    title: str
    languages: list[EditionLanguage]
    physical_format: str | None
    print_status: PrintStatus
    identifiers: list[OpenLibraryEditionIdentifier]


class LibraryIsbnCandidate(TypedDict):
    isbn: str
    source: LibraryIsbnCandidateSource


class LibraryMatchAttempt(LibraryIsbnCandidate):
    hit_count: int


class LibraryMatchResult(TypedDict):
    reado_isbn: str
    attempts: list[LibraryMatchAttempt]
    match: LibraryIsbnCandidate | None


class ScrapeResult(TypedDict):
    total_entries: int
    removed_count: int
    removal_success: bool
    items: list[Item]
    loans: list[Loan]
