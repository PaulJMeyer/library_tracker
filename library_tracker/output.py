from __future__ import annotations

import datetime
import html
import re
from pathlib import Path

from library_tracker.clients.openlibrary import strip_sort_markers
from library_tracker.titles import merkliste_title_key
from library_tracker.parsers.library import is_lendable_location, is_orderable
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
STATUS_RANK = {status: rank for rank, status in enumerate(STATUS_LABELS)}
NUMBER_PATTERN = re.compile(r"\d+")


def _book_key(title: str) -> tuple[str, tuple[str, ...]]:
    """Same title (without subtitle and leading article) and same numbers (e.g.
    'Band 2') means the same book."""
    return merkliste_title_key(title), tuple(NUMBER_PATTERN.findall(strip_sort_markers(title)))


def merge_duplicate_items(items: list[Item]) -> list[Item]:
    """Show a book once when several editions or copies of it are on the Merkliste.

    The merged entry takes the best status of its editions (Ausleihbar before
    Bestellbar), the title and page count of that edition, and the copies of all
    editions, so the overview lists every shelf or branch it can be fetched from.
    """
    groups: dict[tuple[str, tuple[str, ...]], list[Item]] = {}
    for item in items:
        groups.setdefault(_book_key(item["title"]), []).append(item)

    merged: list[Item] = []
    for group in groups.values():
        if len(group) == 1:
            merged.append(group[0])
            continue
        best = min(group, key=lambda item: STATUS_RANK.get(item["overall_status"], 99))
        copies = best["copies"] + [c for item in group if item is not best for c in item["copies"]]
        merged_item: Item = {
            "title": best["title"],
            "overall_status": best["overall_status"],
            "copies": copies,
        }
        if "pages" in best:
            merged_item["pages"] = best["pages"]
        merged.append(merged_item)
    return merged


def format_copy_line(copy: Copy) -> str:
    line = f"{copy['branch']} | {copy['status_text']}"
    if copy["due_date"] and copy["due_date"] not in copy["status_text"]:
        line += f" (fällig bis {copy['due_date']})"
    return line


def format_status_summary(items: list[Item]) -> list[str]:
    items = merge_duplicate_items(items)
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
        titles = [
            item["title"] for item in merge_duplicate_items(items) if item["overall_status"] == status
        ]
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
    title = html.escape(strip_sort_markers(item["title"]))
    available = [copy for copy in item["copies"] if copy["status"] == "ausleihbar"]
    if item["overall_status"] == "ausleihbar":
        places = _unique([_shelf(c["branch"]) for c in available if c["is_central"] and is_lendable_location(c)])
    else:
        places = _unique([_branch_name(c["branch"]) for c in item["copies"] if is_orderable(c)])
    pages = f", {item['pages']} S." if item.get("pages") else ""
    suffix = f" <i>({html.escape(', '.join(places))})</i>" if places else ""
    return f"• {title}{pages}{suffix}"


def _format_status_sections(items: list[Item]) -> list[str]:
    lines: list[str] = []
    for status in SUMMARY_STATUSES:
        matching = [item for item in items if item["overall_status"] == status]
        lines.extend(["", f"<b>{TELEGRAM_HEADINGS[status]} ({len(matching)})</b>"])
        lines.extend(format_telegram_item(item) for item in matching)
        if not matching:
            lines.append("– keine –")
    return lines


def format_telegram_message(
    items: list[Item],
    today: datetime.date | None = None,
    *,
    added_titles: list[str] | None = None,
    warnings: list[str] | None = None,
    review_titles: list[str] | None = None,
    removed_titles: list[str] | None = None,
    second_wishlist_titles: list[str] | None = None,
    own_wishlist_titles: list[str] | None = None,
    second_wishlist_heading: str = "Von der zweiten Wunschliste:",
) -> str:
    """Telegram overview of available Merkliste titles.

    With `second_wishlist_titles` (catalog titles of books on the second READO
    wishlist) those titles get their own section under `second_wishlist_heading`.
    They stay in the main section too when they are in `own_wishlist_titles`."""
    today = today or datetime.date.today()
    lines = [f"<b>📚 Merkliste – {today.strftime('%d.%m.%Y')}</b>"]
    items = merge_duplicate_items(items)
    own_items = items
    second_items: list[Item] = []
    if second_wishlist_titles is not None:
        second = {merkliste_title_key(title) for title in second_wishlist_titles}
        own = {merkliste_title_key(title) for title in own_wishlist_titles or []}
        # Books on both wishlists are listed in both sections.
        own_items = [
            item
            for item in items
            if merkliste_title_key(item["title"]) in own or merkliste_title_key(item["title"]) not in second
        ]
        second_items = [item for item in items if merkliste_title_key(item["title"]) in second]
    lines.extend(_format_status_sections(own_items))
    if second_wishlist_titles is not None:
        lines.extend(["", f"<b>{html.escape(second_wishlist_heading)}</b>"])
        lines.extend(_format_status_sections(second_items))
    for heading, titles in (
        ("Neu auf der Merkliste", added_titles),
        ("Von der Merkliste entfernt", removed_titles),
        ("Bitte prüfen, nicht hinzugefügt", review_titles),
    ):
        # Several editions of one book: listed once.
        unique = _unique([strip_sort_markers(title) for title in titles or []])
        if unique:
            lines.extend(["", f"<b>{heading} ({len(unique)})</b>"])
            lines.extend(f"• {html.escape(title)}" for title in unique)
    if warnings:
        lines.extend(["", "⚠️ <i>" + html.escape("; ".join(warnings)) + "</i>"])
    return "\n".join(lines)


CANDIDATE_SOURCE_LABELS = {
    "reado": "READO-ISBN",
    "openlibrary_confirmed": "deutsche Druckausgabe",
    "openlibrary_unknown": "deutsche Ausgabe, Format unbekannt",
    "openlibrary_english": "englische Ausgabe",
    "dnb": "deutsche Druckausgabe laut DNB",
}


MEMORIZE_STATUS_LABELS = {
    "added": "von library-tracker hinzugefügt",
    "already_listed": "stand schon drauf",
    "failed": "Hinzufügen fehlgeschlagen, wird erneut versucht",
    "needs_review": "nicht hinzugefügt: Einzelband einer mehrbändigen Ausgabe, bitte prüfen",
}


def format_match_report(rows: list[MatchReportRow]) -> str:
    lines = [f"Abgleich READO-Wunschliste: {len(rows)} Bücher", ""]
    for row in rows:
        lines.append(f"{row['isbn13']} | {strip_sort_markers(row['title'])}")
        lines.append(
            f"  Metadaten: {row['metadata']} | ISBN-Kandidaten: {row['candidate_count']}"
            f" | im Katalog geprüft: {row['searched_count']}"
        )
        if row["match"] is not None:
            source = CANDIDATE_SOURCE_LABELS.get(row["match"]["source"], row["match"]["source"])
            lines.append(f"  Katalog: gefunden mit {row['match']['isbn']} ({source})")
            if row["memorize_status"]:
                lines.append(f"  Merkliste: {MEMORIZE_STATUS_LABELS.get(row['memorize_status'], row['memorize_status'])}")
            else:
                lines.append("  Merkliste: noch nicht eingetragen (merkliste-add)")
        elif row["searched_count"] < row["candidate_count"]:
            lines.append(
                f"  Katalog: noch nicht gefunden, {row['candidate_count'] - row['searched_count']}"
                " ISBN(s) offen (match-books)"
            )
        else:
            lines.append("  Katalog: nicht gefunden")
        if row["reason"] and row["match"] is None:
            lines.append(f"  Hinweis: {row['reason']}")
        lines.append("")

    found = sum(row["match"] is not None for row in rows)
    pending = sum(
        row["match"] is None and row["searched_count"] < row["candidate_count"] for row in rows
    )
    lines.append("Zusammenfassung:")
    lines.append(f"  Im Katalog gefunden: {found}/{len(rows)}")
    if pending:
        lines.append(f"  Noch ISBNs offen: {pending} Bücher")
    reasons: dict[str, int] = {}
    for row in rows:
        if row["match"] is None and row["reason"]:
            reasons[row["reason"]] = reasons.get(row["reason"], 0) + 1
    for reason, count in sorted(reasons.items(), key=lambda item: -item[1]):
        lines.append(f"  {count}x {reason}")
    return "\n".join(lines)
