from typing import TypedDict

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