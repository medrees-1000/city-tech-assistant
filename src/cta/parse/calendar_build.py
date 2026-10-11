"""Build data/calendar/calendar_events.json and docs/calendar-verification.md from the PDFs.

Run: uv run python -m cta.parse.calendar_build
Every row is written with verified: false. The owner checks each row against the PDF.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import yaml

from cta.parse.calendar import (
    Extraction,
    build_events,
    extract_pdf,
    parse_last_updated,
    weekday_check,
)
from cta.settings import ROOT
from cta.validate.calendar import (
    calendar_status,
    check_against_pdf,
    check_dates_in_window,
    check_duplicates,
    check_no_calendar_terms,
    check_required_fields,
    check_term_markers,
    check_term_matches_pdf,
    check_unparsed,
    check_weekdays,
)
from cta.validate.findings import Finding


def load_terms(path: Path = ROOT / "config" / "calendar_terms.yaml") -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def build_all(config: dict, root: Path = ROOT) -> tuple[list[dict], list[Extraction], dict]:
    """(all events, extractions, unparsed rows per term), in PDF order, term by term."""
    events: list[dict] = []
    extractions: list[Extraction] = []
    unparsed: dict[str, list[dict]] = {}
    for item in config["terms"]:
        ex = extract_pdf(root / item["pdf"])
        if ex.term != item["term"]:
            raise SystemExit(f"{item['pdf']}: title says {ex.term!r}, config says {item['term']!r}")
        term_events, term_unparsed = build_events(ex, item["pdf"])
        events += term_events
        extractions.append(ex)
        unparsed[ex.term] = term_unparsed
    return events, extractions, unparsed


def run_checks(events, extractions, unparsed, config) -> list[Finding]:
    windows = {t["term"]: tuple(t["window"]) for t in config["terms"]}
    findings = [
        *check_required_fields(events),
        *check_dates_in_window(events, windows),
        *check_weekdays(events),
        *check_duplicates(events),
        *check_no_calendar_terms(events, config["no_calendar_terms"]),
    ]
    for item, ex in zip(config["terms"], extractions, strict=True):
        findings += [
            *check_term_matches_pdf(ex, item["term"]),
            *check_term_markers(events, item["term"]),
            *check_against_pdf(events, ex),
            *check_unparsed(unparsed[ex.term], ex),
        ]
    return findings


def parsed_date(e: dict) -> str:
    if e["date_start"] is None:
        return "TBA"
    return f"{e['date_start']} to {e['date_end']}" if e["date_end"] else e["date_start"]


def cell(text: str, bold: bool | None = False) -> str:
    text = text.replace("|", "\\|")
    return f"**{text}**" if bold else text


def render_verification(events: list[dict], extractions: list[Extraction]) -> str:
    lines = [
        "# Calendar verification",
        "",
        "Written by `uv run python -m cta.parse.calendar_build`. Check every row against the PDF,",
        "tick the last column, then set `verified: true` for that event in",
        "`data/calendar/calendar_events.json`. All rows are `verified: false` until you do.",
        "",
        "- Printed date and day are exactly as printed. Parsed date is the resolved date (the year",
        "  comes from the term).",
        "- Text in **bold** in the Event column is bold in the PDF.",
        "- Weekday check compares the printed day with the weekday of the parsed date. Dates are",
        "  never changed to make them match.",
        "",
    ]
    for ex in extractions:
        rows = [e for e in events if e["term"] == ex.term]
        pdf = rows[0]["source_pdf"] if rows else ex.pdf
        updated = parse_last_updated(ex.last_updated_raw)
        lines += [
            f"## {ex.term}",
            "",
            f'Source: `{pdf}`, title "{ex.title}", last updated {updated} '
            f'(printed "{ex.last_updated_raw}"). {len(rows)} events.',
            "",
            "| # | Printed date | Printed day | Event text | Parsed date | Weekday check | OK |",
            "|---|---|---|---|---|---|---|",
        ]
        for i, e in enumerate(rows, 1):
            check = weekday_check(e["date_start"], e["date_end"], e["weekday_raw"])
            lines.append(
                f"| {i} | {cell(e['date_raw'])} | {cell(e['weekday_raw'])} | "
                f"{cell(e['event'], e['bold'])} | {parsed_date(e)} | {check} | [ ] |"
            )
        joined = [i for i, e in enumerate(rows, 1) if e["notes"] and "joined" in e["notes"]]
        tba = [i for i, e in enumerate(rows, 1) if e["date_start"] is None]
        applies = [i for i, e in enumerate(rows, 1) if e["applies_to"]]
        checks = [weekday_check(e["date_start"], e["date_end"], e["weekday_raw"]) for e in rows]
        mismatches = [i for i, c in enumerate(checks, 1) if c.startswith("MISMATCH")]
        lines += [
            "",
            f"Rows made from two printed lines (wrapped text, joined): {joined or 'none'}.",
            f"Rows with a TBA date: {tba or 'none'}. "
            f"Rows where `applies_to` was filled: {applies or 'none'}.",
            f"Weekday mismatches: {mismatches or 'none'}.",
            "Text in the PDF outside the table (not events): "
            + "; ".join(f'"{t}"' for t in ex.excluded)
            + ".",
            "",
        ]
    return "\n".join(lines)


def main() -> int:
    config = load_terms()
    events, extractions, unparsed = build_all(config)
    findings = run_checks(events, extractions, unparsed, config)
    out = ROOT / "data" / "calendar" / "calendar_events.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(events, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (ROOT / "docs" / "calendar-verification.md").write_text(
        render_verification(events, extractions), encoding="utf-8"
    )
    print("events per term:", dict(Counter(e["term"] for e in events)))
    for term in config["no_calendar_terms"]:
        print(f"{term}: {calendar_status(events, term)}")
    for f in findings:
        print(f"[{f.severity.upper()}] {f.check} {f.course}: {f.message}")
    print(f"{len(events)} events, {sum(f.severity == 'fail' for f in findings)} failures")
    return 1 if any(f.severity == "fail" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
