"""Load the hand-verified calendar events into the calendar_events table. No API call.

    uv run python -m cta.index.load_calendar --dry-run   # counts only, nothing written
    uv run python -m cta.index.load_calendar             # preview and stop
    uv run python -m cta.index.load_calendar --yes       # upsert, delete stale rows, then check

The file is read only through load_events_for_indexing, which refuses unverified events.
"""

import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from cta.index.db import connect
from cta.settings import ROOT
from cta.validate.calendar import UnverifiedCalendarError, load_events_for_indexing

EVENTS_FILE = ROOT / "data" / "calendar" / "calendar_events.json"
COLUMNS = (
    "id", "term", "event", "date_start", "date_end", "date_raw", "weekday_raw", "applies_to",
    "source_pdf", "source_page", "pdf_last_updated", "verified", "verified_by", "verified_on",
    "notes",
)  # fmt: skip
DATE_COLUMNS = ("date_start", "date_end", "pdf_last_updated", "verified_on")
EXPECTED_COUNTS = {"Fall 2026": 55, "Winter 2027": 26, "Spring 2027": 55}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def to_row(event: dict) -> dict:
    """A table row from a file event: dates are date objects; TBA is None (date_raw kept)."""
    row = {c: event.get(c) for c in COLUMNS}
    for c in DATE_COLUMNS:
        row[c] = date.fromisoformat(row[c]) if row[c] else None
    return row


def existing_rows(conn) -> dict[str, dict]:
    cur = conn.execute(f"SELECT {', '.join(COLUMNS)} FROM calendar_events")
    return {r[0]: dict(zip(COLUMNS, r, strict=True)) for r in cur}


def make_plan(rows: list[dict], existing: dict[str, dict]) -> dict[str, list]:
    plan = {"new": [], "changed": [], "unchanged": [], "stale": []}
    for row in rows:
        old = existing.get(row["id"])
        plan["new" if old is None else "unchanged" if old == row else "changed"].append(row)
    plan["stale"] = sorted(set(existing) - {r["id"] for r in rows})
    return plan


def apply_plan(conn, rows: list[dict], plan: dict[str, list]) -> None:
    marks = ", ".join(["%s"] * len(COLUMNS))
    sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in COLUMNS[1:])
    with conn.transaction():
        for row in plan["new"] + plan["changed"]:
            conn.execute(
                f"INSERT INTO calendar_events ({', '.join(COLUMNS)}) VALUES ({marks}) "
                f"ON CONFLICT (id) DO UPDATE SET {sets}",
                [row[c] for c in COLUMNS],
            )
        if plan["stale"]:
            conn.execute("DELETE FROM calendar_events WHERE id = ANY(%s)", (plan["stale"],))


# ---- integrity checks: they report, they never fix ----


def weekday_name(d: date) -> str:
    return WEEKDAYS[d.weekday()]


def integrity(rows: list[dict], expected: dict = EXPECTED_COUNTS) -> tuple[list[str], list[str]]:
    """(problems, TBA event names) for rows as stored in the table."""
    problems: list[str] = []
    counts = Counter(r["term"] for r in rows)
    if dict(counts) != expected:
        problems.append(
            f"row counts {dict(counts)} (total {len(rows)}), expected {EXPECTED_COUNTS}"
        )
    for r in rows:
        who = r["id"]
        if not (r["verified"] is True and r["verified_by"] and r["verified_on"]):
            problems.append(f"{who}: not fully verified")
        start, end = r["date_start"], r["date_end"]
        if start is None:
            continue
        names = (r["weekday_raw"] or "").split("-")
        if names[0] != weekday_name(start):
            problems.append(
                f"{who}: {start} is a {weekday_name(start)}, weekday_raw {r['weekday_raw']!r}"
            )
        if end is not None and len(names) == 2 and names[1] != weekday_name(end):
            problems.append(
                f"{who}: {end} is a {weekday_name(end)}, weekday_raw {r['weekday_raw']!r}"
            )
        printed = re.search(r"\b(20\d\d)\b", r["date_raw"] or "")
        season, year = r["term"].split()
        for d in (start, end):
            if d is None:
                continue
            if printed:  # the PDF printed a year ("January 01, 2027"): it decides
                want = int(printed.group(1))
            else:  # Winter 2027 starts in December 2026: December belongs to the year before
                want = int(year) - 1 if season == "Winter" and d.month == 12 else int(year)
            if d.year != want:
                problems.append(f"{who}: {d} has year {d.year}, expected {want} for {r['term']}")
    tba = [r["event"] for r in rows if r["date_start"] is None]
    return problems, tba


def report(conn) -> tuple[str, bool]:
    rows = list(existing_rows(conn).values())
    problems, tba = integrity(rows)
    lines = [f"rows in calendar_events: {len(rows)} ({dict(Counter(r['term'] for r in rows))})"]
    lines.append(f"integrity problems: {len(problems)}" + "".join(f"\n  {p}" for p in problems))
    lines.append(f"rows with a NULL date (TBA): {len(tba)}" + "".join(f"\n  {t}" for t in tba))
    return "\n".join(lines), not problems


def run(conn, events: list[dict], yes: bool, dry_run: bool, out=print) -> int:
    rows = [to_row(e) for e in events]
    plan = make_plan(rows, existing_rows(conn))
    out(", ".join(f"{k} {len(v)}" for k, v in plan.items()))
    if dry_run:
        out("dry run: nothing written")
        return 0
    changes = bool(plan["new"] or plan["changed"] or plan["stale"])
    if changes and not yes:
        out("nothing was changed; run again with --yes to apply")
        return 0
    if changes:
        apply_plan(conn, rows, plan)
        conn.commit()
    text, ok = report(conn)
    out(text)
    return 0 if ok else 1


def main(argv: list[str], path: Path = EVENTS_FILE) -> int:
    flags = set(argv[1:])
    if not flags <= {"--dry-run", "--yes"}:
        print("usage: python -m cta.index.load_calendar [--dry-run] [--yes]")
        return 2
    try:
        events = load_events_for_indexing(path)
    except UnverifiedCalendarError as e:
        print(f"refused: {e}")
        return 1
    with connect() as conn:
        return run(conn, events, "--yes" in flags, "--dry-run" in flags)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
