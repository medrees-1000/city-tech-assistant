"""The renderer: the only code that writes dates in a calendar answer (step 4a).

It takes calendar rows the selector chose and writes the answer from the row fields alone: the
weekday and date in words from date_start (rendering the printed weekday, and counting it, if the
two disagree), ranges, the event, the source line, and (applies to: ...) when the row has it.
A row with no date (TBA) is "not announced yet" plus the Registrar contact.
"""

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from cta.settings import ROOT

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]  # fmt: skip
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
CALENDAR_FILE = "data/calendar/calendar_events.json"
REGISTRAR_FILE = ROOT / "data" / "processed" / "contacts" / "registrar.json"
NO_CONTACT = "the Registrar's Office (contact details are not loaded)"


@dataclass
class Rendered:
    text: str
    sources: list[dict]  # one chunk-like dict per row, numbered [1], [2] ... in the text
    row_ids: list[str]
    weekday_mismatches: int = 0
    tba_rows: list[str] = field(default_factory=list)


def registrar_contact(path: Path = REGISTRAR_FILE) -> str:
    """Emails and phones from the contact record."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        return ", ".join([*record["emails"], *record["phones"]]) or NO_CONTACT
    except (OSError, ValueError, KeyError):
        return NO_CONTACT


def day_text(d: date, with_year: bool = True) -> str:
    return f"{MONTHS[d.month - 1]} {d.day}" + (f", {d.year}" if with_year else "")


def date_in_words(row: dict) -> tuple[str, bool]:
    """(text, weekday mismatch): 'Friday, November 6, 2026', 'December 15-21, 2026 (Tuesday-Monday)'
    or 'May 28 - June 2, 2027 (...)'. The year comes from date_start, so a Winter row in December is
    2026 and one in January is 2027."""
    start = date.fromisoformat(row["date_start"])
    printed = row["weekday_raw"]
    actual = WEEKDAYS[start.weekday()]
    mismatch = printed.split("-")[0] != actual
    if not row["date_end"]:
        return f"{printed}, {day_text(start)}", mismatch
    end = date.fromisoformat(row["date_end"])
    if (start.year, start.month) == (end.year, end.month):
        span = f"{MONTHS[start.month - 1]} {start.day}-{end.day}, {start.year}"
    elif start.year == end.year:
        span = f"{day_text(start, False)} - {day_text(end)}"
    else:
        span = f"{day_text(start)} - {day_text(end)}"
    return f"{span} ({printed})", mismatch


def provenance(row: dict) -> str:
    pdf = Path(row["source_pdf"]).name
    updated = row["pdf_last_updated"]
    return f"({row['term']} calendar, {pdf}, last updated {updated}; the calendar can change)"


def row_text(row: dict, number: int, contact: str) -> tuple[str, bool]:
    """One row as a sentence ending in its citation number and source line; (text, mismatch)."""
    mismatch = False
    if row["date_start"]:
        when, mismatch = date_in_words(row)
        head = f"{when}: {row['event']}"
    else:
        head = f"{row['event']}: not announced yet"
    text = f"{head} [{number}] {provenance(row)}"
    if row["applies_to"]:
        text += f" (applies to: {row['applies_to']})"
    if not row["date_start"]:
        text += f" Contact the Registrar: {contact}."
    return text, mismatch


def sort_rows(rows: list[dict]) -> list[dict]:
    """By date, rows with no date last, then by id."""
    return sorted(rows, key=lambda r: (r["date_start"] is None, r["date_start"] or "", r["id"]))


def source_chunk(row: dict, text: str) -> dict:
    """The row in the shape the answer and judge code expects of a source chunk."""
    return {
        "id": row["id"], "source_id": row["id"], "kind": "calendar", "source": CALENDAR_FILE,
        "heading_path": f"{row['term']}: {row['event']}", "terms": [row["term"]],
        "last_updated": row["pdf_last_updated"], "text": text, "merged_section_ids": [],
        "similarity": 0.0,
    }  # fmt: skip


def row_line(row: dict, number: int, contact: str) -> tuple[str, bool]:
    """One row of the answer: the date in bold, the event and its citation number (no provenance:
    that is one line per calendar). A row with no date is "not announced yet" plus the Registrar."""
    mismatch = False
    if row["date_start"]:
        when, mismatch = date_in_words(row)
        line = f"**{when}**: {row['event']} [{number}]"
    else:
        line = f"{row['event']}: not announced yet [{number}]"
    if row["applies_to"]:
        line += f" (applies to: {row['applies_to']})"
    if not row["date_start"]:
        line += f" Contact the Registrar: {contact}."
    return line, mismatch


def calendar_key(row: dict) -> tuple[str, str, str]:
    return (row["term"], Path(row["source_pdf"]).name, row["pdf_last_updated"])


def provenance_line(key: tuple[str, str, str]) -> str:
    term, pdf, updated = key
    return f"From the {term} calendar ({pdf}, last updated {updated}). The calendar can change."


def render_rows(rows: list[dict], contact: str, assumed_term: str | None = None) -> Rendered:
    """Rows grouped by calendar (groups in order of their earliest row, rows by date inside one),
    numbered [1], [2] ... in the order shown, one provenance line after each group."""
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for row in sort_rows(rows):
        groups.setdefault(calendar_key(row), []).append(row)
    ordered = [row for group in groups.values() for row in group]
    several = len(ordered) > 1
    sources, mismatches, tba, parts, n = [], 0, [], [], 0
    for key, group in groups.items():
        lines = []
        for row in group:
            n += 1
            line, bad = row_line(row, n, contact)
            lines.append(f"- {line}" if several else line)
            sources.append(source_chunk(row, row_text(row, n, contact)[0]))
            mismatches += bad
            if not row["date_start"]:
                tba.append(row["id"])
        parts += ["\n".join(lines), provenance_line(key)]
    if assumed_term:
        parts.insert(0, f"Assuming the current term, {assumed_term}.")
    return Rendered("\n\n".join(parts), sources, [r["id"] for r in ordered], mismatches, tba)


def abstain_text(reason: str, contact: str) -> str:
    """The abstention line the eval runner recognises ('ABSTAIN:') with the Registrar contact."""
    return f"ABSTAIN: {reason} Contact the Registrar: {contact}."
