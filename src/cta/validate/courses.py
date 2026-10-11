"""Automatic course checks from docs/data-validation.md.

Run: uv run python -m cta.validate.courses
A "fail" finding fails the build. A "warning" is flagged for the owner, not guessed away.
"""

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from cta.settings import ROOT, load_sources

REQUIRED_FIELDS = ("code", "title", "description", "credits", "department", "status")
RULE_ID = re.compile(r"\b\d{6}\b")
# SUBJ NNNN with an optional space and suffix letters: CST 1201, CST1201, MAT 1475H, ENG 1101CO.
# Also matches inside shorthand such as PRE_CST3500_CST3600.
COURSE_CODE = re.compile(r"(?<![A-Za-z0-9])([A-Z]{2,5}) ?(\d{3,4})([A-Z]{0,2})(?![A-Za-z0-9])")
MAX_COUNT_CHANGE = 3  # "a few courses"


@dataclass
class Finding:
    check: str
    severity: str  # "fail" or "warning"
    message: str
    course: str | None = None


def check_totals(summary: dict, expected_total: int) -> list[Finding]:
    found = []
    downloaded, before, after = (
        summary["downloaded"],
        summary["total_before"],
        summary["total_after"],
    )
    if not downloaded == before == after:
        msg = f"API total before={before}, after={after}, downloaded={downloaded}"
        found.append(Finding("totals", "fail", msg))
    if before != expected_total:
        msg = f"API total is {before}, CLAUDE.md says {expected_total}"
        found.append(Finding("totals", "warning", msg))
    return found


def check_required_fields(records: list[dict]) -> list[Finding]:
    found = []
    for rec in records:
        missing = [f for f in REQUIRED_FIELDS if rec.get(f) in (None, "")]
        if missing:
            found.append(Finding("required_fields", "fail", f"missing {missing}", rec.get("code")))
        if rec.get("status") != "Active":
            found.append(
                Finding("required_fields", "fail", f"status={rec.get('status')}", rec.get("code"))
            )
    return found


def check_extra_fields(records: list[dict]) -> list[Finding]:
    """Fields taken from the raw data: present and the right type (pathways_category: non-empty)."""
    found = []
    for rec in records:
        bad = [f for f in ("liberal_arts", "writing_intensive") if not isinstance(rec.get(f), bool)]
        if not isinstance(rec.get("catalog_attributes"), list):
            bad.append("catalog_attributes")
        if not isinstance(rec.get("legacy_prefix"), bool):
            bad.append("legacy_prefix")
        bad += [f for f in ("credit_hours", "contact_hours") if not isinstance(rec.get(f), dict)]
        if not isinstance(rec.get("pathways_category"), str) or not rec["pathways_category"]:
            bad.append("pathways_category")
        if bad:
            found.append(
                Finding("extra_fields", "fail", f"missing or wrong type: {bad}", rec["code"])
            )
    return found


def check_pathways_labels(records: list[dict]) -> list[Finding]:
    """A coded pathways_category (no spaces, e.g. RLA_CollegeOption) with no pathways_label."""
    return [
        Finding(
            "pathways_labels",
            "warning",
            f"{r['pathways_category']} has no pathways_label",
            r["code"],
        )
        for r in records
        if r.get("pathways_category")
        and " " not in r["pathways_category"]
        and not r.get("pathways_label")
    ]


def check_rules_resolved(records: list[dict]) -> list[Finding]:
    found = []
    for rec in records:
        text = rec.get("prerequisite_text")
        if rec.get("rule_id") and not text:
            msg = f"rule {rec['rule_id']} did not resolve to text"
            found.append(Finding("rules_resolved", "fail", msg, rec["code"]))
        elif text and RULE_ID.search(text):
            msg = f"prerequisite text contains a 6-digit rule ID: {text[:80]!r}"
            found.append(Finding("rules_resolved", "fail", msg, rec["code"]))
    return found


def check_prereq_codes_exist(records: list[dict], all_codes: set[str]) -> list[Finding]:
    """Warn about codes in prerequisite text that are not in the catalog (not Active, or unknown).

    A match only counts as a code when SUBJ is a subject used by the catalog, so words like
    "OR 3513" are ignored. A suffix is accepted if the code with or without it exists.
    """
    subjects = {code.split()[0] for code in all_codes}
    found = []
    for rec in records:
        seen = set()
        for subj, number, suffix in COURSE_CODE.findall(rec.get("prerequisite_text") or ""):
            code = f"{subj} {number}{suffix}"
            if subj not in subjects or code in seen:
                continue
            seen.add(code)
            if code not in all_codes and f"{subj} {number}" not in all_codes:
                msg = f"prerequisite mentions {code}, which is not an Active catalog course"
                found.append(Finding("prereq_codes", "warning", msg, rec["code"]))
    return found


def check_no_duplicates(records: list[dict]) -> list[Finding]:
    counts = Counter((r["department"], r["code"]) for r in records)
    return [
        Finding("duplicates", "fail", f"{n} records for {code} in {dept}", code)
        for (dept, code), n in counts.items()
        if n > 1
    ]


def check_counts(current: dict[str, int], previous: dict[str, int]) -> list[Finding]:
    found = []
    for dept in sorted(set(current) | set(previous)):
        now, before = current.get(dept, 0), previous.get(dept)
        if before is not None and abs(now - before) > MAX_COUNT_CHANGE:
            found.append(Finding("counts", "warning", f"{dept}: {before} -> {now}"))
    return found


def run_course_checks(
    records: list[dict], summary: dict, all_codes: set[str], expected_total: int
) -> list[Finding]:
    current = dict(Counter(r["department"] for r in records))
    return [
        *check_totals(summary, expected_total),
        *check_required_fields(records),
        *check_extra_fields(records),
        *check_pathways_labels(records),
        *check_rules_resolved(records),
        *check_prereq_codes_exist(records, all_codes),
        *check_no_duplicates(records),
        *check_counts(current, summary.get("previous_counts_per_department", {})),
    ]


def load_records(processed: Path) -> list[dict]:
    paths = sorted((processed / "courses").rglob("*.json"))
    return [json.loads(p.read_text(encoding="utf-8")) for p in paths]


def main() -> int:
    processed = ROOT / "data" / "processed"
    summary = json.loads((processed / "catalog_run.json").read_text(encoding="utf-8"))
    records = load_records(processed)
    expected = load_sources()["catalog_api"]["expected_total"]
    findings = run_course_checks(records, summary, set(summary["all_codes"]), expected)
    for f in findings:
        print(f"[{f.severity.upper()}] {f.check} {f.course or ''}: {f.message}")
    fails = sum(f.severity == "fail" for f in findings)
    print(f"{len(records)} records, {fails} failures, {len(findings) - fails} warnings")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
