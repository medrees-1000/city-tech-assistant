"""CLARIFY (step 4): a short, generic deadline question gets a fixed question back.

Plain code, no model call. It runs after the classifier and before the calendar and retrieval
nodes. It fires only when every condition holds (docs/decisions.md, "Step 4: CLARIFY"):
  1. the question is short (at most MAX_WORDS words);
  2. it holds a generic deadline cue ("deadline", "due date", "last day");
  3. it names no topic (TOPIC_WORDS), no course code and no department;
  4. the classifier did not say "prerequisite".
The reply is a fixed template; the terms in it are read from config/calendar_terms.yaml.
"""

import re
from functools import lru_cache

import yaml

from cta.index.departments import detect_departments
from cta.settings import ROOT

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
    if not any(re.search(rf"\b{cue}\b", text) for cue in CUES):
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
