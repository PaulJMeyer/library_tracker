from library_tracker.wishlist import extract_memorize_page, remove_entries, get_all_memorize_pages
from unittest.mock import MagicMock, patch, ANY


def test_extract_memorize_page_finds_entry_and_hidden_fields():
    html = """
    <html><body>
        <form id="MemorizeBean">
            <input type="hidden" name="selectedMemorizeList" value="">
            <input type="hidden" name="displayType" value="short">
            <input type="hidden" name="curPos" value="21">
            <input type="hidden" name="CSId" value="test-cs-id-123">

            <div class="row border-bottom py-2">
                <div class="col-auto my-2 order-1">
                    <input type="checkbox" value="test-uuid-123"
                           name="selectedMemListentries[0]"
                           id="selectedMemListentries_0">
                </div>
                <div class="col-12 col-md-9 my-2 order-4 order-md-3">
                    <a href="/webOPACClient/availability.do?methodToCall=runMemorizeAvailability&amp;curPos=21&amp;activeTab=1">
                        zum Dokument
                    </a>
                </div>
            </div>
        </form>
    </body></html>
    """

    page = extract_memorize_page(html, cur_pos=21)

    assert page["cur_pos"] == "21"
    assert page["cs_id"] == "test-cs-id-123"
    assert page["display_type"] == "short"
    assert page["selected_memorize_list"] == ""
    assert page["entries"] == [{
        "uuid": "test-uuid-123",
        "availability_link": "https://opac.stabi-hb.de/webOPACClient/availability.do?methodToCall=runMemorizeAvailability&curPos=21&activeTab=1",
    }]


def test_extract_memorize_page_multiple_inputs():
    html = """
        <html><body>
            <form id="MemorizeBean">
                <input type="hidden" name="selectedMemorizeList" value="">
                <input type="hidden" name="displayType" value="short">
                <input type="hidden" name="curPos" value="21">
                <input type="hidden" name="CSId" value="test-cs-id-123">
    
                <div class="row border-bottom py-2">
                    <div class="col-auto my-2 order-1">
                        <input type="checkbox" value="test-uuid-123"
                               name="selectedMemListentries[0]"
                               id="selectedMemListentries_0">
                    </div>
                
                    <div class="col-12 col-md-9 my-2 order-4 order-md-3">
                        <a href="/webOPACClient/availability.do?methodToCall=runMemorizeAvailability&amp;curPos=21&amp;activeTab=1">
                            zum Dokument
                        </a>
                    </div>
                </div>

                <div class="row border-bottom py-2">
                    <div class="col-auto my-2 order-1">
                        <input type="checkbox" value="test-uuid-987"
                               name="selectedMemListentries[0]"
                               id="selectedMemListentries_0">
                    </div>
                
                    <div class="col-12 col-md-9 my-2 order-4 order-md-3">
                        <a href="/webOPACClient/availability.do?methodToCall=runMemorizeAvailability&amp;curPos=21&amp;activeTab=2">
                            zum Dokument
                        </a>
                    </div>
                </div>

            </form>
        </body></html>
        """

    page = extract_memorize_page(html, cur_pos=21)

    assert page["entries"] == [
        {"uuid": "test-uuid-123",
        "availability_link": "https://opac.stabi-hb.de/webOPACClient/availability.do?methodToCall=runMemorizeAvailability&curPos=21&activeTab=1",
        },
        {"uuid": "test-uuid-987",
        "availability_link": "https://opac.stabi-hb.de/webOPACClient/availability.do?methodToCall=runMemorizeAvailability&curPos=21&activeTab=2",
        }
    ]


def test_extract_memorize_page_no_inputs():
    html = """
        <html><body>
            <form id="MemorizeBean">
                <input type="hidden" name="selectedMemorizeList" value="">
                <input type="hidden" name="displayType" value="short">
                <input type="hidden" name="curPos" value="21">
                <input type="hidden" name="CSId" value="test-cs-id-123">

                <div class="row border-bottom py-2">
                    
                </div>
            </form>
        </body></html>
        """

    page = extract_memorize_page(html, cur_pos=21)

    assert page["cur_pos"] == "21"
    assert page["cs_id"] == "test-cs-id-123"
    assert page["display_type"] == "short"
    assert page["selected_memorize_list"] == ""
    assert page["entries"] == []


def test_extract_memorize_page_no_link():
    html = """
    <html><body>
        <form id="MemorizeBean">
            <input type="hidden" name="selectedMemorizeList" value="">
            <input type="hidden" name="displayType" value="short">
            <input type="hidden" name="curPos" value="21">
            <input type="hidden" name="CSId" value="test-cs-id-123">

            <div class="row border-bottom py-2">
                <div class="col-auto my-2 order-1">
                    <input type="checkbox" value="test-uuid-123"
                           name="selectedMemListentries[0]"
                           id="selectedMemListentries_0">
                </div>
                <div class="col-12 col-md-9 my-2 order-4 order-md-3">
                </div>
            </div>
        </form>
    </body></html>
    """

    page = extract_memorize_page(html, cur_pos=21)

    assert page["cur_pos"] == "21"
    assert page["cs_id"] == "test-cs-id-123"
    assert page["display_type"] == "short"
    assert page["selected_memorize_list"] == ""
    assert page["entries"] == []


def test_extract_memorize_page_no_memorize_bean():
    html = """
        <html><body>
            <form id="MemorizeBanana">
                <input type="hidden" name="selectedMemorizeList" value="">
                <input type="hidden" name="displayType" value="short">
                <input type="hidden" name="curPos" value="21">
                <input type="hidden" name="CSId" value="test-cs-id-123">

                <div class="row border-bottom py-2">
                    
                </div>
            </form>
        </body></html>
        """

    page = extract_memorize_page(html, cur_pos=21)

    assert page["cur_pos"] == "21"
    assert page["cs_id"] == ""
    assert page["display_type"] == ""
    assert page["selected_memorize_list"] == ""
    assert page["entries"] == []


@patch("library_tracker.wishlist.get")
def test_remove_entries_sends_correct_params(mock_get):
    mock_get.return_value = MagicMock(status_code=200)

    page = {
        "cur_pos": "21",
        "cs_id": "test-cs-id-123",
        "display_type": "short",
        "selected_memorize_list": "",
        "entries": [],
    }

    result = remove_entries(session=MagicMock(), page=page, uuids=["uuid-1", "uuid-2"])

    assert result is True

    called_args, called_kwargs = mock_get.call_args
    params = called_kwargs["params"]

    assert params["methodToCall"] == "deleteSelectedEntries"
    assert params["CSId"] == "test-cs-id-123"
    assert params["curPos"] == "21"
    assert params["displayType"] == "short"
    assert params["selectedMemorizeList"] == ""
    assert params["selectedMemListentries[0]"] == "uuid-1"
    assert params["selectedMemListentries[1]"] == "uuid-2"


@patch("library_tracker.wishlist.get")
def test_remove_entries_no_uuids_skips_request(mock_get):
    page = {
        "cur_pos": "21",
        "cs_id": "test-cs-id-123",
        "display_type": "short",
        "selected_memorize_list": "",
        "entries": [],
    }

    result = remove_entries(session=MagicMock(), page=page, uuids=[])

    mock_get.assert_not_called()
    assert result is True


@patch("library_tracker.wishlist.get")
def test_remove_entries_returns_false_on_error_status(mock_get):
    mock_get.return_value = MagicMock(status_code=404)

    page = {
        "cur_pos": "21",
        "cs_id": "test-cs-id-123",
        "display_type": "short",
        "selected_memorize_list": "",
        "entries": [],
    }

    result = remove_entries(session=MagicMock(), page=page, uuids=["uuid-1"])

    assert result is False


@patch("library_tracker.wishlist.get_wishlist_page")
def test_get_all_memorize_pages_single_page(mock_get_wishlist_page):
    html_with_one_entry = """
    <html><body>
        <form id="MemorizeBean">
            <input type="hidden" name="selectedMemorizeList" value="">
            <input type="hidden" name="displayType" value="short">
            <input type="hidden" name="curPos" value="1">
            <input type="hidden" name="CSId" value="test-cs-id">

            <div class="row border-bottom py-2">
                <div class="col-auto my-2 order-1">
                    <input type="checkbox" value="uuid-a" name="selectedMemListentries[0]">
                </div>
                <div class="col-12 col-md-9 my-2 order-4 order-md-3">
                    <a href="/webOPACClient/availability.do?methodToCall=runMemorizeAvailability&amp;curPos=1&amp;activeTab=1"></a>
                </div>
            </div>
        </form>
    </body></html>
    """

    mock_get_wishlist_page.return_value = html_with_one_entry

    pages = get_all_memorize_pages(session=MagicMock())

    assert len(pages) == 1
    assert pages[0]["entries"] == [{
        "uuid": "uuid-a",
        "availability_link": "https://opac.stabi-hb.de/webOPACClient/availability.do?methodToCall=runMemorizeAvailability&curPos=1&activeTab=1",
    }]
    mock_get_wishlist_page.assert_called_once_with(ANY, 1)


@patch("library_tracker.wishlist.get_wishlist_page")
def test_get_all_memorize_pages_empty_wishlist(mock_get_wishlist_page):
    html_empty = """
    <html><body>
        <form id="MemorizeBean">
            <input type="hidden" name="selectedMemorizeList" value="">
            <input type="hidden" name="displayType" value="short">
            <input type="hidden" name="curPos" value="1">
            <input type="hidden" name="CSId" value="test-cs-id">
        </form>
    </body></html>
    """

    mock_get_wishlist_page.return_value = html_empty

    pages = get_all_memorize_pages(session=MagicMock())

    assert pages == []
    mock_get_wishlist_page.assert_called_once()


def _build_page_html(cur_pos: int, entry_count: int) -> str:
    entries_html = "".join(f"""
        <div class="row border-bottom py-2">
            <div class="col-auto my-2 order-1">
                <input type="checkbox" value="uuid-{cur_pos}-{i}" name="selectedMemListentries[{i}]">
            </div>
            <div class="col-12 col-md-9 my-2 order-4 order-md-3">
                <a href="/webOPACClient/availability.do?methodToCall=runMemorizeAvailability&amp;curPos={cur_pos}&amp;activeTab={i}"></a>
            </div>
        </div>
    """ for i in range(entry_count))

    return f"""
    <html><body>
        <form id="MemorizeBean">
            <input type="hidden" name="selectedMemorizeList" value="">
            <input type="hidden" name="displayType" value="short">
            <input type="hidden" name="curPos" value="{cur_pos}">
            <input type="hidden" name="CSId" value="test-cs-id">
            {entries_html}
        </form>
    </body></html>
    """


@patch("library_tracker.wishlist.get_wishlist_page")
def test_get_all_memorize_pages_multiple_full_pages(mock_get_wishlist_page):
    page_1_html = _build_page_html(cur_pos=1, entry_count=10)
    page_2_html = _build_page_html(cur_pos=11, entry_count=3)

    mock_get_wishlist_page.side_effect = [page_1_html, page_2_html]

    pages = get_all_memorize_pages(session=MagicMock())

    assert len(pages) == 2
    assert len(pages[0]["entries"]) == 10
    assert len(pages[1]["entries"]) == 3
    assert mock_get_wishlist_page.call_count == 2
    mock_get_wishlist_page.assert_any_call(ANY, 1)
    mock_get_wishlist_page.assert_any_call(ANY, 11)