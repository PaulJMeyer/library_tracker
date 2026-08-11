import datetime
from pathlib import Path

from library_tracker.client import get, build_url
from library_tracker.models import Item
from library_tracker.login import login
from library_tracker.library_parser import parse_availability_page
from library_tracker.wishlist import get_all_availability_links
from dotenv import load_dotenv

load_dotenv()

STATUS_ORDER = {
    "ausleihbar": 0,
    "bestellbar": 1,
    "entliehen":  2,
    "bestellt":   3,
    "unbekannt":  4,
}

STATUS_LABELS = {
    "ausleihbar": "Ausleihbar",
    "bestellbar": "Bestellbar",
    "entliehen":  "Entliehen",
    "bestellt":   "Bestellt",
    "unbekannt":  "Unbekannt",
}

EXEMPLAR_TAB_URL = build_url(
    "/webOPACClient/singleHit.do"
    "?methodToCall=activateTab"
    "&tab=showExemplarMemorizeActive"
)

RESULTS_PATH = Path("results.md")


def format_results_markdown(items: list[Item]) -> str:
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Merkliste – Verfügbarkeit",
        "",
        f"Zuletzt aktualisiert: {timestamp}",
        "",
    ]

    for entry in items:
        label = STATUS_LABELS.get(entry["overall_status"], entry["overall_status"])
        lines.append(f"## [{label}] {entry['title']}")
        for copy in entry["copies"]:
            lines.append(f"- {copy['branch']} | {copy['status_text']}")
        lines.append("")

    return "\n".join(lines)


def write_results_markdown(items: list[Item], path: Path = RESULTS_PATH) -> None:
    path.write_text(format_results_markdown(items), encoding="utf-8")


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

    for entry in items:
        print(f"\n[{entry['overall_status'].upper()}] {entry['title']}")

        for copy in entry["copies"]:
            print(f"  - {copy['branch']} | {copy['status_text']}")

    write_results_markdown(items)


if __name__ == "__main__":
    main()
