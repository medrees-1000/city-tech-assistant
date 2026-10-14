"""Step 3b detectors F1 to F3 (docs/decisions.md, "Step 5b" and its addendum). No model call.

A date token is "Month D" (full or three-letter month name, optional year) or "M/D" or
"M/D/YY(YY)". A date is normalised to (month, day); the year is ignored (a source date and an
answer date are the same when month and day agree).
"""

import re

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december"]  # fmt: skip
_NAMES = "|".join([*MONTHS, *(m[:3] for m in MONTHS), "sept"])
NAMED = re.compile(rf"\b({_NAMES})\.?\s+(\d{{1,2}})\b", re.IGNORECASE)
NUMERIC = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/\d{2,4})?\b")
BULLET = re.compile(r"^\s*[-*•]\s+")
CONDITION = "when you first registered"  # F3 for the tuition-deadline tiers (q13)


def dates_in(text: str) -> set[tuple[int, int]]:
    """Normalised (month, day) of every date token in the text."""
    found = set()
    for name, day in NAMED.findall(text):
        found.add(
            (next(i for i, m in enumerate(MONTHS, 1) if m.startswith(name[:3].lower())), int(day))
        )
    for month, day in NUMERIC.findall(text):
        if 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
            found.add((int(month), int(day)))
    return found


def structured_rows(chunk_text: str) -> list[str]:
    """The rows of a markdown table (lines starting with "|") and the items of a "- " list."""
    return [ln for ln in chunk_text.splitlines() if ln.lstrip().startswith("|") or BULLET.match(ln)]


def has_date_rows(chunk_text: str) -> bool:
    """F1 trigger: the chunk holds three or more table rows or list items with a date each."""
    return sum(bool(dates_in(row)) for row in structured_rows(chunk_text)) >= 3


def bullet_lines(answer: str) -> list[str]:
    return [ln for ln in answer.splitlines() if BULLET.match(ln)]


def f1(answer: str, earlier_answers: list[str]) -> tuple[bool, str]:
    """At least three bullet lines that each contain a date, and no date lost: every date that an
    earlier (before-arm) answer to the same question stated is still stated."""
    dated = [ln for ln in bullet_lines(answer) if dates_in(ln)]
    if len(dated) < 3:
        return False, f"{len(dated)} dated bullet lines"
    lost = set().union(*(dates_in(a) for a in earlier_answers)) - dates_in(answer)
    return (not lost), (f"dates lost: {sorted(lost)}" if lost else "ok")


def f2(answer: str) -> tuple[bool, str]:
    """A one-fact answer is not a list: at most one bullet line."""
    n = len(bullet_lines(answer))
    return n <= 1, f"{n} bullet lines"


def f3(answer: str, condition: str = CONDITION) -> tuple[bool, str]:
    """The condition that explains the tiers is still stated."""
    return condition.lower() in " ".join(answer.lower().split()), f"condition {condition!r}"
