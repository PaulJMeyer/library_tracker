from library_tracker.wishlist import extract_availability_links
 
 
def test_extract_availability_links_finds_matching_link():
    html = """
    <html><body>
        <a href="/webOPACClient/singleHit.do?runMemorizeAvailability=1">Details</a>
    </body></html>
    """
    links = extract_availability_links(html)
    assert links == ["https://opac.stabi-hb.de/webOPACClient/singleHit.do?runMemorizeAvailability=1"]
 
 
def test_extract_availability_links_ignores_unrelated_links():
    html = """
    <html><body>
        <a href="/webOPACClient/start.do?methodToCall=logout">Logout</a>
        <a href="/webOPACClient/help.do">Hilfe</a>
    </body></html>
    """
    links = extract_availability_links(html)
    assert links == []
 
 
def test_extract_availability_links_finds_multiple_links():
    html = """
    <html><body>
        <a href="/webOPACClient/singleHit.do?runMemorizeAvailability=1">Details 1</a>
        <a href="/webOPACClient/help.do">Hilfe</a>
        <a href="/webOPACClient/singleHit.do?runMemorizeAvailability=2">Details 2</a>
    </body></html>
    """
    links = extract_availability_links(html)
    assert links == [
        "https://opac.stabi-hb.de/webOPACClient/singleHit.do?runMemorizeAvailability=1",
        "https://opac.stabi-hb.de/webOPACClient/singleHit.do?runMemorizeAvailability=2",
    ]
 
 
def test_extract_availability_links_no_anchor_tags():
    html = "<html><body><p>keine Links hier</p></body></html>"
    links = extract_availability_links(html)
    assert links == []
 
 
def test_extract_availability_links_empty_html():
    assert extract_availability_links("") == []