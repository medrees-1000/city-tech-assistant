"""Load and check eval/questions.jsonl (CLAUDE.md, "Evaluation").

Run: uv run python -m cta.eval.questions
Row checks: required fields, type, split, unique ids, department. Gold-source checks: a section id
must exist in the section index data (embed true) with the same source and heading path, a
"catalog:<CODE>" must be a course record, a calendar entry must be a verified event. Question text,
splits and gold answers are never changed by this module. Not part of CI yet.
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from cta.index.section_index import load_rows
from cta.settings import ROOT

QUESTIONS = ROOT / "eval" / "questions.jsonl"
CALENDAR = "data/calendar/calendar_events.json"
FIELDS = ("id", "question", "gold_answer", "gold_sources", "type", "department", "split", "note")
TYPES = ("lookup", "multi_chunk", "time_sensitive", "ambiguous", "unanswerable")
SPLITS = ("dev", "test")
DEPARTMENTS = ("CST-NYT", "MATH-NYT", "EET-NYT", "DENT-NYT")
NEEDS_SOURCES = ("lookup", "multi_chunk", "time_sensitive")  # the others may have none
SECTION_ID = re.compile(r"^(page|pdf|dept)/.+#\d+$")
LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
COURSE_CODE = re.compile(r"\b([A-Z]{2,5}) ?(\d{3,4}[A-Z]{0,2})\b")


def load_questions(path: Path = QUESTIONS) -> list[dict]:
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path.name} line {n}: not valid JSON ({e})") from e
    return rows


def plain(heading: str) -> str:
    """A heading without markdown link markup: "[CIS/AAS](https://...)" -> "CIS/AAS". Some stored
    headings carry the link; the gold file gives the visible text."""
    return LINK.sub(r"\1", heading)


def row_problems(row: dict) -> list[str]:
    """Problems with the row itself (not its gold sources)."""
    problems = [f"missing field {f}" for f in FIELDS if f not in row]
    if row.get("type") not in TYPES:
        problems.append(f"type {row.get('type')!r} is not one of {'|'.join(TYPES)}")
    if row.get("split") not in SPLITS:
        problems.append(f"split {row.get('split')!r} is not dev or test")
    if (
        "department" in row
        and row["department"] is not None
        and row["department"] not in DEPARTMENTS
    ):
        problems.append(f"department {row['department']!r} is not one of the four ids or null")
    for f in ("id", "question", "gold_answer"):
        if f in row and (not isinstance(row[f], str) or not row[f].strip()):
            problems.append(f"{f} is empty")
    sources = row.get("gold_sources")
    if "gold_sources" in row and not isinstance(sources, list):
        problems.append("gold_sources is not a list")
    else:
        for i, s in enumerate(sources or [], 1):
            missing = [
                k for k in ("id", "source", "heading") if not isinstance(s, dict) or k not in s
            ]
            if missing:
                problems.append(f"gold source {i} lacks {missing}")
    return problems


def duplicate_ids(rows: list[dict]) -> set[str]:
    seen: set[str] = set()
    return {r["id"] for r in rows if r.get("id") in seen or seen.add(r.get("id"))}  # type: ignore[func-returns-value]


@dataclass
class GoldData:
    sections: dict[str, dict] = field(default_factory=dict)  # section id -> index row (embed true)
    courses: dict[str, list[dict]] = field(default_factory=dict)  # code -> course records
    events: dict[str, dict] = field(default_factory=dict)  # event id -> calendar event
    processed: Path = ROOT / "data" / "processed"


def load_gold_data(root: Path = ROOT) -> GoldData:
    processed = root / "data" / "processed"
    rows, _ = load_rows(processed)
    data = GoldData({r["id"]: r for r in rows}, processed=processed)
    for path in sorted((processed / "courses").rglob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        data.courses.setdefault(rec["code"], []).append(rec)
    events = json.loads((root / CALENDAR).read_text(encoding="utf-8"))
    data.events = {e["id"]: e for e in events}
    return data


def gold_problem(src: dict, data: GoldData) -> str | None:
    """None if the gold source resolves, else what is wrong."""
    sid, source, heading = src.get("id", ""), src.get("source", ""), src.get("heading", "")
    if sid == "TODO":
        return "unresolved (TODO)"
    if SECTION_ID.match(sid):
        row = data.sections.get(sid)
        if row is None:
            return f"{sid} is not a section in the index (embed true)"
        if row["source"] != source:
            return f"{sid}: source is {row['source']!r}, the file says {source!r}"
        if plain(row["heading_path"]) != heading:
            return f"{sid}: heading path is {row['heading_path']!r}, the file says {heading!r}"
        return None
    if sid.startswith("catalog:"):
        code = sid.removeprefix("catalog:")
        records = data.courses.get(code)
        if not records:
            return f"no course record with code {code!r}"
        if source != "catalog_course":
            return f"{sid}: source should be catalog_course"
        return None
    if source == CALENDAR:
        event = data.events.get(sid)
        if event is None:
            return f"no calendar event with id {sid!r}"
        if event.get("verified") is not True:
            return f"calendar event {sid} is not verified"
        if not heading.startswith(f"{event['term']}:"):
            return f"calendar event {sid} is {event['term']}, the heading says {heading!r}"
        return None
    return f"{sid!r} is not a section id, catalog code or calendar event id"


def question_problems(row: dict, data: GoldData) -> list[str]:
    problems = row_problems(row)
    sources = row.get("gold_sources")
    if isinstance(sources, list):
        if not sources and row.get("type") in NEEDS_SOURCES:
            problems.append(f"no gold sources for a {row['type']} question")
        for s in sources:
            if isinstance(s, dict):
                found = gold_problem(s, data)
                if found:
                    problems.append(found)
    return problems


def check_all(rows: list[dict], data: GoldData) -> dict[str, list[str]]:
    """Problems per question id (an empty list means ok)."""
    dupes = duplicate_ids(rows)
    out: dict[str, list[str]] = {}
    for i, row in enumerate(rows, 1):
        key = str(row.get("id", f"row {i}"))
        problems = question_problems(row, data)
        if row.get("id") in dupes:
            problems.append("id is not unique")
        out.setdefault(key, []).extend(problems)
    return out


def course_codes_in(text: str | None) -> list[str]:
    """Course codes named in prerequisite text, in order, without repeats."""
    found: list[str] = []
    for m in COURSE_CODE.finditer(text or ""):
        code = f"{m[1]} {m[2]}"
        if code not in found:
            found.append(code)
    return found


def prerequisite_chain(code: str, data: GoldData) -> dict:
    """The prerequisite text of a course, the courses it names, and for each of those its own
    prerequisite text and the courses that names (one level further). A suggestion for
    gold_sources; nothing is written to the file."""

    def record(c: str) -> dict | None:
        found = data.courses.get(c)
        return found[0] if found else None

    first = record(code)
    level1 = []
    for c in course_codes_in(first["prerequisite_text"] if first else None):
        rec = record(c)
        text = rec["prerequisite_text"] if rec else None
        level1.append({"code": c, "in_catalog": rec is not None, "prerequisite_text": text,
                       "names": course_codes_in(text)})  # fmt: skip
    return {"code": code, "prerequisite_text": first["prerequisite_text"] if first else None,
            "named": level1}  # fmt: skip


def main() -> int:
    rows = load_questions()
    data = load_gold_data()
    results = check_all(rows, data)
    for qid, problems in results.items():
        print(f"{qid}: " + ("ok" if not problems else "; ".join(problems)))
    bad = sum(bool(p) for p in results.values())
    print(f"{len(rows)} questions, {bad} with problems")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
