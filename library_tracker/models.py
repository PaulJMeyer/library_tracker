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