"""Deutsche Nationalbibliothek (DNB) catalog via its public SRU interface."""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import requests

from library_tracker.clients.openlibrary import authors_match, normalize_title, surname, titles_match
from library_tracker.isbn import isbn10_to_isbn13, normalize_isbn

DNB_SRU_URL = "https://services.dnb.de/sru/dnb"
SRU_NS = "{http://www.loc.gov/zing/srw/}"
MARC_NS = "{http://www.loc.gov/MARC21/slim}"
REQUEST_TIMEOUT = 30
REQUEST_DELAY = 1.0
MAX_RECORDS = 50
NON_PRINT_MARKERS = ("online", "computermedien", "e-book", "ebook", "audio", "hörbuch")


class DnbError(RuntimeError):
    """Raised when the DNB catalog cannot be queried reliably."""


@dataclass
class DnbRecord:
    title: str
    authors: list[str]
    languages: list[str]
    isbns: list[str] = field(default_factory=list)
    is_print: bool = True

    @property
    def is_german(self) -> bool:
        return "ger" in self.languages or (
            not self.languages and any(isbn.startswith("9783") for isbn in self.isbns)
        )


def _subfields(datafield: ET.Element, code: str) -> list[str]:
    return [
        (subfield.text or "").strip()
        for subfield in datafield.findall(f"{MARC_NS}subfield")
        if subfield.get("code") == code and subfield.text
    ]


def _datafields(record: ET.Element, tag: str) -> list[ET.Element]:
    return [field for field in record.findall(f"{MARC_NS}datafield") if field.get("tag") == tag]


def _controlfield(record: ET.Element, tag: str) -> str:
    for control in record.findall(f"{MARC_NS}controlfield"):
        if control.get("tag") == tag:
            return control.text or ""
    return ""


def _isbn13s(values: list[str]) -> list[str]:
    isbns: list[str] = []
    for value in values:
        # Subfields can carry qualifiers such as "978-3-...  (kart.)".
        match = re.search(r"[0-9][0-9\- ]{8,16}[0-9Xx]", value)
        if not match:
            continue
        isbn = normalize_isbn(match.group(0))
        if len(isbn) == 10:
            isbn = isbn10_to_isbn13(isbn) or ""
        if len(isbn) == 13 and isbn.isdigit() and isbn not in isbns:
            isbns.append(isbn)
    return isbns


def parse_marc_record(record: ET.Element) -> DnbRecord | None:
    title_fields = _datafields(record, "245")
    if not title_fields:
        return None
    title = " ".join(_subfields(title_fields[0], "a")).strip(" /:;")
    if not title:
        return None

    authors = [
        name
        for tag in ("100", "700")
        for datafield in _datafields(record, tag)
        for name in _subfields(datafield, "a")
    ]

    languages = [
        code for datafield in _datafields(record, "041") for code in _subfields(datafield, "a")
    ]
    fixed = _controlfield(record, "008")
    if not languages and len(fixed) >= 38 and fixed[35:38].strip():
        languages = [fixed[35:38]]

    isbn_values = [
        value
        for datafield in _datafields(record, "020")
        for code in ("a", "9")
        for value in _subfields(datafield, code)
    ]

    leader = record.findtext(f"{MARC_NS}leader") or ""
    media_texts = " ".join(
        value
        for tag in ("337", "338", "020")
        for datafield in _datafields(record, tag)
        for code in ("a", "c", "q")
        for value in _subfields(datafield, code)
    ).casefold()
    is_print = (
        (len(leader) < 7 or leader[6] == "a")
        and not _controlfield(record, "007").startswith("c")
        and not any(marker in media_texts for marker in NON_PRINT_MARKERS)
    )

    return DnbRecord(
        title=title,
        authors=authors,
        languages=languages,
        isbns=_isbn13s(isbn_values),
        is_print=is_print,
    )


def parse_sru_response(xml_text: str) -> list[DnbRecord]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise DnbError("DNB returned invalid XML.") from exc
    records: list[DnbRecord] = []
    for record_data in root.iter(f"{SRU_NS}recordData"):
        marc = record_data.find(f"{MARC_NS}record")
        if marc is not None and (parsed := parse_marc_record(marc)) is not None:
            records.append(parsed)
    return records


def _cql_phrase(text: str) -> str:
    return '"' + text.replace('"', " ").strip() + '"'


class DnbClient:
    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "library-tracker/1.0"})

    def search(self, query: str) -> list[DnbRecord]:
        time.sleep(REQUEST_DELAY)
        try:
            response = self.session.get(
                DNB_SRU_URL,
                params={
                    "version": "1.1",
                    "operation": "searchRetrieve",
                    "query": query,
                    "recordSchema": "MARC21-xml",
                    "maximumRecords": str(MAX_RECORDS),
                },
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DnbError(f"DNB request failed ({type(exc).__name__}).") from exc
        return parse_sru_response(response.text)

    def lookup_isbn(self, isbn: str) -> DnbRecord | None:
        records = self.search(f"num={normalize_isbn(isbn)}")
        return records[0] if records else None

    def find_german_print_editions(self, title: str, authors: list[str]) -> list[DnbRecord]:
        """German print editions with a matching title and author."""
        normalized = normalize_title(title)
        if not normalized or not authors:
            return []
        query = f"tit={_cql_phrase(normalized)} and per={_cql_phrase(surname(authors[0]))}"
        return [
            record
            for record in self.search(query)
            if record.is_print
            and record.is_german
            and record.isbns
            and titles_match(title, record.title)
            and authors_match(authors, record.authors)
        ]
