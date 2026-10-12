# ruff: noqa: E501  (long prose strings: candidate notes and the generated text)
"""Write docs/calendar-candidates.md: about 14 calendar question candidates for the owner to review.

    uv run python scripts/make_calendar_candidates.py

Rules (docs/phase3-plan.md, step 4a-0):
- The questions are picked by category (SPECS below), from the calendar table, never from any system
  output. Nothing here is added to eval/questions.jsonl.
- Every gold answer is built mechanically from the row fields (event, date, term, last-updated date,
  source PDF); nothing comes from outside knowledge. The Registrar contact is read from the contact
  record (data/processed/contacts/registrar.json); if it is missing the text says TODO.
- The output is deterministic: the same inputs give the same file.
"""

import json
from datetime import date
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parents[1]
CALENDAR = ROOT / "data" / "calendar" / "calendar_events.json"
REGISTRAR = ROOT / "data" / "processed" / "contacts" / "registrar.json"
QUESTIONS = ROOT / "eval" / "questions.jsonl"
OUT = ROOT / "docs" / "calendar-candidates.md"
FIRST_ID = 61
TODAY = (
    "2026-10-12"  # the date the owner asked the term to be resolved from (config says 2026-10-11)
)
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]  # fmt: skip
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class Spec(TypedDict, total=False):
    question: str
    ids: list[str]  # calendar rows the gold is built from
    kind: str  # rows | tba | abstain | branches
    category: str
    assumed: str  # the term the gold assumes when the question names none
    type: str
    split: str
    tags: list[str]
    note: str
    flag: str


# ---- dates and gold text (pure functions, tested) ----


def day_text(d: date, with_year: bool = True) -> str:
    return f"{MONTHS[d.month - 1]} {d.day}" + (f", {d.year}" if with_year else "")


def date_in_words(row: dict) -> str:
    """'Friday, November 6, 2026', 'December 15-21, 2026 (Tuesday-Monday)', 'TBA (not announced)'.
    The year always comes from date_start, so a Winter row in January is 2027 and one in December
    is 2026. A range across months or years prints both ends in full."""
    if not row["date_start"]:
        return "TBA (not announced)"
    start = date.fromisoformat(row["date_start"])
    if not row["date_end"]:
        return f"{row['weekday_raw']}, {day_text(start)}"
    end = date.fromisoformat(row["date_end"])
    if (start.year, start.month) == (end.year, end.month):
        span = f"{MONTHS[start.month - 1]} {start.day}-{end.day}, {start.year}"
    elif start.year == end.year:
        span = f"{day_text(start, False)} - {day_text(end)}"
    else:
        span = f"{day_text(start)} - {day_text(end)}"
    return f"{span} ({row['weekday_raw']})"


def pdf_name(row: dict) -> str:
    return Path(row["source_pdf"]).name


def provenance(rows: list[dict]) -> str:
    """'(Fall 2026 calendar, fall_2026.pdf, last updated 2026-09-15; the calendar can change)' for
    each distinct term/PDF/date among the rows."""
    seen = dict.fromkeys(
        f"{r['term']} calendar, {pdf_name(r)}, last updated {r['pdf_last_updated']}" for r in rows
    )
    return "(" + "; ".join(seen) + "; the calendar can change)"


def row_sentence(row: dict) -> str:
    return f"{date_in_words(row)}: {row['event']} [{row['id']}]"


def gold_answer(spec: Spec, rows: list[dict], contact: str | None) -> str:
    kind = spec.get("kind", "rows")
    if kind == "abstain":
        return "ABSTAIN"
    reach = f"Registrar: {contact}" if contact else "Registrar contact: TODO"
    if kind == "tba":
        row = rows[0]
        return (
            f"Not announced yet: the {row['term']} calendar lists the date of "
            f'"{row["event"]}" as TBA [{row["id"]}] {provenance(rows)}. Contact the {reach}.'
        )
    text = "; ".join(row_sentence(r) for r in rows) + " " + provenance(rows)
    if spec.get("assumed"):
        text = f"Assumed term: {spec['assumed']} (from today's date, {TODAY}). " + text
    return text


def heading(row: dict) -> str:
    return f"{row['term']}: {row['event']}"


def weekday_problems(events: list[dict]) -> list[str]:
    """Rows whose printed weekday differs from the weekday of date_start (a range prints
    'Tuesday-Monday', so only the first name is compared)."""
    out = []
    for e in events:
        if not e["date_start"]:
            continue
        actual = WEEKDAYS[date.fromisoformat(e["date_start"]).weekday()]
        if e["weekday_raw"].split("-")[0] != actual:
            out.append(f"{e['id']}: printed {e['weekday_raw']}, {e['date_start']} is a {actual}")
    return out


def repeated_events(events: list[dict]) -> list[str]:
    """Events with the same text and date in more than one row (across terms or within one)."""
    seen: dict[tuple, list[str]] = {}
    for e in events:
        seen.setdefault((e["event"], e["date_start"]), []).append(e["id"])
    return [f'{", ".join(ids)}: "{ev}" on {d}' for (ev, d), ids in seen.items() if len(ids) > 1]


def weekend_deadlines(events: list[dict]) -> list[str]:
    out = []
    for e in events:
        if (
            e["date_start"]
            and not e["date_end"]
            and e["event"].lower().startswith(("last day", "deadline"))
        ):
            if date.fromisoformat(e["date_start"]).weekday() >= 5:
                out.append(f"{e['id']}: {e['weekday_raw']}, {e['date_start']}: {e['event']}")
    return out


# ---- the candidates (chosen by category) ----

SPECS: list[Spec] = [
    {"category": "simple date, Fall 2026",
     "question": "What is the last day to add a course in Fall 2026?",
     "ids": ["fall-2026-007"], "split": "dev",
     "note": "Same date as four other rows (75% refund, no-WD drop, credit/no-credit opt-in, aid status date); only -007 matches the question."},
    {"category": "simple date, Fall 2026",
     "question": "When does the filing period for Fall 2026 graduation begin?",
     "ids": ["fall-2026-028"], "split": "test",
     "note": "The end of the same period is -050 (December 21); the question asks only for the start."},
    {"category": "simple date, Winter 2027 (January: year 2027)",
     "question": "When does the Winter 2027 session start?",
     "ids": ["winter-2027-004"], "split": "dev",
     "note": "-005 'Classes begin' has the same date and is not needed. Differs from q12 (end of the session)."},
    {"category": "simple date, Winter 2027 (December: year 2026)",
     "question": "What is the last day to file an ePermit request for the Winter session?",
     "ids": ["winter-2027-001"], "split": "dev",
     "note": "The row is dated December 28 in the Winter 2027 calendar; the year printed in the answer must be 2026, not 2027."},
    {"category": "simple date, Spring 2027",
     "question": "What is the last day to drop for a 50% tuition refund in Spring 2027?",
     "ids": ["spring-2027-017"], "split": "dev",
     "note": "Four refund rows share the term (100%, 75%, 50%, 25%); the percentage picks one."},
    {"category": "simple date, Spring 2027",
     "question": "When does the filing period for Spring 2027 graduation end?",
     "ids": ["spring-2027-051"], "split": "test",
     "note": "The start is -027 (February 22); the question asks for the end."},
    {"category": "start and end in one question (finals)",
     "question": "When are final exams in Spring 2027?",
     "ids": ["spring-2027-050"], "split": "dev",
     "note": "A seven-day range. The Fall 2026 version is q36 (this fall)."},
    {"category": "start and end in one question (Plan Week, 'fall semester' wording)",
     "question": "When is Plan Week in the fall semester?",
     "ids": ["fall-2026-035"], "split": "dev", "assumed": "Fall 2026",
     "note": "A range; the row is the wrapped (two printed lines) row. 'Fall semester' must resolve to Fall 2026."},
    {"category": "start and end in one question ('this spring' wording)",
     "question": "When is spring recess this spring?",
     "ids": ["spring-2027-045"], "split": "test", "assumed": "Spring 2027",
     "flag": "'This spring' on 2026-10-12 can only mean the coming Spring 2027 term; the owner should decide whether that wording is natural in October.",
     "note": "April 21-29 (printed weekday 'Wednesday-Thursday'): nine days."},
    {"category": "TBA row",
     "question": "When is graduation ceremony day in 2027?", "kind": "tba",
     "ids": ["spring-2027-055"], "split": "dev",
     "flag": "DUPLICATE RISK: q11 ('When is the 87th Commencement Ceremony?', test) has the same gold row. This is a paraphrase without the ordinal; recommend drop unless a paraphrase is wanted.",
     "note": "Date is null in the table. The answer must say it is not announced and give the Registrar contact."},
    {"category": "no term stated",
     "question": "What is the last day to withdraw from a course with a W?",
     "ids": ["fall-2026-040"], "split": "dev", "assumed": "Fall 2026",
     "note": "The term must come from today's date. Nearby rows: -024 (withdrawal period begins), -025 (W assigned). q31 asks the same with the term stated."},
    {"category": "unsupported term",
     "question": "When do classes begin in Fall 2027?", "kind": "abstain", "ids": [],
     "type": "unanswerable", "split": "test",
     "note": "No Fall 2027 calendar is published. Abstain with the Registrar contact. Differs from q25 and q34 (Summer 2027)."},
    {"category": "term whose rows sit in another term's calendar",
     "question": "When does online registration for Fall 2027 begin for all students?",
     "ids": ["spring-2027-040"], "split": "test",
     "flag": "Trap for an over-eager 'unsupported term' rule: Fall 2027 has no calendar, but the Spring 2027 calendar has its registration rows. The early registration row (-038) is for named populations only (see q37's gold for the same pattern).",
     "note": "Answered from the Spring 2027 calendar (like q37 for Spring registration in the Fall calendar)."},
    {"category": "several rows could match",
     "question": "What is the last day to drop a class in Fall 2026?", "kind": "branches",
     "ids": ["fall-2026-004", "fall-2026-008", "fall-2026-011", "fall-2026-016", "fall-2026-019", "fall-2026-021"],
     "type": "ambiguous", "split": "test",
     "flag": "Owner decision: either answer every branch (this gold) or CLARIFY ('for a refund, or without a grade of WD?'). Six rows collide.",
     "note": "Rows: 100% refund Aug 27 (-004), 75% refund Sep 3 (-008), drop without WD Sep 3 (-011), 50% refund Sep 10 (-016), 25% refund Sep 17 (-019), drop with WD Sep 17 (-021). 'Course Withdrawal period begins' (-024) is a withdrawal, not a drop."},
    {"category": "holiday / college closed",
     "question": "When is Thanksgiving break in the fall semester?",
     "ids": ["fall-2026-046", "fall-2026-045", "fall-2026-047"], "split": "dev", "assumed": "Fall 2026",
     "flag": "-045 (Nov 25) and -047 (Nov 28) are 'No classes scheduled', not 'College Closed'; the closed days are only -046 (Nov 26-27). Owner: keep all three or only -046?",
     "note": "The rows differ in meaning (closed vs no classes), so the gold lists all three."},
]  # fmt: skip


def build(events: list[dict], contact: str | None) -> list[dict]:
    """The candidates as dicts with the gold text, rows and ids filled in."""
    by_id = {e["id"]: e for e in events}
    out = []
    for n, spec in enumerate(SPECS):
        rows = [by_id[i] for i in spec["ids"]]
        out.append({
            "id": f"q{FIRST_ID + n}",
            "spec": spec,
            "rows": rows,
            "gold": gold_answer(spec, rows, contact),
            "type": spec.get("type", "time_sensitive"),
            "tags": ["calendar", *spec.get("tags", [])],
            "sources": [{"id": r["id"], "source": "data/calendar/calendar_events.json",
                         "heading": heading(r)} for r in rows],
        })  # fmt: skip
    return out


# ---- the file ----


def existing_calendar_questions() -> list[str]:
    out = []
    for line in QUESTIONS.read_text(encoding="utf-8").splitlines():
        q = json.loads(line)
        if any(g["id"].split("-")[0] in ("fall", "winter", "spring") for g in q["gold_sources"]):
            out.append(f"{q['id']} ({q['split']}): {q['question']}")
    return out


def render(events: list[dict], contact: str | None, existing: list[str]) -> str:
    items = build(events, contact)
    dev = sum(c["spec"]["split"] == "dev" for c in items)
    out = [
        "# Calendar question candidates (for the owner to review)",
        "",
        "Generated by `scripts/make_calendar_candidates.py` from `data/calendar/calendar_events.json`. "
        f"**{len(items)} candidates, ids from q{FIRST_ID}, proposed split {dev} dev / {len(items) - dev} test.** "
        "Nothing here is in `eval/questions.jsonl`. Questions were chosen by category from the calendar table; "
        "no system output was used. Every gold answer is built mechanically from the row fields "
        "(event, date, term, PDF last-updated date); check each row against your copy of the PDF named in the candidate.",
        "",
        f"- `applies_to` is empty in {sum(not e['applies_to'] for e in events)} of {len(events)} rows; where it is set it narrows who the row is "
        "for (listed at the end). The chosen rows have it empty, except `spring-2027-040` (all students).",
        f"- 'Today' for the term-resolution candidates is {TODAY} (the date you gave; `eval.today` in `config/models.yaml` is 2026-10-11, same terms).",
        "- Existing questions with calendar gold (not duplicated except where flagged): "
        + "; ".join(existing)
        + ".",
        "",
    ]
    for c in items:
        s = c["spec"]
        out += [
            f"## {c['id']} — {s['category']}",
            "",
            f"- **Question:** {s['question']}",
            f"- **Type:** {c['type']}  |  **Proposed split:** {s['split']}  |  **Tags:** {', '.join(c['tags'])}",
            f"- **Source PDF to check:** {', '.join(dict.fromkeys(pdf_name(r) for r in c['rows'])) or '(none: no calendar exists for this term)'}",
            f"- **Gold row ids:** {', '.join(r['id'] for r in c['rows']) or '(none)'}",
        ]
        if s.get("flag"):
            out.append(f"- **FLAG:** {s['flag']}")
        out += [f"- **Note:** {s['note']}", "", f"**Draft gold answer (built from the rows; {'DRAFT: owner must review'}):**", "",
                f"> {c['gold']}", ""]  # fmt: skip
        if s.get("kind") == "abstain":
            out += [
                f"The assistant should abstain and give the Registrar contact ({contact or 'TODO'}).",
                "",
            ]
        if c["rows"]:
            out += ["Rows as stored:", "", "```json"]
            out += [json.dumps(r, ensure_ascii=False) for r in c["rows"]]
            out += ["```", ""]
    out += [
        "## Checklist for the owner",
        "",
        "| id | date matches PDF (yes/no) | question natural (yes/no) | keep / edit / drop |",
        "|---|---|---|---|",
    ]
    out += [f"| {c['id']} | | | |" for c in items]
    out += ["", "## What looked wrong or inconsistent while building this (data not changed)", ""]
    out += consistency_section(events)
    return "\n".join(out) + "\n"


def consistency_section(events: list[dict]) -> list[str]:
    def block(title: str, lines: list[str]) -> list[str]:
        return [f"**{title}** ({len(lines)})", ""] + [f"- {x}" for x in lines or ["none"]] + [""]

    applies = [f"{e['id']}: {e['applies_to']}" for e in events if e["applies_to"]]
    unnamed_closed = [
        f"{e['id']}: {e['weekday_raw']}, {e['date_start']}: {e['event']}"
        for e in events
        if e["event"].strip().rstrip(".") == "College Closed"
    ]
    return (
        block("Weekday printed differs from the date", weekday_problems(events))
        + block("Same event and date in more than one row", repeated_events(events))
        + block("'Last day' or 'Deadline' rows that fall on a weekend", weekend_deadlines(events))
        + block("Rows where applies_to is set", applies)
        + block("'College Closed' rows with no holiday name", unnamed_closed)
        + [
            "**Other observations**",
            "",
            "- `fall-2026-055` (January 1, 2027, the only row with a printed year) sits in the Fall 2026 calendar and repeats `winter-2027-002`. "
            "A question about New Year's Day closure has two correct rows in two terms.",
            "- The Fall 2026 calendar also holds rows dated before the term (July 9, August 21) and the Winter and Spring calendars hold January rows that overlap "
            "(`winter-2027-017/018` and `spring-2027-001/002` are the same appeals deadline in both). The term of a question does not always decide which calendar a row is in.",
            "- `fall-2026-002`, `-042`, `winter-2027-018` and `spring-2027-002`, `-047` are rows whose event text is only a 'For more info' web address, split from the appeals row above them.",
            "- Some deadline rows are dated on a weekend (listed above); the owner may want to confirm those against the PDFs.",
            "- Rows -035 (Plan Week), -038 and the appeals rows were printed on two lines and joined by the parser; their text is as stored.",
        ]
    )


def main() -> int:
    events = json.loads(CALENDAR.read_text(encoding="utf-8"))
    contact = None
    if REGISTRAR.exists():
        record = json.loads(REGISTRAR.read_text(encoding="utf-8"))
        contact = ", ".join([*record["emails"], *record["phones"]]) or None
    OUT.write_text(render(events, contact, existing_calendar_questions()), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
