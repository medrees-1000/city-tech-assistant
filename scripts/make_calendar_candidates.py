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
TODAY = "2026-10-11"  # eval.today in config/models.yaml (the owner kept it at this date)
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
    decision: str  # owner's decision: keep | edit | drop
    clarify: str  # the CLARIFY rule text that opens a CLARIFY gold


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
    if kind == "branches":
        facts = "; ".join(row_sentence(r) for r in rows) + " " + provenance(rows)
        return f"{spec['clarify']} Facts: {facts}"
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
     "question": "When is spring break this spring?",
     "ids": ["spring-2027-045"], "split": "test", "assumed": "Spring 2027", "decision": "edit",
     "note": "Owner edit: the student says 'spring break'; the calendar row says 'Spring Recess' (April 21-29, printed weekday 'Wednesday-Thursday', nine days). 'This spring' on eval.today (2026-10-11) means the coming Spring 2027 term."},
    {"category": "TBA row",
     "question": "When is graduation ceremony day in 2027?", "kind": "tba",
     "ids": ["spring-2027-055"], "split": "dev", "decision": "drop",
     "flag": "DROPPED by the owner: its gold row is the same as q11 (test), and a dev copy would make the test case easy. The TBA rule (null date means 'not announced' plus the Registrar contact) is covered by unit tests in step 4a; q11 is the end-to-end check in the test split.",
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
     "clarify": "CLARIFY OR ALL BRANCHES: either ask which kind of drop is meant (a drop for a tuition refund, a drop without a grade of WD, or a drop with a grade of WD), or answer every branch correctly from the calendar with sources; never give one date as if it applied to all of them.",
     "flag": "Owner decision: stays type ambiguous with the existing CLARIFY rule (passes if it asks which one, or lists every branch correctly with sources). Six rows collide.",
     "note": "Rows: 100% refund Aug 27 (-004), 75% refund Sep 3 (-008), drop without WD Sep 3 (-011), 50% refund Sep 10 (-016), 25% refund Sep 17 (-019), drop with WD Sep 17 (-021). 'Course Withdrawal period begins' (-024) is a withdrawal, not a drop."},
    {"category": "holiday / college closed",
     "question": "What days are off for Thanksgiving break?",
     "ids": ["fall-2026-046", "fall-2026-045", "fall-2026-047"], "split": "dev", "assumed": "Fall 2026",
     "decision": "edit",
     "flag": "Owner decision: the gold stays the three rows. -045 (Nov 25) and -047 (Nov 28) are 'No classes scheduled', not 'College Closed'; the closed days are only -046 (Nov 26-27).",
     "note": "The rows differ in meaning (closed vs no classes), so the gold lists all three."},
]  # fmt: skip


# ---- the independent PDF check (step 4a-1) ----
# Read by Claude Code from page images rendered with pdfplumber's page.to_image (pypdfium2), NOT from
# the text layer or the original parser: (date, weekday, event text) as printed. The comparison with
# the stored rows below is mechanical (whitespace collapsed).

CHECKED_ON = "2026-10-12"
METHOD = "page image (pdfplumber page.to_image), read by eye"
METHOD_SHORT = "image"
PDF_PRINTS: dict[str, tuple[str, str, str]] = {
    "fall-2026-004": ("August 27", "Thursday", "Last day to drop for 100% tuition refund."),
    "fall-2026-007": ("September 03", "Thursday", "Last day to add a course."),
    "fall-2026-008": ("September 03", "Thursday", "Last day to drop for 75% tuition refund."),
    "fall-2026-011": ("September 03", "Thursday", "Last Day to drop without a grade of WD"),
    "fall-2026-016": ("September 10", "Thursday", "Last day to drop for 50% tuition refund"),
    "fall-2026-019": ("September 17", "Thursday", "Last day to drop for 25% tuition refund."),
    "fall-2026-021": ("September 17", "Thursday", "Last day to drop a course with a grade of WD."),
    "fall-2026-028": ("October 05", "Monday", "Filing Period for Fall 2026 graduation begins"),
    "fall-2026-035": ("October 19-23", "Monday-Friday", "Plan Week: Students plan course registration for the following semester and connect with an advisor."),
    "fall-2026-040": ("November 06", "Friday", "Last day to withdraw from a course with a grade of W."),
    "fall-2026-045": ("November 25", "Wednesday", "No classes scheduled"),
    "fall-2026-046": ("November 26-27", "Thursday-Friday", "Thanksgiving Holiday. College Closed"),
    "fall-2026-047": ("November 28", "Saturday", "No classes scheduled"),
    "winter-2027-001": ("December 28", "Monday", "Last day to file ePermit request for the Winter Session"),
    "winter-2027-003": ("January 03", "Sunday", "Last day to drop for 100% tuition refund."),
    "winter-2027-004": ("January 04", "Monday", "Start of Winter 2027 session."),
    "winter-2027-019": ("January 17", "Sunday", "Last day to withdraw from a course with a grade of W."),
    "spring-2027-017": ("February 10", "Wednesday", "Last day to drop for 50% tuition refund"),
    "spring-2027-040": ("March 22", "Monday", "Online registration for Fall 2027 begins for all students."),
    "spring-2027-045": ("April 21-29", "Wednesday-Thursday", "Spring Recess"),
    "spring-2027-050": ("May 21-27", "Friday-Thursday", "Final Examinations"),
    "spring-2027-051": ("May 27", "Thursday", "Filing period for Spring 2027 graduation ends"),
}  # fmt: skip
PRINTED_UPDATED = {
    "fall_2026.pdf": "9/15/26",
    "winter_2027.pdf": "7/27/26",
    "spring_2027.pdf": "7/27/26",
}
EXTRA_CHECK_ROWS = [
    "winter-2027-003",
    "winter-2027-019",
]  # the two Sunday rows (no question needs them)


def same_text(a: str, b: str) -> bool:
    return " ".join(a.split()) == " ".join(b.split())


def check_rows(events: list[dict], prints: dict[str, tuple[str, str, str]]) -> list[dict]:
    """For each row read from the PDF: what the PDF prints, what the table stores, and whether the
    date, weekday and event text agree. The page number is the one stored with the row."""
    by_id = {e["id"]: e for e in events}
    out = []
    for rid, (date_text, weekday, event) in prints.items():
        row = by_id[rid]
        diffs = [
            name
            for name, printed, stored in (
                ("date", date_text, row["date_raw"]),
                ("weekday", weekday, row["weekday_raw"]),
                ("event", event, row["event"]),
            )
            if not same_text(printed, stored)
        ]
        out.append({
            "id": rid, "printed": f"{date_text} / {weekday} / {event}",
            "stored": f"{row['date_raw']} / {row['weekday_raw']} / {row['event']}",
            "match": "yes" if not diffs else "NO: " + ", ".join(diffs),
            "page": row["source_page"], "pdf": pdf_name(row),
        })  # fmt: skip
    return out


def kept_questions_using(items: list[dict]) -> dict[str, list[str]]:
    """Row id -> the kept or edited questions whose gold uses it."""
    used: dict[str, list[str]] = {}
    for c in items:
        if c["spec"].get("decision", "keep") != "drop":
            for r in c["rows"]:
                used.setdefault(r["id"], []).append(c["id"])
    return used


def check_section(events: list[dict], items: list[dict]) -> list[str]:
    results = check_rows(events, PDF_PRINTS)
    used = kept_questions_using(items)
    out = [
        "## Independent PDF check of the gold rows",
        "",
        f"Checked by Claude Code on {CHECKED_ON}; **owner spot-check pending** (this is not owner verification). "
        f"Method: {METHOD}: each page was rendered to an image and the event text, date and weekday were read from the image, "
        "then compared (whitespace collapsed) with the stored row. The original text parser was not used. A model reading "
        "an image can misread a character, so the rows in the eyeball list below are still worth a look. "
        "The printed 'Last updated' date of each PDF also matches `pdf_last_updated`: "
        + ", ".join(f"{k} {v}" for k, v in PRINTED_UPDATED.items())
        + ".",
        "",
        "| row id | page | PDF prints (date / weekday / event) | table stores | match | used by | method |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        out.append(
            f"| {r['id']} | {r['pdf']} p{r['page']} | {r['printed']} | {r['stored']} | {r['match']} | "
            f"{', '.join(used.get(r['id'], [])) or '(Sunday-row check)'} | {METHOD_SHORT} |"
        )
    bad = [r["id"] for r in results if r["match"] != "yes"]
    out += ["", f"Rows that disagree or are unclear: {bad or 'none'}.", ""]
    out += [
        "Printed years: the PDFs print no year except `January 01, 2027`. The stored years were not read from the image; "
        "they come from the term, and every stored weekday agrees with its date (checked by the script, see below).",
        "",
        "Rows for you to eyeball on the PDF yourself:",
        "",
    ]
    pages = {r["id"]: f"{r['pdf']} page {r['page']}" for r in results}
    out += [
        f"1. The six q74 rows, `fall-2026-004`, `-008`, `-011`, `-016`, `-019`, `-021`: {pages['fall-2026-004']} "
        "(the 'fall-2026-004 to -021' range also holds other rows; only these six matter).",
        f"2. The December 28 ePermit row, `winter-2027-001`: {pages['winter-2027-001']}.",
        f"3. The Thanksgiving rows: `fall-2026-045` (Nov 25): {pages['fall-2026-045']}; `fall-2026-046` (Nov 26-27) and "
        f"`fall-2026-047` (Nov 28): {pages['fall-2026-046']}.",
        f"4. The Spring finals range, `spring-2027-050`: {pages['spring-2027-050']}.",
        "",
    ]
    return out


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


def question_row(c: dict, contact: str | None) -> dict:
    """The eval/questions.jsonl row of a kept candidate (same fields as the existing rows)."""
    return {
        "id": c["id"],
        "question": c["spec"]["question"],
        "gold_answer": c["gold"],
        "gold_sources": c["sources"],
        "type": c["type"],
        "department": None,
        "split": c["spec"]["split"],
        "note": c["spec"]["note"] + (f" Registrar contact: {contact}." if c["spec"].get("kind") == "abstain" and contact else ""),
        "tags": c["tags"],
    }  # fmt: skip


def kept_rows(events: list[dict], contact: str | None) -> list[dict]:
    return [
        question_row(c, contact)
        for c in build(events, contact)
        if c["spec"].get("decision", "keep") != "drop"
    ]


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
    kept = [c for c in items if c["spec"].get("decision", "keep") != "drop"]
    dev = sum(c["spec"]["split"] == "dev" for c in kept)
    out = [
        "# Calendar question candidates (for the owner to review)",
        "",
        "Generated by `scripts/make_calendar_candidates.py` from `data/calendar/calendar_events.json`. "
        f"**{len(items)} candidates, ids from q{FIRST_ID}; the owner kept or edited {len(kept)} and dropped {len(items) - len(kept)} "
        f"(q70); split {dev} dev / {len(kept) - dev} test.** The kept ones are merged into `eval/questions.jsonl` by "
        "`scripts/merge_calendar_questions.py` (step 4a-1). Questions were chosen by category from the calendar table; "
        "no system output was used. Every gold answer is built mechanically from the row fields "
        "(event, date, term, PDF last-updated date); check each row against your copy of the PDF named in the candidate.",
        "",
        f"- `applies_to` is empty in {sum(not e['applies_to'] for e in events)} of {len(events)} rows; where it is set it narrows who the row is "
        "for (listed at the end). The chosen rows have it empty, except `spring-2027-040` (all students).",
        f"- 'Today' for the term-resolution candidates is {TODAY}, which is `eval.today` in `config/models.yaml` (unchanged; the terms are the same as on 2026-10-12).",
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
    out += check_section(events, items)
    out += [
        "## Checklist: owner decisions (2026-10-12)",
        "",
        "'Date matches PDF' is the independent check above (Claude Code, owner spot-check pending). "
        "'Question natural': yes for all except q69 and q75, which the owner edited (new wording is in the candidate).",
        "",
        "| id | date matches PDF | question natural | keep / edit / drop | split |",
        "|---|---|---|---|---|",
    ]
    checked = {r["id"]: r["match"] for r in check_rows(events, PDF_PRINTS)}
    for c in items:
        d = c["spec"].get("decision", "keep")
        rows_ok = [checked.get(r["id"]) for r in c["rows"]]
        date_ok = (
            "n/a (no row)"
            if not rows_ok
            else ("yes" if all(x == "yes" for x in rows_ok) else "NOT CHECKED OR NO")
        )
        natural = "edited" if d == "edit" else ("n/a" if d == "drop" else "yes")
        out.append(
            f"| {c['id']} | {date_ok} | {natural} | {d} | {c['spec']['split'] if d != 'drop' else '-'} |"
        )
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
