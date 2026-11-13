from __future__ import annotations

import datetime
from pathlib import Path

from library_tracker.models import AvailabilitySnapshot, Copy, Item, Loan, ScrapeResult

STATUS_LABELS = {
    "ausleihbar": "Ausleihbar",
    "bestellbar": "Bestellbar",
    "entliehen": "Entliehen",
    "bestellt": "Bestellt",
    "unbekannt": "Unbekannt",
}
RESULTS_PATH = Path("results.md")
SUMMARY_STATUSES = ("ausleihbar", "bestellbar")


def format_copy_line(copy: Copy) -> str:
    line = f"{copy['branch']} | {copy['status_text']}"
    if copy["due_date"] and copy["due_date"] not in copy["status_text"]:
        line += f" (fällig bis {copy['due_date']})"
    return line


def format_status_summary(items: list[Item]) -> list[str]:
    lines: list[str] = []
    for status in SUMMARY_STATUSES:
        titles = [item["title"] for item in items if item["overall_status"] == status]
        lines.append(f"{STATUS_LABELS[status]} ({len(titles)}):")
        lines.extend(f"  - {title}" for title in titles)
        if not titles:
            lines.append("  - (keine)")
    return lines


def format_results_markdown(items: list[Item]) -> str:
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Merkliste – Verfügbarkeit",
        "",
        f"Zuletzt aktualisiert: {timestamp}",
        "",
        "## Übersicht",
        "",
    ]

    for status in SUMMARY_STATUSES:
        titles = [item["title"] for item in items if item["overall_status"] == status]
        lines.append(f"**{STATUS_LABELS[status]} ({len(titles)}):**")
        lines.extend(f"- {title}" for title in titles)
        if not titles:
            lines.append("- (keine)")
        lines.append("")

    lines.extend(["## Details", ""])
    for item in items:
        lines.append(f"## [{STATUS_LABELS[item['overall_status']]}] {item['title']}")
        lines.extend(f"- {format_copy_line(copy)}" for copy in item["copies"])
        lines.append("")
    return "\n".join(lines)


def write_results_markdown(items: list[Item], path: Path = RESULTS_PATH) -> None:
    path.write_text(format_results_markdown(items), encoding="utf-8")


def print_results_console(items: list[Item]) -> None:
    print("\n=== Übersicht ===")
    for line in format_status_summary(items):
        print(line)

    print("\n=== Details ===")
    for item in items:
        print(f"\n[{item['overall_status'].upper()}] {item['title']}")
        for copy in item["copies"]:
            print(f"  - {format_copy_line(copy)}")


def print_loans_console(loans: list[Loan]) -> None:
    print(f"\n=== Kontoübersicht: Ausgeliehene Medien ({len(loans)}) ===")
    for loan in loans:
        print(f"\n{loan['title']} ({loan['author']})")
        print(f"  {loan['signature']} | {loan['branch']}")
        print(
            f"  Ausgeliehen seit: {loan['borrowed_since'] or '?'} | "
            f"Fällig: {loan['due_date'] or '?'}"
        )
        print(f"  {loan['renewal_note']}")


def print_scrape_result(result: ScrapeResult) -> None:
    print(f"Gefundene Medien: {result['total_entries']}")
    if result["removed_count"]:
        print(
            f"Entfernt: {result['removed_count']} Titel "
            f"(Erfolg: {result['removal_success']})"
        )
    print_results_console(result["items"])
    write_results_markdown(result["items"])
    print_loans_console(result["loans"])


def format_history_line(snapshot: AvailabilitySnapshot) -> str:
    due_suffix = f" | due: {snapshot['due_date']}" if snapshot["due_date"] else ""
    return (
        f"{snapshot['checked_at']} | {snapshot['status']} | "
        f"{snapshot['status_text']}{due_suffix}"
    )
