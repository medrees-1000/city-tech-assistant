"""NO ADVICE (step 5): "should I drop this class?" gets the rules and dates, never a verdict.

Plain code detects the question (an advice cue and an action word) and writes the frame of the
answer. The answer has three parts (docs/decisions.md, "Step 5: NO ADVICE"):
  1. one fixed sentence, written here once;
  2. the policy rules, from the existing retrieval path run on a fixed question per action
     (never on the student's own text);
  3. the calendar rows for the action, chosen by a fixed pattern and rendered by the calendar
     renderer.
"""

import re
from dataclasses import dataclass
from datetime import date

from cta.answer import Answer
from cta.graph import render
from cta.graph.state import RoutedAnswer
from cta.index.search import Search

SENTENCE = "I can't tell you whether you should, but here are the rules and dates that apply."

CUES = (
    "should i", "should we", "do you think i should", "is it a good idea", "is it a bad idea",
    "would you recommend", "do you recommend", "what do you recommend", "would you advise",
    "would you suggest", "is it better to", "would it be better", "is it worth", "is it wise",
    "is it smart",
)  # fmt: skip

ARTICLE = r"(?:a |an |the |this |that |my |another )?"


@dataclass(frozen=True)
class Action:
    name: str
    words: re.Pattern  # the action word in the question
    query: str  # the fixed question retrieval answers
    calendar: re.Pattern | None  # which calendar rows of the term belong to it


def pattern(text: str) -> re.Pattern:
    return re.compile(text, re.IGNORECASE)


ACTIONS = (
    Action(
        "incomplete", pattern(r"\bincomplete\b"),
        "What are the rules for receiving an Incomplete grade and for completing it?",
        pattern(r"incomplete"),
    ),
    Action(
        "drop_withdraw", pattern(r"\b(?:drop|dropping|withdraw|withdrawing|withdrawal)\b"),
        "What are the rules and deadlines for dropping or withdrawing from a class?",
        pattern(r"drop|withdraw|grade of W"),
    ),
    Action(
        "audit", pattern(r"\baudit(?:ing)?\b"),
        "What are the rules for auditing a course?", None,
    ),
    Action(
        "payment_plan", pattern(r"\bpayment plan\b|\bnelnet\b"),
        "What are the rules and deadlines for the tuition payment plan?",
        pattern(r"payment plan"),
    ),
    Action(
        "sign_up", pattern(r"\bsign(?:ing)? up\b"),
        "What are the rules and deadlines for registering for classes?",
        pattern(r"regist|add a course"),
    ),
    Action(
        "change_major",
        pattern(r"\b(?:chang(?:e|ing)|switch(?:ing)?) (?:my )?major\b|\bdeclar(?:e|ing) a major\b"),
        "What are the rules and deadlines for changing or declaring a major?",
        pattern(r"major"),
    ),
    Action(
        "transfer", pattern(r"\btransfer(?:ring)?\b"),
        "What are the rules for transferring credits to City Tech?", None,
    ),
    Action(
        "take_class",
        pattern(rf"\b(?:take|taking|retake|retaking) {ARTICLE}(?:class|classes|course|courses)\b"),
        "What are the rules for repeating or retaking a course?", None,
    ),
)  # fmt: skip

# Phrases that would make an answer a recommendation. Checked by code on what the assistant writes.
BANNED = (
    "i recommend", "i'd recommend", "i would recommend", "my recommendation", "you should",
    "you ought", "i suggest", "i'd suggest", "i advise", "it is best", "it's best",
    "it would be better", "you'd be better", "better off", "consider dropping",
    "consider withdrawing", "is a good idea", "is a bad idea",
)  # fmt: skip


def advice_phrases(text: str) -> list[str]:
    """Banned phrases in the text. The fixed sentence is removed first: it says "whether you
    should" in order to refuse, which is not a recommendation."""
    lowered = text.replace(SENTENCE, "").lower().replace("’", "'")
    return [p for p in BANNED if p in lowered]


def matched_actions(question: str, intent: str | None = None) -> list[Action]:
    """The actions the question asks about, or [] when it is not an advice question."""
    if intent == "prerequisite":
        return []
    text = question.lower().replace("’", "'")
    if not any(re.search(rf"\b{cue}\b", text) for cue in CUES):
        return []
    return [a for a in ACTIONS if a.words.search(question)]


def needs_advice_rules(question: str, intent: str | None = None) -> bool:
    return bool(matched_actions(question, intent))


def rule_query(actions: list[Action]) -> str:
    """The fixed question for retrieval: the queries of the matched actions, in list order."""
    return " ".join(a.query for a in actions)


def calendar_rows(pool: list[dict], actions: list[Action]) -> list[dict]:
    """The rows of one term whose event text matches an action's pattern."""
    patterns = [a.calendar for a in actions if a.calendar]
    return [r for r in pool if any(p.search(r["event"]) for p in patterns)]


CITATION = re.compile(r"\[(\d+)\]")
MONTH_NAMES = (
    "january february march april may june july august september october november december".split()
)
WORD_DATE = re.compile(rf"\b({'|'.join(MONTH_NAMES)})\.? (\d{{1,2}})\b", re.IGNORECASE)
SLASH_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/\d{2,4})?\b")


def dates_in(text: str) -> set[tuple[int, int]]:
    """(month, day) of every "September 3" and "9/3" in the text."""
    found = {(MONTH_NAMES.index(m.group(1).lower()) + 1, int(m.group(2)))
             for m in WORD_DATE.finditer(text)}  # fmt: skip
    return found | {(int(m.group(1)), int(m.group(2))) for m in SLASH_DATE.finditer(text)}


def untraceable_dates(ans: Answer, today: date | None = None) -> set[tuple[int, int]]:
    """Dates in the answer that no cited source holds (an empty set is what the rule asks for).
    Today's date is allowed: it is the date the pipeline gives the model (docs/decisions.md)."""
    held: set[tuple[int, int]] = {(today.month, today.day)} if today else set()
    for n in ans.citations:
        if 1 <= n <= len(ans.sources):
            held |= dates_in(ans.sources[n - 1].get("text", ""))
    return dates_in(ans.text) - held


def shift(text: str, by: int) -> str:
    return CITATION.sub(lambda m: f"[{int(m.group(1)) + by}]", text)


def compose(found: Answer, rendered: render.Rendered | None) -> RoutedAnswer:
    """The answer: the fixed sentence, the policy answer, then the calendar rows. Calendar rows are
    numbered after the policy sources."""
    policy = found.text.strip()
    parts = [SENTENCE, policy]
    sources, citations = list(found.sources), list(found.citations)
    row_ids: list[str] = []
    if rendered and rendered.sources:
        by = len(sources)
        parts.append(shift(rendered.text, by))
        for i, chunk in enumerate(rendered.sources, 1):
            sources.append({**chunk, "text": shift(chunk["text"], by)})
            citations.append(by + i)
        row_ids = rendered.row_ids
    ans = RoutedAnswer(
        "\n\n".join(parts), False, None, sources, citations, list(found.invalid_citations),
        found.search or Search([], False, 0, 0, 0.0), found.prompt, found.prompt_tokens,
        found.completion_tokens, found.chat_cost, found.latency_ms, found.chat_ms,
    )  # fmt: skip
    ans.row_ids = row_ids
    return ans
