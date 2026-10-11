"""Metadata completeness of every section that will be embedded (docs/data-validation.md).

Every section with embed true carries: source_url or source_file, doc_type (one of the allowed
list), department (null allowed for central offices), scope, term (null allowed where none is
printed), fetched_at or a file date, and last_updated (null allowed). A missing key fails; a null
where null is not allowed fails. A page that no doc_type rule covers is flagged.
"""

import json
from pathlib import Path

from cta.index.metadata import chunk_metadata, null_problems
from cta.validate.findings import Finding

RECORD_GLOBS = ("pages/*/*.json", "pdfs/*.json", "departments/*/*.json")


def embedded_sections(record: dict) -> list[dict]:
    """Sections that will be embedded: the record is indexed and the section is not embed false."""
    if not record.get("index") or record.get("status", "collected") != "collected":
        return []
    return [s for s in record["sections"] if s.get("embed") is not False]


def record_name(record: dict) -> str:
    return record.get("source_url") or record.get("source_file") or "?"


def check_record_metadata(record: dict, allowed: list[str]) -> list[Finding]:
    name = record_name(record)
    values, missing = chunk_metadata(record)
    n = len(embedded_sections(record))
    if not n:  # nothing is embedded; only flag a collected page that no doc_type rule covers
        if values["doc_type"] is None and record.get("status", "collected") == "collected":
            message = "no doc_type rule covers it (not indexed)"
            return [Finding("doc_type_missing", "warning", message, name)]
        return []
    found = [
        Finding("metadata_missing_key", "fail", f"no key for {f} ({n} sections)", name)
        for f in missing
    ]
    doc_type = values["doc_type"]
    if doc_type is None and "doc_type" not in missing:
        message = f"no doc_type rule covers it ({n} sections)"
        found.append(Finding("doc_type_missing", "fail", message, name))
    elif doc_type is not None and doc_type not in allowed:
        message = f"{doc_type!r} is not in the allowed list"
        found.append(Finding("doc_type_not_allowed", "fail", message, name))
    for field in null_problems(values):
        if field not in missing and field != "doc_type":
            found.append(Finding("metadata_null", "fail", f"{field} is null ({n} sections)", name))
    return found


def run_metadata_checks(records: list[dict], allowed: list[str]) -> list[Finding]:
    return [f for r in records for f in check_record_metadata(r, allowed)]


def load_records(processed: Path) -> list[dict]:
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for pattern in RECORD_GLOBS
        for p in sorted(processed.glob(pattern))
    ]
