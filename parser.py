from bs4 import BeautifulSoup


def parse_availability_page(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    headings = [
        h.get_text(" ", strip=True)
        for h in soup.find_all(["h1", "h2", "h3"])
    ]

    title = None
    for heading in headings:
        if heading not in [
            "Verfügbarkeit aus Merkliste",
            "Menu Closed Menu Open Exemplare",
            "Menu Closed Menu Open Bestellung (kostenlos)/Vormerkung (1,- Euro)",
            "Menu Closed Menu Open mehr zum Titel",
        ]:
            title = heading
            break

    page_text = soup.get_text(" ", strip=True)

    status = "unbekannt"
    if "entliehen" in page_text:
        status = "entliehen"
    elif "ausleihbar" in page_text:
        status = "ausleihbar"
    elif "bestellbar" in page_text:
        status = "bestellbar"
    elif "verfügbar" in page_text:
        status = "verfügbar"

    return {
        "title": title,
        "status": status,
    }