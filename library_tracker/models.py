from typing import (TypedDict,
                    Literal)


OpenLibraryResolutionStatus = Literal[
    "resolved",
    "not_found",
    "ambiguous",
    "failed",
]


class Copy(TypedDict):
    media_number:   str
    signature:      str
    branch:         str
    status_text:    str
    status:         str
    due_date:       str | None
    is_central:     bool


class Item(TypedDict):
    title:              str
    overall_status:     str
    copies:             list[Copy]


class Loan(TypedDict):
    title:              str
    author:             str
    media_number:       str
    signature:          str
    branch:             str
    borrowed_since:     str | None
    due_date:           str | None
    renewal_note:       str


class MemorizeEntry(TypedDict):
    uuid:               str
    availability_link:  str


class MemorizePage(TypedDict):
    cur_pos:                    str
    cs_id:                      str
    display_type:               str
    selected_memorize_list:     str
    entries:                    list[MemorizeEntry]


class AvailabilitySnapshot(TypedDict):
    media_number: str
    checked_at: str
    status: str
    status_text: str
    due_date: str | None


ReadoListType = Literal[
    "wishlist",
    "tbr",
    "reading",
    "completed",
]


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