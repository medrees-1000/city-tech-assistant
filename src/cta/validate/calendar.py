"""Automatic calendar checks from docs/data-validation.md ("Calendar").

Run: uv run python -m cta.parse.calendar_build   (builds the table, then runs these checks)
Dates are never changed to make a check pass: every problem is reported as a finding.
"""

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from cta.parse.calendar import Extraction, joined_lines, weekday_check
from cta.validate.findings import Finding, squash

REQUIRED = ("id", "term", "event", "date_raw", "weekday_raw", "source_pdf", "source_page")


def check_required_fields(events: list[dict]) -> list[Finding]:
    """Every row has an id, term, event, source, page and last-updated date, and a date or TBA."""
    found = []
    for e in events:
        missing = [f for f in REQUIRED if e.get(f) in (None, "")]
        if not e.get("pdf_last_updated"):
            missing.append("pdf_last_updated")
        if e.get("verified") not in (True, False):
            missing.append("verified")
        if e.get("date_raw", "").upper() == "TBA":
            if e.get("date_start") or e.get("date_end"):
                missing.append("TBA row must have null dates")
        else:
            try:
                date.fromisoformat(e["date_start"])
            except (TypeError, ValueError):
                missing.append("date_start")
        if e.get("source_page") is not None and (
            not isinstance(e["source_page"], int) or e["source_page"] < 1
        ):
            missing.append("source_page must be a page number")
        if missing:
            found.append(
                Finding("required_fields", "fail", f"missing or invalid: {missing}", e.get("id"))
            )
    ids = Counter(e.get("id") for e in events)
    found += [Finding("ids", "fail", f"id used {n} times", i) for i, n in ids.items() if n > 1]
    return found


def check_dates_in_window(
    events: list[dict], windows: dict[str, tuple[date, date]]
) -> list[Finding]:
    """Every date falls inside its term's window; an end date is not before its start date."""
    found = []
    for e in events:
        if not e.get("date_start"):
            continue
        low, high = windows[e["term"]]
        start = date.fromisoformat(e["date_start"])
        end = date.fromisoformat(e["date_end"]) if e.get("date_end") else start
        if end < start:
            found.append(Finding("date_range", "fail", f"{end} is before {start}", e["id"]))
        for d in sorted({start, end}):
            if not low <= d <= high:
                msg = f"{d} is outside the {e['term']} window {low}..{high}"
                found.append(Finding("date_window", "fail", msg, e["id"]))
    return found


def check_weekdays(events: list[dict]) -> list[Finding]:
    """The printed weekday matches the resolved date. Mismatches are listed, never corrected."""
    found = []
    for e in events:
        result = weekday_check(e["date_start"], e["date_end"], e["weekday_raw"])
        if result.startswith("MISMATCH"):
            msg = f"{e['date_raw']} / {e['weekday_raw']}: {result}"
            found.append(Finding("weekday", "fail", msg, e["id"]))
    return found


def check_duplicates(events: list[dict]) -> list[Finding]:
    """No two rows with the same term, date, day and event text."""
    keys = Counter((e["term"], e["date_raw"], e["weekday_raw"], e["event"]) for e in events)
    return [
        Finding("duplicates", "fail", f"{n} identical rows: {key[1]} {key[3][:50]!r}", key[0])
        for key, n in keys.items()
        if n > 1
    ]


def check_term_markers(events: list[dict], term: str) -> list[Finding]:
    """The PDF's own "Start of <term>" and "End of <term>" events exist once, start before end."""
    found = []
    dates = {}
    for word in ("Start", "End"):
        rows = [e for e in events if e["term"] == term
                and re.match(rf"^{word} of {term}\b", e["event"], re.I)]  # fmt: skip
        if len(rows) != 1:
            found.append(
                Finding("term_markers", "fail", f"{len(rows)} '{word} of {term}' events", term)
            )
        else:
            dates[word] = rows[0]["date_start"]
    if len(dates) == 2 and dates["Start"] > dates["End"]:
        found.append(
            Finding(
                "term_markers", "fail", f"start {dates['Start']} after end {dates['End']}", term
            )
        )
    return found


def check_against_pdf(events: list[dict], ex: Extraction) -> list[Finding]:
    """Nothing dropped and nothing extra, compared with the PDF's own text.

    1. Every character inside the table outline on the page (found without using rows or cells),
       minus the header row, equals the characters of the events (each row's date and day once).
    2. The event texts, in order, are exactly the printed event lines of the rows, in order."""
    found = []
    term_events = [e for e in events if e["term"] == ex.term]
    produced: Counter = Counter()
    index = 0
    for row in ex.rows:
        groups = joined_lines(row.events, ex.edge)
        if groups and index < len(term_events):
            first = term_events[index]
            produced.update(squash(first["date_raw"] + first["weekday_raw"]))
        index += len(groups)
    for e in term_events:
        produced.update(squash(e["event"]))
    expected = Counter(ex.body_chars) - Counter(ex.header_chars)
    missing, extra = expected - produced, produced - expected
    if missing:
        found.append(
            Finding(
                "pdf_missing", "fail", f"in the PDF but not in the table: {dict(missing)}", ex.term
            )
        )
    if extra:
        found.append(
            Finding("pdf_extra", "fail", f"in the table but not in the PDF: {dict(extra)}", ex.term)
        )
    printed = squash("".join(ln.text for row in ex.rows for ln in row.events))
    table = squash("".join(e["event"] for e in term_events))
    if printed != table:
        found.append(
            Finding(
                "event_lines", "fail", "event text differs from the printed event lines", ex.term
            )
        )
    return found


def check_term_matches_pdf(ex: Extraction, expected_term: str) -> list[Finding]:
    """The term printed in the PDF title is the term we expect for that file."""
    if ex.term != expected_term:
        return [
            Finding("term", "fail", f"title says {ex.term!r}, expected {expected_term!r}", ex.pdf)
        ]
    return []


def check_unparsed(unparsed: list[dict], ex: Extraction) -> list[Finding]:
    return [
        Finding("unparsed", "fail", f"{u['where']}: {u['why']}: {u['text']}", ex.term)
        for u in unparsed
    ]


def check_no_calendar_terms(events: list[dict], terms: list[str]) -> list[Finding]:
    """Terms with no published calendar produce no rows and the status for them is abstain."""
    found = []
    for term in terms:
        rows = [e for e in events if e["term"] == term]
        if rows:
            found.append(Finding("no_calendar", "fail", f"{len(rows)} rows for {term}", term))
        if calendar_status(events, term) != "abstain":
            found.append(Finding("no_calendar", "fail", f"{term} does not abstain", term))
    return found


def calendar_status(events: list[dict], term: str) -> str:
    """ "available" if the table has rows for the term, otherwise "abstain" (do not answer)."""
    return "available" if any(e["term"] == term for e in events) else "abstain"


class UnverifiedCalendarError(Exception):
    """The calendar table has rows the owner has not verified, so it must not be indexed."""


def check_verified(events: list[dict]) -> list[Finding]:
    """Every event is verified: true, by someone, on a date (checked when loaded for indexing)."""
    found = []
    for e in events:
        if e.get("verified") is not True:
            found.append(Finding("verified", "fail", "verified is not true", e.get("id")))
            continue
        try:
            date.fromisoformat(e["verified_on"])
        except (KeyError, TypeError, ValueError):
            found.append(
                Finding("verified", "fail", "verified_on is missing or not a date", e.get("id"))
            )
        if not e.get("verified_by"):
            found.append(Finding("verified", "fail", "verified_by is missing", e.get("id")))
    return found


def load_events_for_indexing(path: Path) -> list[dict]:
    """Load calendar_events.json for indexing. Raises if any event is not verified."""
    events = json.loads(path.read_text(encoding="utf-8"))
    problems = check_verified(events)
    if problems:
        ids = ", ".join(str(f.course) for f in problems[:5])
        raise UnverifiedCalendarError(
            f"{len(problems)} calendar problems: not verified or incomplete (first: {ids})"
        )
    return events
