"""Run every automatic check of docs/data-validation.md and print one table.

Run: uv run python -m cta.validate
Areas: courses, pages, PDFs, departments, calendar. Each area checks the records on disk (what
would be indexed) against their sources. A missing input (for example a PDF that is not committed)
is reported as SKIPPED, never as a pass. The exit code is 1 if any check fails.
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from cta.settings import ROOT, load_sources
from cta.validate.findings import Finding

PROCESSED = ROOT / "data" / "processed"


@dataclass
class Area:
    name: str
    checked: str = "-"
    findings: list[Finding] = field(default_factory=list)
    skipped: str | None = None

    @property
    def failed(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "fail" and not f.accepted]

    @property
    def accepted(self) -> list[Finding]:
        return [f for f in self.findings if f.accepted]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning" and not f.accepted]

    @property
    def result(self) -> str:
        if self.skipped:
            return "SKIPPED"
        return "FAIL" if self.failed else "PASS"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def check_courses() -> Area:
    from cta.validate.courses import load_records, run_course_checks

    area = Area("courses")
    summary_path = PROCESSED / "catalog_run.json"
    if not summary_path.exists():
        area.skipped = f"{summary_path} is missing"
        return area
    summary = read_json(summary_path)
    records = load_records(PROCESSED)
    expected = load_sources()["catalog_api"]["expected_total"]
    area.findings = run_course_checks(records, summary, set(summary["all_codes"]), expected)
    area.checked = f"{len(records)} courses"
    return area


def check_pages() -> Area:
    from cta.validate.pages import apply_accepted, run_page_checks

    area = Area("pages")
    manifest_path = PROCESSED / "pages_manifest.json"
    log_path = ROOT / "data" / "raw" / "fetch_log.jsonl"
    if not manifest_path.exists() or not log_path.exists():
        area.skipped = "pages manifest or fetch log is missing"
        return area
    records = [read_json(p) for p in sorted((PROCESSED / "pages").rglob("*.json"))]
    log = [json.loads(x) for x in log_path.read_text(encoding="utf-8").splitlines() if x]
    contacts = [read_json(p) for p in sorted((PROCESSED / "contacts").glob("*.json"))]
    area.findings = apply_accepted(
        run_page_checks(read_json(manifest_path), records, log, contacts)
    )
    area.checked = f"{len(records)} pages, {len(contacts)} contact records"
    return area


def check_pdfs() -> Area:
    from cta.validate.pdfs import run_pdf_checks

    area = Area("pdfs")
    paths = sorted((PROCESSED / "pdfs").glob("*.json"))
    records = [read_json(p) for p in paths]
    missing = [r["source_file"] for r in records if not (ROOT / r["source_file"]).exists()]
    if not records or missing:
        area.skipped = f"no records, or PDFs missing: {missing}"
        return area
    for r in records:
        area.findings += run_pdf_checks(r, ROOT / r["source_file"])
    area.checked = f"{len(records)} PDFs"
    return area


def check_departments() -> Area:
    from cta.parse.departments import DEPARTMENTS, Parsed, boilerplate_sentences
    from cta.validate.departments import run_department_checks

    area = Area("departments")
    pdf_dir = ROOT / "data" / "pdfs"
    missing = [n for n in DEPARTMENTS.values() if not (pdf_dir / n).exists()]
    folders = {d: PROCESSED / "departments" / d for d in DEPARTMENTS}
    if missing or not all(f.exists() for f in folders.values()):
        area.skipped = f"department PDFs or records missing: {missing}"
        return area
    parsed = {d: Parsed(d, pdf_dir / n) for d, n in DEPARTMENTS.items()}
    generic = boilerplate_sentences({d: p.trees for d, p in parsed.items()})
    count = 0
    for dept, folder in folders.items():
        records = [read_json(p) for p in sorted(folder.glob("*.json"))]
        count += len(records)
        area.findings += run_department_checks(records, parsed[dept], generic)
    area.checked = f"{count} records in {len(folders)} departments"
    return area


def check_calendar() -> Area:
    from cta.parse.calendar_build import build_all, load_terms, run_checks
    from cta.validate.calendar import check_verified

    area = Area("calendar")
    path = ROOT / "data" / "calendar" / "calendar_events.json"
    config = load_terms()
    pdfs = [ROOT / t["pdf"] for t in config["terms"]]
    if not path.exists() or not all(p.exists() for p in pdfs):
        area.skipped = "calendar table or calendar PDFs are missing"
        return area
    events = read_json(path)
    _, extractions, unparsed = build_all(config)  # re-read in memory; the file is not touched
    area.findings = [*run_checks(events, extractions, unparsed, config), *check_verified(events)]
    area.checked = f"{len(events)} events"
    return area


AREAS = [check_courses, check_pages, check_pdfs, check_departments, check_calendar]


def table(areas: list[Area]) -> str:
    lines = [
        "| Area | Checked | Fail | Accepted | Warnings | Result |",
        "|---|---|---|---|---|---|",
    ]
    for a in areas:
        checked = a.checked if not a.skipped else f"skipped: {a.skipped}"
        row = (a.name, checked, len(a.failed), len(a.accepted), len(a.warnings), a.result)
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(lines)


def details(areas: list[Area]) -> list[str]:
    out = []
    for a in areas:
        for f in a.findings:
            tag = "ACCEPTED" if f.accepted else f.severity.upper()
            why = f" ({f.accepted})" if f.accepted else ""
            out.append(f"[{tag}] {a.name}: {f.check} {f.course or ''}: {f.message}{why}")
    return out


def main() -> int:
    areas = [run() for run in AREAS]
    print(table(areas))
    for line in details(areas):
        print(line)
    return 1 if any(a.failed for a in areas) else 0


if __name__ == "__main__":
    sys.exit(main())
