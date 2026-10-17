"""Load and check eval/questions.jsonl (CLAUDE.md, "Evaluation").

Run: uv run python -m cta.eval.questions
Row checks: required fields, type, split, unique ids, department. The separate locked casual set
(eval/questions_casual_v2.jsonl, split "heldout") is checked with `--heldout`: same rules, but
a gold answer still `TODO` is allowed. Gold-source checks: a section id
must exist in the section index data (embed true) with the same source and heading path, a
"catalog:<CODE>" must be a course record, a calendar entry must be a verified event. Question text,
splits and gold answers are never changed by this module. Not part of CI yet.
"""

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from cta.index.section_index import load_rows
from cta.settings import ROOT
from cta.validate.findings import Finding

QUESTIONS = ROOT / "eval" / "questions.jsonl"
HELDOUT_QUESTIONS = ROOT / "eval" / "questions_casual_v2.jsonl"  # version 2, one locked set
CALENDAR = "data/calendar/calendar_events.json"
FIELDS = ("id", "question", "gold_answer", "gold_sources", "type", "department", "split", "note")
# tags: a list of non-empty strings, e.g. "chain". calendar_acceptable_extra: calendar row ids that
# may appear in an answer to a calendar-only question without penalty (same event, different
# wording; scoring v2 in cta.eval.run_answers). They must not also be gold sources.
OPTIONAL_FIELDS = ("tags", "calendar_acceptable_extra")
TYPES = ("lookup", "multi_chunk", "time_sensitive", "ambiguous", "unanswerable")
SPLITS = ("dev", "test")
HELDOUT = "heldout"  # only in HELDOUT_QUESTIONS; never mixed into the dev/test file
DEPARTMENTS = ("CST-NYT", "MATH-NYT", "EET-NYT", "DENT-NYT")
PLACEHOLDERS = ("TODO", "FILL_FROM_CALENDAR")  # a gold answer still to be written
ABSTAIN_IDS = ("q25", "q26", "q27", "q28", "q29")  # the owner exempted these from the answer check
NEEDS_SOURCES = ("lookup", "multi_chunk", "time_sensitive")  # the others may have none
SECTION_ID = re.compile(r"^(page|pdf|dept)/.+#\d+$")
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


def select_questions(
    rows: list[dict], split: str, ids: list[str] | None = None, tag: str | None = None
) -> list[dict]:
    """The questions of a split, optionally only the given ids and/or those carrying a tag.
    An unknown id is an error (a typo must not silently shrink a run)."""
    chosen = [q for q in rows if q["split"] == split]
    if ids:
        unknown = sorted(set(ids) - {q["id"] for q in chosen})
        if unknown:
            raise ValueError(f"not in the {split} split: {', '.join(unknown)}")
        chosen = [q for q in chosen if q["id"] in ids]
    if tag:
        chosen = [q for q in chosen if tag in q.get("tags", [])]
    return chosen


def question_ids_record(questions: list[dict]) -> dict:
    """What a run config stores about its question set: the sorted ids and a short hash of them."""
    ids = sorted(q["id"] for q in questions)
    digest = hashlib.sha256("\n".join(ids).encode()).hexdigest()[:12]
    return {"question_ids": ids, "question_ids_hash": digest}


def questions_path(split: str) -> Path:
    """The file that holds a split: the held-out split has its own file."""
    return HELDOUT_QUESTIONS if split == HELDOUT else QUESTIONS


def row_problems(row: dict, splits: tuple[str, ...] = SPLITS) -> list[str]:
    """Problems with the row itself (not its gold sources)."""
    problems = [f"missing field {f}" for f in FIELDS if f not in row]
    problems += [f"unknown field {f}" for f in row if f not in FIELDS + OPTIONAL_FIELDS]
    tags = row.get("tags")
    if "tags" in row and (
        not isinstance(tags, list) or not all(isinstance(t, str) and t.strip() for t in tags)
    ):
        problems.append("tags is not a list of non-empty strings")
    extra = row.get("calendar_acceptable_extra")
    if "calendar_acceptable_extra" in row:
        if not isinstance(extra, list) or not all(isinstance(x, str) and x.strip() for x in extra):
            problems.append("calendar_acceptable_extra is not a list of non-empty strings")
        else:
            gold_ids = {s.get("id") for s in row.get("gold_sources", []) if isinstance(s, dict)}
            both = sorted(set(extra) & gold_ids)
            if both:
                problems.append(f"calendar_acceptable_extra also gold: {', '.join(both)}")
    if row.get("type") not in TYPES:
        problems.append(f"type {row.get('type')!r} is not one of {'|'.join(TYPES)}")
    if row.get("split") not in splits:
        problems.append(f"split {row.get('split')!r} is not {' or '.join(splits)}")
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
        if row["heading_path"] != heading:
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


def question_problems(row: dict, data: GoldData, splits: tuple[str, ...] = SPLITS) -> list[str]:
    problems = row_problems(row, splits)
    sources = row.get("gold_sources")
    if isinstance(sources, list):
        if not sources and row.get("type") in NEEDS_SOURCES:
            problems.append(f"no gold sources for a {row['type']} question")
        for s in sources:
            if isinstance(s, dict):
                found = gold_problem(s, data)
                if found:
                    problems.append(found)
    extras = row.get("calendar_acceptable_extra")
    if isinstance(extras, list):
        gold_ids = [s.get("id", "") for s in sources or [] if isinstance(s, dict)]
        if not gold_ids or not all(i in data.events for i in gold_ids):
            problems.append("calendar_acceptable_extra needs a calendar-only question")
        for event_id in extras:
            event = data.events.get(event_id)
            if event is None or event.get("verified") is not True:
                problems.append(
                    f"calendar_acceptable_extra {event_id!r} is not a verified calendar event"
                )
    return problems


def answer_problems(row: dict) -> list[str]:
    """A question outside the exempt abstain questions must have a written gold answer."""
    if row.get("id") not in ABSTAIN_IDS and row.get("gold_answer") in PLACEHOLDERS:
        return [f"gold_answer is still {row['gold_answer']}"]
    return []


def check_all(
    rows: list[dict], data: GoldData, splits: tuple[str, ...] = SPLITS, require_answers: bool = True
) -> dict[str, list[str]]:
    """Problems per question id (an empty list means ok). `require_answers` False lets a gold
    answer stay TODO (the held-out set, until the owner writes them)."""
    dupes = duplicate_ids(rows)
    out: dict[str, list[str]] = {}
    for i, row in enumerate(rows, 1):
        key = str(row.get("id", f"row {i}"))
        problems = [*question_problems(row, data, splits)]
        if require_answers:
            problems += answer_problems(row)
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


MODE = re.compile(
    r"(?P<pre_or_co>pre[\s/-]*(?:or\s+)?co-?requisites?)|(?P<co>co-?requisites?)"
    r"|(?P<pre>\bpre(?:requisites?)?\b)",
    re.I,
)
CLAUSE = re.compile(r"\s*[&;.]\s*")
PHRASE = re.compile(r"\s+(?:or(?!\s+higher)|and)\s+", re.I)  # "or higher" is not a list "or"
FINE = re.compile(r"\s*,\s*")
EXCLUSION = re.compile(r"\b(?:must not|may not|cannot|not have passed)\b", re.I)
EQUIVALENT = re.compile(r"\bequivalent\b", re.I)
PLACEMENT = re.compile(
    r"\bplacement\b|proficien|regents|\bscore\b|\bGPA\b|high school|permission|approval"
    r"|students only|\bdepartment\b",
    re.I,
)
KIND_OF = {"pre": "prerequisite", "co": "corequisite", "pre_or_co": "pre- or corequisite"}


def analyze_prerequisite(text: str | None) -> list[dict]:
    """The parts of prerequisite text, in order. {kind, code} for a named course: prerequisite,
    corequisite, pre- or corequisite, exclusion ("must not have passed") or equivalence. {kind:
    "placement", text} for placement, proficiency or permission wording (the walk stops there)."""
    text = text or ""
    marks = list(MODE.finditer(text))
    spans = [(marks[i].start(), marks[i + 1].start() if i + 1 < len(marks) else len(text),
              marks[i].lastgroup) for i in range(len(marks))]  # fmt: skip
    if not marks or marks[0].start() > 0:
        spans.insert(0, (0, marks[0].start() if marks else len(text), "pre"))
    items: list[dict] = []
    for start, end, mode in spans:
        for clause in CLAUSE.split(text[start:end]):
            clause = MODE.sub("", clause, count=1).strip(" :-()")
            if clause and not course_codes_in(clause):
                if PLACEMENT.search(clause):  # wording only, no course: one stop, kept whole
                    items.append({"kind": "placement", "text": clause})
                continue
            for phrase in PHRASE.split(clause):
                for piece in FINE.split(phrase):
                    codes = course_codes_in(piece)
                    if PLACEMENT.search(piece) and not EQUIVALENT.search(piece):
                        items.append({"kind": "placement", "text": piece.strip(" :-()")})
                    elif EXCLUSION.search(piece):
                        items += [{"kind": "exclusion", "code": c} for c in codes]
                    elif EQUIVALENT.search(piece):
                        items += [{"kind": "equivalence", "code": c} for c in codes]
                    else:
                        items += [{"kind": KIND_OF[mode], "code": c} for c in codes]
    return items


def prerequisite_tree(code: str, data: GoldData, seen: set[str] | None = None) -> dict:
    """The whole prerequisite chain of a course as a tree. Only prerequisites are followed.
    Corequisites and exclusions are listed, not followed; placement wording stops the walk; a
    course with no record (for example outside the four departments) is marked. A course already
    shown higher up or earlier is not expanded again."""
    seen = seen if seen is not None else set()
    seen.add(code)
    found = data.courses.get(code)
    text = found[0]["prerequisite_text"] if found else None
    title = found[0]["title"].strip() if found else None
    node = {"code": code, "record": bool(found), "title": title, "text": text, "items": []}
    for item in analyze_prerequisite(text):
        if item["kind"] == "prerequisite":
            if item["code"] in seen:
                node["items"].append({**item, "node": None, "expanded_elsewhere": True})
            else:
                node["items"].append({**item, "node": prerequisite_tree(item["code"], data, seen)})
        else:
            node["items"].append(item)
    return node


def tree_courses(node: dict) -> list[str]:
    """Codes of the courses in the tree that have a record, in the order they are first shown."""
    out = [node["code"]] if node["record"] else []
    for item in node["items"]:
        if item.get("node"):
            out += [c for c in tree_courses(item["node"]) if c not in out]
    return out


def tree_without_records(node: dict) -> list[str]:
    out = [] if node["record"] else [node["code"]]
    for item in node["items"]:
        if item.get("node"):
            out += [c for c in tree_without_records(item["node"]) if c not in out]
    return out


def render_tree(node: dict, indent: int = 0, label: str = "") -> list[str]:
    pad = "  " * indent
    if not node["record"]:
        return [f"{pad}- {label}{node['code']}: **no record**"]
    shown = f"{pad}- {label}{node['code']} ({node['title']})"
    lines = [f"{shown}: {node['text']}" if node["text"] else f"{shown}: no prerequisite text"]
    for item in node["items"]:
        kind = item["kind"]
        if kind == "placement":
            lines.append(f"{pad}  - placement or proficiency text, walk stops: {item['text']}")
        elif kind == "prerequisite" and item.get("node"):
            lines += render_tree(item["node"], indent + 1, "prerequisite ")
        elif kind == "prerequisite":
            lines.append(f"{pad}  - prerequisite {item['code']}: shown elsewhere in this tree")
        elif kind == "exclusion":
            lines.append(f"{pad}  - exclusion, not a prerequisite: {item['code']}")
        elif kind == "equivalence":
            lines.append(f"{pad}  - equivalence note, not a prerequisite: {item['code']}")
        else:
            lines.append(f"{pad}  - {kind}, not followed: {item['code']}")
    return lines


def eval_findings(rows: list[dict], data: GoldData) -> list[Finding]:
    """The question check as findings (used by cta.validate)."""
    return [
        Finding("eval_question", "fail", problem, qid)
        for qid, problems in check_all(rows, data).items()
        for problem in problems
    ]


def main(argv: list[str] | None = None) -> int:
    heldout = "--heldout" in (sys.argv[1:] if argv is None else argv)
    rows = load_questions(HELDOUT_QUESTIONS if heldout else QUESTIONS)
    data = load_gold_data()
    results = (
        check_all(rows, data, (HELDOUT,), require_answers=False)
        if heldout
        else check_all(rows, data)
    )
    for qid, problems in results.items():
        print(f"{qid}: " + ("ok" if not problems else "; ".join(problems)))
    bad = sum(bool(p) for p in results.values())
    print(f"{len(rows)} questions, {bad} with problems")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
