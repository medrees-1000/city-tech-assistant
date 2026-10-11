"""docs/eval-review.md: each question with the full text of its gold sources.

For writing the gold answers. Built by scripts/make_eval_review.py. A question whose gold sources
are empty or unresolved is marked.
"""

import json

from cta.eval.questions import (
    CALENDAR,
    GoldData,
    gold_problem,
    prerequisite_chain,
)

CHAINED = ("q20", "q22")  # chained prerequisites: also show a suggestion, not written to the file


def fence(text: str) -> str:
    return f"~~~~markdown\n{text}\n~~~~"


def section_text(sid: str, data: GoldData) -> str:
    """The full markdown of an indexed section, read from its record (ids count all sections)."""
    kind, rest = sid.split("/", 1)
    stem, n = rest.rsplit("#", 1)
    folder = {"page": "pages", "pdf": "pdfs", "dept": "departments"}[kind]
    record = json.loads((data.processed / folder / f"{stem}.json").read_text(encoding="utf-8"))
    return record["sections"][int(n) - 1]["markdown"]


def course_text(code: str, data: GoldData) -> str:
    out = []
    for rec in data.courses[code]:
        out.append(
            f"{rec['code']} - {rec['title']} ({rec['credits']} cr, {rec['department']})\n\n"
            f"Description: {rec['description']}\n\n"
            f"Prerequisite text: {rec['prerequisite_text'] or '(none)'}"
        )
    return "\n\n".join(out)


def event_text(event: dict) -> str:
    date = event["date_start"] or "TBA (not announced)"
    if event["date_end"]:
        date += f" to {event['date_end']}"
    rows = [
        ("term", event["term"]), ("event", event["event"]), ("date", date),
        ("weekday as printed", event["weekday_raw"]), ("applies to", event["applies_to"]),
        ("calendar last updated", event["pdf_last_updated"]), ("verified", event["verified"]),
        ("notes", event["notes"]),
    ]  # fmt: skip
    return "\n".join(f"- {k}: {v}" for k, v in rows if v not in (None, ""))


def source_block(src: dict, data: GoldData) -> list[str]:
    problem = gold_problem(src, data)
    head = f"**{src['id']}** — {src['heading']} ({src['source']})"
    if problem:
        return [head, "", f"**UNRESOLVED: {problem}**"]
    sid = src["id"]
    if sid.startswith("catalog:"):
        return [head, "", fence(course_text(sid.removeprefix("catalog:"), data))]
    if src["source"] == CALENDAR:
        return [head, "", event_text(data.events[sid])]
    return [head, "", fence(section_text(sid, data))]


def chain_block(code: str, data: GoldData) -> list[str]:
    chain = prerequisite_chain(code, data)
    lines = [
        f"**Suggestion for gold_sources (not in the file): chain below {code}**",
        "",
        f"- {code} prerequisite text: {chain['prerequisite_text']}",
        "- Courses it names, each with its own prerequisite text and the courses that names:",
    ]
    for c in chain["named"]:
        where = "" if c["in_catalog"] else " (not in the catalog data)"
        lines.append(f"  - {c['code']}{where}: {c['prerequisite_text'] or 'no prerequisite text'}")
        if c["names"]:
            lines.append(f"    - names: {', '.join(c['names'])}")
    return lines


def render(rows: list[dict], data: GoldData) -> str:
    lines = [
        "# Eval review",
        "",
        "Each question with the full text of its gold sources, for writing the gold answers.",
        "Built by `scripts/make_eval_review.py` from `eval/questions.jsonl`; do not edit.",
        "Questions marked **NO GOLD SOURCES** or **UNRESOLVED** need your attention.",
        "",
    ]
    for row in rows:
        sources = row["gold_sources"]
        unresolved = [s for s in sources if gold_problem(s, data)]
        marks = []
        if not sources:
            marks.append("NO GOLD SOURCES")
        if unresolved:
            marks.append("UNRESOLVED")
        flag = f" — **{' / '.join(marks)}**" if marks else ""
        lines += [
            f"## {row['id']}{flag}",
            "",
            f"**Question:** {row['question']}",
            "",
            f"type: {row['type']} | split: {row['split']} | department: {row['department'] or '-'}",
            "",
            f"Gold answer in the file: {row['gold_answer']}",
        ]
        if row["note"]:
            lines += ["", f"Note: {row['note']}"]
        for src in sources:
            lines += ["", *source_block(src, data)]
        if row["id"] in CHAINED:
            code = sources[0]["id"].removeprefix("catalog:")
            lines += ["", *chain_block(code, data)]
        lines.append("")
    return "\n".join(lines)
