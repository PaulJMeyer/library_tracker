from __future__ import annotations

import datetime
import html
import re
from pathlib import Path

from library_tracker.models import (
    AvailabilitySnapshot,
    Copy,
    Item,
    Loan,
    MatchReportRow,
    ScrapeResult,
)

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


TELEGRAM_HEADINGS = {
    "ausleihbar": "Ausleihbar in der Zentralbibliothek",
    "bestellbar": "Bestellbar aus anderen Zweigstellen",
}
BRANCH_PREFIX_PATTERN = re.compile(r"^\d+-")


def _branch_name(branch: str) -> str:
    """'21-Vahr / Geschichte' -> 'Vahr'."""
    return BRANCH_PREFIX_PATTERN.sub("", branch.split("/", 1)[0].strip())


def _shelf(branch: str) -> str:
    """'10-Zentralbibliothek / 2.OG Dom-Flügel' -> '2.OG Dom-Flügel'."""
    parts = branch.split("/", 1)
    return parts[1].strip() if len(parts) == 2 else ""


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def format_telegram_item(item: Item) -> str:
    title = html.escape(item["title"].replace("¬", ""))
    available = [copy for copy in item["copies"] if copy["status"] == "ausleihbar"]
    if item["overall_status"] == "ausleihbar":
        places = _unique([_shelf(c["branch"]) for c in available if c["is_central"]])
    else:
        places = _unique(
            [_branch_name(c["branch"]) for c in item["copies"]
             if not c["is_central"] and c["status"] in {"ausleihbar", "bestellbar"}]
        )
    suffix = f" <i>({html.escape(', '.join(places))})</i>" if places else ""
    return f"• {title}{suffix}"


def format_telegram_message(
    items: list[Item],
    today: datetime.date | None = None,
) -> str:
    today = today or datetime.date.today()
    lines = [f"<b>📚 Merkliste – {today.strftime('%d.%m.%Y')}</b>"]
    for status in SUMMARY_STATUSES:
        matching = [item for item in items if item["overall_status"] == status]
        lines.extend(["", f"<b>{TELEGRAM_HEADINGS[status]} ({len(matching)})</b>"])
        lines.extend(format_telegram_item(item) for item in matching)
        if not matching:
            lines.append("– keine –")
    return "\n".join(lines)


CANDIDATE_SOURCE_LABELS = {
    "reado": "READO-ISBN",
    "openlibrary_confirmed": "deutsche Druckausgabe",
    "openlibrary_unknown": "deutsche Ausgabe, Format unbekannt",
    "openlibrary_english": "englische Ausgabe",
}


def format_match_report(rows: list[MatchReportRow]) -> str:
    lines = [f"Abgleich READO-Wunschliste: {len(rows)} Bücher", ""]
    for row in rows:
        lines.append(f"{row['isbn13']} | {row['title']}")
        lines.append(f"  Metadaten: {row['metadata']} | ISBN-Kandidaten: {row['candidate_count']}")
        if row["match"] is not None:
            source = CANDIDATE_SOURCE_LABELS.get(row["match"]["source"], row["match"]["source"])
            lines.append(f"  Katalog: gefunden mit {row['match']['isbn']} ({source})")
        elif row["catalog_error"]:
            lines.append(f"  Katalog: Suche fehlgeschlagen ({row['catalog_error']})")
        elif row["catalog_checked"]:
            lines.append("  Katalog: nicht gefunden")
        if row["reason"] and row["match"] is None:
            lines.append(f"  Hinweis: {row['reason']}")
        lines.append("")

    found = sum(row["match"] is not None for row in rows)
    lines.append("Zusammenfassung:")
    checked = [row for row in rows if row["catalog_checked"]]
    failed = sum(bool(row["catalog_error"]) for row in rows)
    if checked or failed:
        lines.append(f"  Im Katalog gefunden: {found}/{len(rows)}")
    if failed:
        lines.append(f"  Katalogsuche fehlgeschlagen: {failed}")
    reasons: dict[str, int] = {}
    for row in rows:
        if row["match"] is None and row["reason"]:
            reasons[row["reason"]] = reasons.get(row["reason"], 0) + 1
    for reason, count in sorted(reasons.items(), key=lambda item: -item[1]):
        lines.append(f"  {count}x {reason}")
    return "\n".join(lines)
