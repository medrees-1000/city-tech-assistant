"""Checks of the term tags on sections (docs/data-validation.md, "Metadata").

Every section has `terms`, a list (may be empty) of stored terms such as "Fall 2026". Each entry has
the stored form. A section whose heading path or table title names a term has it in `terms`. A term
that no heading names is allowed only where the section says why (`terms_source`, the refund
calendar rule). `term` is the entry when there is exactly one, else null.
"""

import re

from cta.parse.terms import TERM_FORM, heading_path, table_header_text
from cta.validate.findings import Finding

# a second, plain reading of the names (the parser's own pattern is not reused on purpose)
NAMED = re.compile(
    r"\b(summer|fall|winter|spring)\b(?:\s+session)?(?:\s+(i{1,2})\b)?\s+(20\d\d)\b", re.I
)


def named_in(text: str) -> set[tuple[str, str, str]]:
    return {(m[1].lower(), (m[2] or "").lower(), m[3]) for m in NAMED.finditer(text)}


def key_of(term: str) -> tuple[str, str, str]:
    words = term.split()
    roman = words[1].lower() if len(words) == 3 else ""
    return (words[0].lower(), roman, words[-1])


def record_name(record: dict) -> str:
    return record.get("source_url") or record.get("source_file") or "?"


def check_section_terms(record: dict) -> list[Finding]:
    found = []
    name = record_name(record)
    for n, s in enumerate(record["sections"], 1):
        where = f"{name} section {n} ({s['heading']!r})"
        terms = s.get("terms")
        if not isinstance(terms, list):
            found.append(Finding("terms_not_list", "fail", "terms is missing or not a list", where))
            continue
        bad = [t for t in terms if not isinstance(t, str) or not TERM_FORM.match(t)]
        if bad:
            found.append(Finding("term_form", "fail", f"not a term: {bad}", where))
            continue
        if s.get("term") != (terms[0] if len(terms) == 1 else None):
            found.append(Finding("term_value", "fail", f"term {s.get('term')!r} vs {terms}", where))
        printed = named_in(f"{heading_path(s)} {table_header_text(s['markdown'])}")
        have = {key_of(t) for t in terms}
        for missing in sorted(printed - have):
            found.append(
                Finding("term_missing", "fail", f"names {missing} but not in terms", where)
            )
        if not s.get("terms_source"):
            for extra in sorted(have - printed):
                found.append(Finding("term_invented", "fail", f"{extra} is in no heading", where))
    return found


def check_covered_terms(record: dict, refund_pages: list[str]) -> list[Finding]:
    """A refund page stores covered_terms: valid terms, and every section term is among them."""
    if record.get("source_url") not in refund_pages:
        return []
    name = record_name(record)
    covered = record.get("covered_terms")
    if not isinstance(covered, list) or not all(TERM_FORM.match(str(t)) for t in covered):
        return [
            Finding("covered_terms", "fail", "covered_terms is missing or not a term list", name)
        ]
    used = {t for s in record["sections"] for t in s.get("terms", [])}
    return [
        Finding("covered_terms", "fail", f"{t} is a section term but not covered", name)
        for t in sorted(used - set(covered))
    ]


def run_term_checks(records: list[dict], refund_pages: list[str]) -> list[Finding]:
    return [
        f for r in records for f in (*check_section_terms(r), *check_covered_terms(r, refund_pages))
    ]
