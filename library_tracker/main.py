from library_tracker.client import get, build_url
from library_tracker.models import Item
from library_tracker.login import login
from library_tracker.library_parser import parse_availability_page
from library_tracker.wishlist import get_all_availability_links
from library_tracker.account import get_account_page, parse_loans
from library_tracker.output import print_results_console, print_loans_console, write_results_markdown
from dotenv import load_dotenv

load_dotenv()

STATUS_ORDER = {
    "ausleihbar": 0,
    "bestellbar": 1,
    "entliehen":  2,
    "bestellt":   3,
    "unbekannt":  4,
}

EXEMPLAR_TAB_URL = build_url(
    "/webOPACClient/singleHit.do"
    "?methodToCall=activateTab"
    "&tab=showExemplarMemorizeActive"
)


def main() -> None:
    session = login()
 
    links = get_all_availability_links(session)
    print(f"Gefundene Medien: {len(links)}")
 
    items: list[Item] = []
 
    for link in links:
        get(session, link)
        response = get(session, EXEMPLAR_TAB_URL)
        item = parse_availability_page(response.text)
        items.append(item)
 
    items = sorted(
        items,
        key=lambda item: STATUS_ORDER.get(item["overall_status"], 99)
    )
 
    print_results_console(items)
    write_results_markdown(items)
 
    account_html = get_account_page(session)
    loans = parse_loans(account_html)
    print_loans_console(loans)
 
 
if __name__ == "__main__":
    main()