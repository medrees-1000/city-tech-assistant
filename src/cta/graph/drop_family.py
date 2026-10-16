"""T04 (casual round; docs/decisions.md, "Casual round"): an unqualified "last day to drop /
withdraw" question gets ALL the grade-related drop rows of the term, not whichever subset the
model-based selector picks that run.

Plain code, no model call. The rows are found by their event text in the calendar data (never by
hand-typed ids): "Last day to drop ... grade of WD" and "Last day to withdraw ... grade of W".
Refund-percent rows and add rows are not included.
"""

import re

FAMILY = re.compile(r"\b(?:drop|dropping|withdraw|withdrawing|withdrawal)\b", re.IGNORECASE)
DATE_CUE = re.compile(r"\b(?:last day|deadline|when|until|date|cutoff)\b", re.IGNORECASE)
# any of these makes the question specific: the selector (or retrieval) handles it as before
QUALIFIER = re.compile(
    r"grade of w|with a w\b|\bwd\b|without|%|percent|refund|tuition|\badd\b|\bafter\b|\bbefore\b",
    re.IGNORECASE,
)
ROW_EVENT = re.compile(r"^last day to (?:drop|withdraw)\b.*\bgrade of WD?\b", re.IGNORECASE)


def applies(question: str) -> bool:
    """True for an unqualified drop/withdraw date question."""
    return bool(
        FAMILY.search(question) and DATE_CUE.search(question) and not QUALIFIER.search(question)
    )


def rows_of(pool: list[dict]) -> list[dict]:
    """The grade-related drop/withdraw rows of one term's rows, in date order."""
    found = [r for r in pool if ROW_EVENT.match(r["event"].strip())]
    return sorted(found, key=lambda r: (r["date_start"] or "", r["id"]))
