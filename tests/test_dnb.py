from unittest.mock import Mock, patch

import pytest
import requests

from library_tracker.clients.dnb import DnbClient, DnbError, parse_sru_response


def marc_record(
    *,
    title: str = "Beispielroman",
    author: str = "Muster, Erika",
    isbns: tuple[str, ...] = ("978-3-499-62602-9",),
    language: str = "ger",
    leader: str = "00000nam a2200000 c 4500",
    extra: str = "",
) -> str:
    isbn_fields = "".join(
        f'<datafield tag="020" ind1=" " ind2=" "><subfield code="9">{isbn}</subfield>'
        f'<subfield code="c">kart. : EUR 12.00</subfield></datafield>'
        for isbn in isbns
    )
    return f"""
    <record><recordSchema>MARC21-xml</recordSchema><recordPacking>xml</recordPacking>
    <recordData><record xmlns="http://www.loc.gov/MARC21/slim" type="Bibliographic">
      <leader>{leader}</leader>
      <controlfield tag="001">1</controlfield>
      {isbn_fields}
      <datafield tag="041" ind1="0" ind2=" "><subfield code="a">{language}</subfield></datafield>
      <datafield tag="100" ind1="1" ind2=" "><subfield code="a">{author}</subfield></datafield>
      <datafield tag="245" ind1="1" ind2="0"><subfield code="a">{title}</subfield>
        <subfield code="b">Roman</subfield></datafield>
      {extra}
    </record></recordData></record>"""


def sru(*records: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<searchRetrieveResponse xmlns="http://www.loc.gov/zing/srw/">'
        f"<version>1.1</version><numberOfRecords>{len(records)}</numberOfRecords>"
        f"<records>{''.join(records)}</records></searchRetrieveResponse>"
    )


def test_parse_sru_response_reads_title_author_language_isbns() -> None:
    records = parse_sru_response(sru(marc_record(isbns=("978-3-499-62602-9", "3-499-62602-0"))))

    assert len(records) == 1
    record = records[0]
    assert record.title == "Beispielroman"
    assert record.authors == ["Muster, Erika"]
    assert record.is_german and record.is_print
    assert record.isbns == ["9783499626029"]


def test_parse_marks_ebooks_and_audiobooks_as_non_print() -> None:
    ebook = marc_record(
        extra='<datafield tag="338" ind1=" " ind2=" "><subfield code="a">Online-Ressource</subfield></datafield>'
    )
    audio = marc_record(leader="00000nim a2200000 c 4500")

    assert [record.is_print for record in parse_sru_response(sru(ebook, audio))] == [False, False]


def test_parse_invalid_xml_raises() -> None:
    with pytest.raises(DnbError):
        parse_sru_response("<not-xml")


def make_client(*bodies: str) -> tuple[DnbClient, Mock]:
    session = Mock(spec=requests.Session)
    session.headers = {}
    responses = []
    for body in bodies:
        response = Mock(spec=requests.Response)
        response.text = body
        response.raise_for_status.return_value = None
        responses.append(response)
    session.get.side_effect = responses
    return DnbClient(session), session


def test_lookup_isbn_queries_num_index() -> None:
    client, session = make_client(sru(marc_record()))
    with patch("library_tracker.clients.dnb.time.sleep"):
        record = client.lookup_isbn("978-3-499-62602-9")

    assert record is not None and record.title == "Beispielroman"
    assert session.get.call_args.kwargs["params"]["query"] == "num=9783499626029"


def test_find_german_print_editions_filters_results() -> None:
    client, session = make_client(
        sru(
            marc_record(isbns=("978-3-499-62602-9",)),
            marc_record(title="Ganz anderes Buch", isbns=("978-3-16-148410-0",)),
            marc_record(language="eng", isbns=("978-0-306-40615-7",)),
            marc_record(author="Andere, Person", isbns=("978-3-596-29600-6",)),
        )
    )
    with patch("library_tracker.clients.dnb.time.sleep"):
        records = client.find_german_print_editions("Beispielroman", ["Erika Muster"])

    assert [record.isbns for record in records] == [["9783499626029"]]
    assert session.get.call_args.kwargs["params"]["query"] == 'tit="beispielroman" and per="Muster"'


def test_find_german_print_editions_needs_author() -> None:
    client, session = make_client()
    assert client.find_german_print_editions("Beispielroman", []) == []
    session.get.assert_not_called()


def test_request_error_raises_dnb_error() -> None:
    session = Mock(spec=requests.Session)
    session.headers = {}
    session.get.side_effect = requests.Timeout()
    with patch("library_tracker.clients.dnb.time.sleep"), pytest.raises(DnbError, match="Timeout"):
        DnbClient(session).lookup_isbn("9783499626029")
