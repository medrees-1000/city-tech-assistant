# ruff: noqa: E501
"""The labeled items and the planted errors for the judge-variant test (step 4-judge). No model call.

Items are read from eval/judge_labels.json (references to stored runs: the answer comes from
request_logs and its five sources from the chunks table). Planted errors are generated here from those
references at run time; nothing derived is stored.

(a) Number plants. For every labeled item whose faithfulness label is "yes" and whose answer is not an
    ABSTAIN: scan the answer left to right (citation markers like [1] are ignored) for the first number
    or course code that also appears in the item's sources; replace that one occurrence by a different
    value of the same kind that appears nowhere in the five sources (numbers: the next integers up;
    course codes: the same prefix and suffix with the next course numbers up). Skip the item if there is
    no such token. Expected faithfulness: not "yes".
(b) Cross-pairs. For the "the sources do not state X" rule: the stored baseline answer paired with the
    on-run1 sources of the same question (q22 and q52), where the claim is false. Expected: not "yes".
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from cta.answer import format_source
from cta.settings import ROOT

LABELS = ROOT / "eval" / "judge_labels.json"
CORRECTNESS = ("correct", "partial", "incorrect")
FAITHFULNESS = ("yes", "partly", "no")
CROSS_QUESTIONS = ("q22", "q52")
CROSS_ANSWER_RUN, CROSS_SOURCE_RUN = "baseline-dev-60-v3", "on-run1"
CITATION = re.compile(r"\[\d+\]")
TOKEN = re.compile(
    r"(?P<code>\b[A-Z]{2,5} ?\d{3,4}[A-Z]{0,2}\b)|(?P<num>(?<![\w.])\d+(?:[.,]\d+)*(?![\w]))"
)
CODE_PARTS = re.compile(r"^([A-Z]{2,5})( ?)(\d{3,4})([A-Z]{0,2})$")
MAX_STEPS = 99


@dataclass
class Item:
    key: str  # "q22|on-run1" for a labeled item, "plant:q22|on-run1", "cross:q22"
    kind: str  # real | plant_number | plant_cross
    question: dict
    answer: str
    sources: list[dict]
    label: dict | None = None  # {"correctness", "faithfulness", "source", "note"} for real items
    note: str = ""  # what was planted
    expected_not_yes: bool = False
    meta: dict = field(default_factory=dict)


def load_labels(path: Path = LABELS) -> list[dict]:
    """The label entries, checked: required fields, allowed values, no duplicate (question, run)."""
    entries = json.loads(path.read_text(encoding="utf-8"))["items"]
    seen = set()
    for e in entries:
        missing = [
            k for k in ("question", "run", "correctness", "faithfulness", "source") if k not in e
        ]
        if missing:
            raise ValueError(f"label {e.get('question')}: missing {missing}")
        if e["correctness"] not in CORRECTNESS or e["faithfulness"] not in FAITHFULNESS:
            raise ValueError(f"label {e['question']}|{e['run']}: bad verdict value")
        if e["source"] not in ("owner", "second reader"):
            raise ValueError(
                f"label {e['question']}|{e['run']}: source must be owner or second reader"
            )
        key = (e["question"], e["run"])
        if key in seen:
            raise ValueError(f"duplicate label {key}")
        seen.add(key)
    return entries


def source_text(sources: list[dict]) -> str:
    """What the answerer saw, in full (headers included)."""
    return "\n\n".join(format_source(n, c) for n, c in enumerate(sources, 1))


def own_text(sources: list[dict]) -> str:
    """The sources' own words: headings and text, without the numbering lines."""
    return "\n".join(f"{c['heading_path']}\n{c['text']}" for c in sources)


def contains_token(text: str, token: str) -> bool:
    """The token as a whole word or number in the text (a course code also with its space removed or added)."""
    forms = {token, token.replace(" ", "")}
    parts = CODE_PARTS.match(token)
    if parts:
        forms.add(f"{parts[1]} {parts[3]}{parts[4]}")
    return any(re.search(rf"(?<![\w.]){re.escape(f)}(?![\w])", text) for f in forms)


def replacement(token: str, sources_full: str) -> str | None:
    """A different value of the same kind that appears nowhere in the sources, or None."""
    parts = CODE_PARTS.match(token)
    if parts:
        prefix, space, digits, suffix = parts.groups()
        for step in range(1, MAX_STEPS + 1):
            digits_new = str(int(digits) + step).zfill(len(digits))
            candidate = f"{prefix}{space}{digits_new}{suffix}"
            if not re.search(rf"(?<!\d){digits_new}(?!\d)", sources_full):
                return candidate
        return None
    comma = "," in token and "." not in token
    head, dot, tail = token.replace(",", "").partition(".")
    for step in range(1, MAX_STEPS + 1):
        value = int(head) + step
        shown = f"{value:,}" if comma else str(value)
        if not re.search(rf"(?<!\d){re.escape(str(value))}(?!\d)", sources_full):
            return f"{shown}{dot}{tail}"
    return None


def plant_number(answer: str, sources: list[dict]) -> tuple[str, str] | None:
    """(planted answer, description) or None if no token of the answer is in the sources."""
    masked = CITATION.sub(lambda m: " " * len(m.group()), answer)
    own, full = own_text(sources), source_text(sources)
    for m in TOKEN.finditer(masked):
        token = m.group()
        if not contains_token(own, token):
            continue
        new = replacement(token, full)
        if new is None:
            continue
        return answer[: m.start()] + new + answer[m.end() :], f"{token} -> {new}"
    return None


def is_abstain(answer: str) -> bool:
    return answer.strip().startswith("ABSTAIN:")


def number_plants(items: list[Item]) -> list[Item]:
    out = []
    for item in items:
        if item.kind != "real" or item.label["faithfulness"] != "yes" or is_abstain(item.answer):
            continue
        planted = plant_number(item.answer, item.sources)
        if planted:
            text, what = planted
            out.append(Item(f"plant:{item.key}", "plant_number", item.question, text, item.sources,
                            None, what, True, {"from": item.key}))  # fmt: skip
    return out


def cross_pairs(items: list[Item]) -> list[Item]:
    """The baseline answer with the on-run1 sources, for the questions where that makes the 'the
    sources do not state X' claim false."""
    by_key = {i.key: i for i in items}
    out = []
    for qid in CROSS_QUESTIONS:
        a, s = by_key.get(f"{qid}|{CROSS_ANSWER_RUN}"), by_key.get(f"{qid}|{CROSS_SOURCE_RUN}")
        if a and s:
            out.append(Item(f"cross:{qid}", "plant_cross", a.question, a.answer, s.sources, None,
                            f"answer of {CROSS_ANSWER_RUN} with the sources of {CROSS_SOURCE_RUN}",
                            True, {"from": a.key}))  # fmt: skip
    return out


def load_real_items(conn, labels: list[dict] | None = None) -> list[Item]:
    """The labeled items with their stored answer and sources (reads request_logs and chunks)."""
    from cta.eval.judge_sheet import load_chunks, stored_answer
    from cta.eval.questions import load_questions

    questions = {q["id"]: q for q in load_questions()}
    items = []
    for e in labels or load_labels():
        q = questions[e["question"]]
        text, ids = stored_answer(conn, e["run"], q["question"])
        items.append(
            Item(f"{e['question']}|{e['run']}", "real", q, text, load_chunks(conn, ids), e)
        )
    return items


def all_items(conn) -> list[Item]:
    real = load_real_items(conn)
    return real + number_plants(real) + cross_pairs(real)
