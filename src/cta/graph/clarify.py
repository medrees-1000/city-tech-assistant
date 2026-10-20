"""CLARIFY (step 4): a short, generic deadline question gets a fixed question back.

Plain code, no model call. It runs after the classifier and before the calendar and retrieval
nodes. It fires only when every condition holds (docs/decisions.md, "Step 4: CLARIFY"):
  1. the question is short (at most MAX_WORDS words);
  2. it holds a generic deadline cue ("deadline", "due date", "last day"), or is exactly a vague
     "when is it (due)" (tester round 2, T08);
  3. it names no topic (TOPIC_WORDS), no course code and no department;
  4. the classifier did not say "prerequisite".
The reply is a fixed template; the terms in it are read from config/calendar_terms.yaml."""

import re
from functools import lru_cache

import yaml

from cta.index.departments import detect_departments
from cta.settings import ROOT

# ---- the drop-family rule (was drop_family.py) ----
# T04 (casual round; docs/decisions.md, "Casual round"): an unqualified "last day to drop /
# withdraw" question gets ALL the grade-related drop rows of the term, not whichever subset the
# model-based selector picks that run.
#
# Plain code, no model call. The rows are found by their event text in the calendar data (never
# by hand-typed ids): "Last day to drop ... grade of WD" and "Last day to withdraw ... grade of W".
# Add rows are not included. Since version 2.1 prep (Oct 17, 2026, owner decision) the
# tuition-refund rows ("Last day to drop for 100% tuition refund" and so on) are included too: a
# drop answer shows the drop and withdraw deadlines and the refund deadlines, all verified
# calendar rows, in date order.

FAMILY = re.compile(r"\b(?:drop|dropping|withdraw|withdrawing|withdrawal)\b", re.IGNORECASE)
DATE_CUE = re.compile(r"\b(?:last day|deadline|when|until|date|cutoff)\b", re.IGNORECASE)
# any of these makes the question specific: the selector (or retrieval) handles it as before
QUALIFIER = re.compile(
    r"grade of w|with a w\b|\bwd\b|without|%|percent|refund|tuition|\badd\b|\bafter\b|\bbefore\b",
    re.IGNORECASE,
)
ROW_EVENT = re.compile(r"^last day to (?:drop|withdraw)\b.*\bgrade of WD?\b", re.IGNORECASE)
REFUND_EVENT = re.compile(r"^last day to drop\b.*\btuition refund\b", re.IGNORECASE)
DROP_FAMILY_VERSION = "drop_family_v2"  # v1 (grade rows only) is what older stored records say


def drop_family_applies(question: str) -> bool:
    """True for an unqualified drop/withdraw date question."""
    return bool(
        FAMILY.search(question) and DATE_CUE.search(question) and not QUALIFIER.search(question)
    )


def drop_family_rows(pool: list[dict]) -> list[dict]:
    """The drop/withdraw deadline rows and the tuition-refund rows of one term's rows, in date order
    (the rows are found by their event text in the verified table; a term with none gets none)."""
    found = [
        r
        for r in pool
        if ROW_EVENT.match(r["event"].strip()) or REFUND_EVENT.match(r["event"].strip())
    ]
    return sorted(found, key=lambda r: (r["date_start"] or "", r["id"]))


MAX_WORDS = 8
CUES = ("deadline", "deadlines", "due date", "due dates", "last day")

# The topics a student can mean by "the deadline". A question holding any of these (or a longer
# word starting with one, "registering") already says which deadline, so it never clarifies. The
# list errs on the side of too many words: a clear question must never be asked to repeat itself.
TOPIC_WORDS = (
    "regist", "enrol", "add", "drop", "withdraw", "tuition", "pay", "bill", "refund", "fee",
    "aid", "fafsa", "tap", "pell", "loan", "scholarship", "grant", "appeal", "sap", "graduat",
    "apply", "application", "commencement", "diploma", "epermit", "permit", "readmi", "incomplete",
    "grade", "exam", "final", "class", "course", "semester", "session", "term", "start", "begin",
    "end", "break", "holiday", "closed", "open", "transfer", "admission", "major", "change",
    "audit", "waiver", "petition", "deposit", "plan", "late", "cancel", "resign", "return",
    "file", "filing", "submit", "advis", "degree", "credit", "hold", "bursar", "registrar",
)  # fmt: skip
# Tester round 2, T08: "when is it due" has no cue word from CUES but is just as vague. Only the
# whole question counts ("when is it due for tuition" and "when is it open" name something).
VAGUE_WHEN = re.compile(r"^when(?:'?s| is| are)\s+(?:it|that|this|they)(?:\s+due)?\s*[?.!]*$")
CODE = re.compile(r"\b[A-Za-z]{2,5} ?\d{3,4}[A-Za-z]{0,2}\b")
# a term name such as "Fall 2026" looks like a course code and is not one
TERM_NAME = re.compile(r"\b(?:fall|winter|spring|summer)\s+20\d\d\b", re.IGNORECASE)
WORD = re.compile(r"[a-z0-9']+")


@lru_cache(maxsize=1)
def calendar_terms() -> list[str]:
    path = ROOT / "config" / "calendar_terms.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [t["term"] for t in config["terms"]]


def names_topic(words: list[str]) -> bool:
    return any(w.startswith(t) for w in words for t in TOPIC_WORDS)


def needs_clarification(question: str, intent: str | None = None) -> bool:
    """True when the question asks for "the deadline" and says nothing about which one."""
    if intent == "prerequisite":
        return False
    text = question.lower()
    words = WORD.findall(text)
    if not words or len(words) > MAX_WORDS:
        return False
    cued = any(re.search(rf"\b{cue}\b", text) for cue in CUES)
    if not (cued or VAGUE_WHEN.match(text.strip().replace("’", "'"))):
        return False
    if (
        names_topic(words)
        or CODE.search(TERM_NAME.sub(" ", question))
        or detect_departments(question)
    ):
        return False
    return True


def reply_text() -> str:
    """The fixed question. Nothing the student typed is ever copied into it."""
    terms = calendar_terms()
    term_list = ", ".join(terms[:-1]) + f" or {terms[-1]}"
    return (
        "I can help with that, but I need a little more detail. Which deadline do you mean: "
        "registration, tuition payment, dropping or withdrawing from a class, applying to "
        f"graduate, or financial aid? And for which term ({term_list})?"
    )
