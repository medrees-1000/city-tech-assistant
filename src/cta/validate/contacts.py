"""config/contacts.yaml against the processed data (Phase 3, step 4c).

Every email and phone must come from the owner's contact record (or, for Special Circumstances, the
flyer record). A phone must sit on a "Phone:" or "Office Phone:" line: a number printed only after
"Fax:", or on any other line (the 24/7 AI-agent line), is refused. Source page and fetched_at must
match the record, and every department of config/departments.yaml needs an entry.
"""

import json
import re
from pathlib import Path

from cta.validate.findings import Finding

PHONE_LINE = re.compile(r"^\s*(?:Office\s+)?Phone:\s*(.*)$", re.IGNORECASE)
FAX_LINE = re.compile(r"^\s*Fax:", re.IGNORECASE)
FLYER = "special-circumstances"


def panel_lines(record: dict) -> list[str]:
    return [ln for p in record.get("panels", []) for ln in p["markdown"].splitlines()]


def flyer_text(record: dict) -> str:
    return "\n".join(s.get("markdown") or s.get("text") or "" for s in record["sections"])


def phone_problem(number: str, lines: list[str]) -> str | None:
    """Why a number is not a phone of the contact block, or None if it is."""
    on = [ln for ln in lines if number in ln]
    if any(PHONE_LINE.match(ln) for ln in on):
        return None
    if on and all(FAX_LINE.match(ln) for ln in on):
        return "is only a fax number"
    return "is not on a Phone: or Office Phone: line" if on else "is not in the record"


def flyer_phone_problem(number: str, text: str) -> str | None:
    """The flyer prints the number on its own line, without a label."""
    lines = [ln for ln in text.splitlines() if number in ln]
    return None if any(not FAX_LINE.match(ln) for ln in lines) else "is not in the flyer"


def check_entry(key: str, entry: dict, record: dict) -> list[Finding]:
    out = []
    is_flyer = key == FLYER
    if is_flyer:
        text = flyer_text(record)
    else:
        if entry["page"] not in record["source_pages"]:
            msg = f"page {entry['page']} is not a source page of the record"
            out.append(Finding("contact_source", "fail", msg, key))
        if entry["fetched_at"] != record["fetched_at"]:
            msg = f"fetched_at {entry['fetched_at']} != {record['fetched_at']}"
            out.append(Finding("contact_source", "fail", msg, key))
    for e in entry["emails"]:
        address = e["address"] if isinstance(e, dict) else e
        if address not in (text if is_flyer else record["emails"]):
            msg = f"{address} is not in {entry['source']}"
            out.append(Finding("contact_email", "fail", msg, key))
    for number in entry["phones"]:
        problem = (
            flyer_phone_problem(number, text)
            if is_flyer
            else phone_problem(number, panel_lines(record))
        )
        if problem:
            out.append(Finding("contact_phone", "fail", f"{number} {problem}", key))
    return out


def run_contact_checks(
    cfg: dict, root: Path, department_ids: list[str]
) -> tuple[int, list[Finding]]:
    findings = []
    for dept in department_ids:
        if dept not in cfg["offices"]:
            findings.append(Finding("contact_missing", "fail", "no entry for the department", dept))
    for key, entry in cfg["offices"].items():
        path = root / entry["source"]
        if not path.exists():
            findings.append(Finding("contact_source", "fail", f"{entry['source']} is missing", key))
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        findings += check_entry(key, entry, record)
    return len(cfg["offices"]), findings
