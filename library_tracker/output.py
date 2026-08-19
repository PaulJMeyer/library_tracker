import datetime
from pathlib import Path

from library_tracker.models import Copy, Item


STATUS_LABELS = {
    "ausleihbar": "Ausleihbar",
    "bestellbar": "Bestellbar",
    "entliehen":  "Entliehen",
    "bestellt":   "Bestellt",
    "unbekannt":  "Unbekannt",
}

RESULTS_PATH = Path("results.md")


SUMMARY_STATUSES = ("ausleihbar", "bestellbar")


def format_copy_line(copy: Copy) -> str:
    line = f"{copy['branch']} | {copy['status_text']}"

    due_date = copy["due_date"]
    if due_date and due_date not in copy["status_text"]:
        line += f" (fällig bis {due_date})"

    return line


def format_status_summary(items: list[Item]) -> list[str]:
    lines = []

    for status in SUMMARY_STATUSES:
        titles = [entry["title"] for entry in items if entry["overall_status"] == status]
        label = STATUS_LABELS.get(status, status)

        lines.append(f"{label} ({len(titles)}):")
        if titles:
            for title in titles:
                lines.append(f"  - {title}")
        else:
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
        titles = [entry["title"] for entry in items if entry["overall_status"] == status]
        label = STATUS_LABELS.get(status, status)
        lines.append(f"**{label} ({len(titles)}):**")
        for title in titles:
            lines.append(f"- {title}")
        if not titles:
            lines.append("- (keine)")
        lines.append("")

    lines.append("## Details")
    lines.append("")

    for entry in items:
        label = STATUS_LABELS.get(entry["overall_status"], entry["overall_status"])
        lines.append(f"## [{label}] {entry['title']}")
        for copy in entry["copies"]:
            lines.append(f"- {format_copy_line(copy)}")
        lines.append("")

    return "\n".join(lines)


def write_results_markdown(items: list[Item], path: Path = RESULTS_PATH) -> None:
    path.write_text(format_results_markdown(items), encoding="utf-8")


def print_results_console(items: list[Item]) -> None:
    print("\n=== Übersicht ===")
    for line in format_status_summary(items):
        print(line)

    print("\n=== Details ===")
    for entry in items:
        print(f"\n[{entry['overall_status'].upper()}] {entry['title']}")
        for copy in entry["copies"]:
            print(f"  - {format_copy_line(copy)}")
