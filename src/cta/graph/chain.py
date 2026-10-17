"""The prerequisite-chain walk, the asked-course extraction and the LangChain tool (step 4b).

Plain, deterministic code; no model decides which courses are in a chain. The rules are those of
docs/chain-candidates.md and docs/step4b-plan.md:
- course codes come from a record's resolved prerequisite text (a bare number after a code takes its
  prefix); a code after "MUST NOT", "NOT HAVE" or "NOT" in the same clause is an exclusion (listed,
  not followed); breadth-first with a visited set; depth at most 4; at most 15 courses with records;
- non-course conditions are kept as text; shorthand or truncated text is UNPARSED (verbatim, nothing
  expanded); a code with no record is shown as "no record" and not expanded;
- texts are verbatim: the walk never decides AND/OR or which alternative applies.
"""

import json
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

from langchain_core.tools import tool

from cta.index.chunks import course_chunk
from cta.settings import ROOT

COURSES_DIR = ROOT / "data" / "processed" / "courses"
PROMPTS = Path(__file__).resolve().parent / "prompts"
MAX_DEPTH = 4
MAX_COURSES = 15  # courses with a catalog record; no-record codes are listed but not counted
MAX_ASKED = 3  # a question may name up to three courses; more falls through to retrieval
SCOPE = "the four departments (CST, Math, EET, Dental Hygiene)"

CODE = re.compile(r"\b([A-Za-z]{2,5}) ?(\d{3,4})([A-Za-z]{0,2})\b(?!-?\s*level)", re.I)
BARE = re.compile(r"(?<![\w-])(\d{4})(?![\w-])(?!\s*-?\s*level)", re.I)
NEGATION = re.compile(r"\b(MUST NOT|NOT HAVE|NOT)\b", re.I)
CLAUSE = re.compile(r"[.;\n]")
CONDITION = re.compile(
    r"placement|proficiency|gpa|regents|approval|permission|eligib|majors?\b|degree", re.I
)
COREQ = re.compile(r"co-?requisite|\bCO:|\bP/C\b|pre/co|pre- ?or ?co|\bCOREQ", re.I)
OR_BRANCH = re.compile(r"\bor\b\s+(?:\(|[A-Za-z]{2,5} ?\d|\d{4}|meet)", re.I)
SHORTHAND = re.compile(r"\bPRE_\w*|\bP_\w*_|[A-Z]{2,5}\d{3,4}_[A-Z]")
# The whole token around a SHORTHAND match ("PRE_CST3500_CST3600"), for explain_shorthand below.
SHORTHAND_TOKEN = re.compile(rf"\b\w*?(?:{SHORTHAND.pattern})\w*")
SHORTHAND_REPLACEMENT = "a prerequisite code the catalog does not spell out"


def explain_shorthand(text: str) -> str:
    """Model-written answer text: replace a catalog shorthand token (PRE_CST3500_CST3600) with a
    plain phrase. Never an expansion: the catalog's own rule lookup returns the shorthand and
    nothing else, so any reading of it would be a guess. Applied only to text a model wrote
    (cta.answer.answer and the model-written chain answer). The chain renderer (`chain_render`)
    keeps its verbatim "Catalog says" text on purpose: it quotes the catalog and says the courses
    "cannot be read from this text", which is the flag the data rules ask for, and it never
    passes through this function."""
    return SHORTHAND_TOKEN.sub(SHORTHAND_REPLACEMENT, text)


TRUNCATED = re.compile(r"[A-Za-z]{2,5}\d{1,2}\s*$")
# words that sit in front of a number without being a department ("(2405 or 2415)", "Fall 2026")
NOT_PREFIXES = {
    "OR", "AND", "OF", "TO", "IN", "FOR", "WITH", "BY", "ON", "AT", "IS", "AS", "TWO", "ONE",
    "FALL", "WINTER", "SPRING", "SUMMER", "YEAR", "TERM", "ROOM", "PAGE", "CLASS", "SEC",
}  # fmt: skip


@dataclass
class Parsed:
    codes: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    inferred: list[str] = field(default_factory=list)
    unparsed: str | None = None
    or_branch: bool = False
    coreq: bool = False


@dataclass
class Node:
    code: str
    level: int
    record: dict | None
    parsed: Parsed
    via: str | None


@dataclass
class Chain:
    root: str
    nodes: list[Node]
    unexpanded: list[dict] = field(default_factory=list)  # level-limit nodes that name codes
    dropped: list[dict] = field(default_factory=list)  # codes named but not added (the course cap)
    asked: list[str] = field(default_factory=list)  # every asked course, in the order asked
    owner: dict[str, str] = field(default_factory=dict)  # code -> the asked course that shows it
    shared: dict[str, list[str]] = field(default_factory=dict)  # asked -> codes shown above it

    @property
    def truncated(self) -> bool:
        return bool(self.unexpanded or self.dropped)

    @property
    def course_count(self) -> int:
        return sum(n.record is not None for n in self.nodes)


def normalise_code(text: str) -> str:
    m = CODE.fullmatch(text.strip())
    return f"{m[1].upper()} {m[2]}{m[3].upper()}" if m else text.strip().upper()


def find_codes(clause: str) -> list[tuple[int, str, bool]]:
    """(position, code, prefix inferred) for every code in the clause, bare numbers included."""
    matches = [m for m in CODE.finditer(clause) if m.group(1).upper() not in NOT_PREFIXES]
    found = [(m.start(), f"{m[1].upper()} {m[2]}{m[3].upper()}", False) for m in matches]
    taken = [(m.start(), m.end()) for m in matches]
    for m in BARE.finditer(clause):
        if any(a <= m.start() < b for a, b in taken):
            continue
        before = [f for f in found if f[0] < m.start()]
        if before:
            found.append((m.start(), f"{before[-1][1].split(' ')[0]} {m.group(1)}", True))
    return sorted(found)


def parse_text(text: str | None, style: str = "text", own: str | None = None) -> Parsed:
    """Course codes, exclusions, conditions and flags of one prerequisite text."""
    p, text = Parsed(), text or ""
    if not text.strip():
        return p
    if style == "shorthand" or SHORTHAND.search(text):
        p.unparsed = "shorthand text"
        return p
    if TRUNCATED.search(text.strip()):
        p.unparsed = "truncated text"
        return p
    p.coreq, p.or_branch = bool(COREQ.search(text)), bool(OR_BRANCH.search(text))
    for clause in (c for c in CLAUSE.split(text) if c.strip()):
        negation = NEGATION.search(clause)
        if CONDITION.search(clause):
            p.conditions.append(clause.strip())
        for pos, code, inferred in find_codes(clause):
            if code == own:
                continue
            target = p.exclusions if negation and pos >= negation.end() else p.codes
            if code not in target:
                target.append(code)
            if inferred and code not in p.inferred:
                p.inferred.append(code)
    return p


def walk(
    root: str, records: dict[str, dict], max_depth=MAX_DEPTH, max_courses=MAX_COURSES
) -> Chain:
    """The chain of one course: `walk_many` with a single asked course."""
    return walk_many([root], records, max_depth, max_courses)


def walk_many(
    roots: list[str], records: dict[str, dict], max_depth=MAX_DEPTH, max_courses=MAX_COURSES
) -> Chain:
    """The chain of each asked course, one after the other, breadth-first, with one visited set and
    one cap. A course reached again is not added again: it stays in the section of the first asked
    course that reached it (`owner`); later asked courses list it in `shared`. An asked course that
    an earlier section already shows is not walked again. The cap leaves room for the asked courses
    still to come. A course at the depth limit is shown but not expanded; both limits are recorded
    exactly."""
    nodes: dict[str, Node] = {}
    chain = Chain(roots[0], [], asked=list(roots), shared={r: [] for r in roots})
    queue: deque[str] = deque()

    def add(code: str, level: int, via: str | None, owner: str) -> None:
        record = records.get(code)
        style = record.get("prereq_style", "text") if record else "text"
        parsed = parse_text(record["prerequisite_text"], style, code) if record else Parsed()
        nodes[code] = Node(code, level, record, parsed, via)
        chain.owner[code] = owner
        if record:
            if level < max_depth:
                queue.append(code)
            elif parsed.codes:
                chain.unexpanded.append(
                    {
                        "code": code,
                        "level": level,
                        "names": list(parsed.codes),
                        "reason": "depth limit",
                    }
                )

    for i, root in enumerate(roots):
        if root in nodes:
            continue  # shown in an earlier section
        add(root, 0, None, root)
        while queue:
            node = nodes[queue.popleft()]
            for code in node.parsed.codes:
                if code in nodes:
                    if chain.owner[code] != root and code in records:
                        if code not in chain.shared[root]:
                            chain.shared[root].append(code)
                        cut = [u for u in chain.unexpanded if u["code"] == code]
                        if cut and node.level + 1 < max_depth:  # an earlier section stopped here,
                            chain.unexpanded.remove(cut[0])  # this one is nearer: go on from it
                            nodes[code].level = node.level + 1
                            queue.append(code)
                    continue
                waiting = [
                    r for r in roots[i + 1 :] if r in records and r not in nodes and r != code
                ]
                held = sum(n.record is not None for n in nodes.values()) + len(waiting)
                if code in records and held >= max_courses:
                    if not any(d["code"] == code for d in chain.dropped):
                        chain.dropped.append(
                            {"code": code, "named_by": node.code, "reason": "course cap"}
                        )
                    continue
                add(code, node.level + 1, node.code, root)
    chain.nodes = list(nodes.values())
    return chain


def chain_to_dict(chain: Chain) -> dict:
    """The JSON-able result the tool returns."""
    courses = []
    for n in chain.nodes:
        if n.record is None:
            continue
        p = n.parsed
        courses.append({
            "code": n.code, "level": n.level, "title": n.record["title"].strip(),
            "text": (n.record["prerequisite_text"] or "").strip(), "unparsed": p.unparsed,
            "codes": p.codes, "exclusions": p.exclusions, "conditions": p.conditions,
            "inferred_prefix": p.inferred, "corequisite_wording": p.coreq,
            "or_wording": p.or_branch,
            "named_by": n.via,
        })  # fmt: skip
    result = {
        "root": chain.root, "courses": courses, "course_count": chain.course_count,
        "no_record": [n.code for n in chain.nodes if n.record is None],
        "unexpanded": chain.unexpanded, "dropped": chain.dropped, "truncated": chain.truncated,
    }  # fmt: skip
    if len(chain.asked) > 1:  # several asked courses: one section each, in the order asked
        has_record = {c["code"] for c in courses}
        result["asked"] = chain.asked
        result["sections"] = [
            {
                "root": r, "found": r in has_record, "already_shown": chain.owner.get(r) != r,
                "courses": [c["code"] for c in courses if chain.owner[c["code"]] == r],
                "shared": chain.shared[r],
            }
            for r in chain.asked
        ]  # fmt: skip
    return result


# ---- records and the tool ----


@lru_cache(maxsize=2)
def _load(directory: str) -> dict[str, dict]:
    records = {}
    for path in sorted(Path(directory).glob("*/*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        records[record["code"]] = record
    return records


def load_records(directory: Path = COURSES_DIR) -> dict[str, dict]:
    """The processed course records of the four departments, by code."""
    return _load(str(directory))


@tool
def prerequisite_chain(course_code: str) -> dict:
    """Walk the catalog prerequisite text of one course and return its prerequisite chain.

    Input: one course code such as "CST 2412". Output: the chain breadth-first from that course
    (verbatim prerequisite texts, exclusions, non-course conditions, courses with no record, and a
    record of anything the depth or size limit left out), or {"found": false} if the four
    departments' catalog data has no record of the code. Never decides AND/OR."""
    records = load_records()
    code = normalise_code(course_code)
    if code not in records:
        return {"found": False, "code": code}
    return {"found": True, **chain_to_dict(walk(code, records))}


def combined_chain(course_codes: list[str]) -> dict:
    """The tool's answer for 2 or 3 asked courses: one combined walk (`walk_many`). {"found": false}
    only when none of the codes has a record; a code without one keeps its own section."""
    records = load_records()
    codes = list(dict.fromkeys(normalise_code(c) for c in course_codes))
    if not any(c in records for c in codes):
        return {"found": False, "code": ", ".join(codes)}
    return {"found": True, **chain_to_dict(walk_many(codes, records))}


# ---- extraction ----


@dataclass
class Extraction:
    status: str  # code | codes (2 or 3) | title | many (more than 3) | ambiguous | none
    code: str | None = None
    detail: list[str] = field(default_factory=list)


def question_codes(question: str) -> list[str]:
    seen: list[str] = []
    for m in CODE.finditer(question):
        if m.group(1).upper() in NOT_PREFIXES:
            continue
        code = f"{m[1].upper()} {m[2]}{m[3].upper()}"
        if code not in seen:
            seen.append(code)
    return seen


def title_matches(question: str, records: dict[str, dict]) -> dict[str, list[str]]:
    """title (lower case) -> codes, for every course title that occurs as a whole phrase in the
    question; a title inside a longer matched title is dropped."""
    by_title: dict[str, list[str]] = {}
    for code, r in records.items():
        by_title.setdefault(r["title"].strip().lower(), []).append(code)
    lowered = question.lower()
    hits = {
        t: c
        for t, c in by_title.items()
        if t and re.search(rf"(?<!\w){re.escape(t)}(?!\w)", lowered)
    }
    return {t: c for t, c in hits.items() if not any(t != u and t in u for u in hits)}


def extract_course(question: str, records: dict[str, dict]) -> Extraction:
    """One distinct course code, or two or three (the first is `code`, all are `detail`), or no code
    and exactly one unique exact course title. Titles are never mixed with codes."""
    codes = question_codes(question)
    if len(codes) == 1:
        return Extraction("code", codes[0])
    if 1 < len(codes) <= MAX_ASKED:
        return Extraction("codes", codes[0], codes)
    if len(codes) > MAX_ASKED:
        return Extraction("many", None, codes)
    hits = title_matches(question, records)
    if len(hits) == 1:
        ((title, found),) = hits.items()
        if len(found) == 1:
            return Extraction("title", found[0], [title])
        return Extraction("ambiguous", None, found)
    return Extraction("ambiguous" if hits else "none", None, [c for v in hits.values() for c in v])


# ---- the answer step ----


def instructions() -> str:
    return (PROMPTS / "chain_answer.txt").read_text(encoding="utf-8")


def sources_of(result: dict, records: dict[str, dict]) -> list[dict]:
    """The numbered sources: one course chunk (id catalog:<CODE>) per chain course with a record."""
    return [course_chunk(records[c["code"]]) for c in result["courses"]]


def describe(result: dict) -> str:
    """The chain description given to the answerer: order, levels, flags and the truncation note."""
    lines = ["Chain order (level, course, source number):"]
    for number, c in enumerate(result["courses"], 1):
        flags = []
        if c["unparsed"]:
            flags.append(f"UNPARSED ({c['unparsed']})")
        if c["exclusions"]:
            flags.append("exclusion (must not have taken): " + ", ".join(c["exclusions"]))
        if c["conditions"]:
            flags.append("conditions as written: " + " | ".join(c["conditions"]))
        lines.append(
            f"- Level {c['level']}: {c['code']} [{number}]"
            + (" -- " + "; ".join(flags) if flags else "")
        )
    if result["no_record"]:
        lines.append("No record in the catalog data: " + ", ".join(result["no_record"]))
    if result["truncated"]:
        parts = [
            f"{u['code']} (level {u['level']}) names {', '.join(u['names'])}, "
            f"not followed ({u['reason']})"
            for u in result["unexpanded"]
        ]
        parts += [
            f"{d['code']} named by {d['named_by']}, not added ({d['reason']})"
            for d in result["dropped"]
        ]
        lines.append("Truncation note: the chain was cut. " + "; ".join(parts) + ".")
    return "\n".join(lines)


def build_messages(question: str, today: date, result: dict, sources: list[dict]) -> list[dict]:
    from cta.answer import format_source

    shown = "\n\n---\n\n".join(format_source(n, s) for n, s in enumerate(sources, 1))
    user = (
        f"Sources:\n\n{shown}\n\n{describe(result)}\n\n"
        f"Today's date: {today.isoformat()}\nQuestion: {question}"
    )
    return [{"role": "system", "content": instructions()}, {"role": "user", "content": user}]


def no_record_text(code: str) -> str:
    return f"ABSTAIN: No record exists in the catalog data for {code} in {SCOPE}."


# ---- a course outside the four departments (tester round 1, item D) ----

OUTSIDE_TEXT = (
    "ABSTAIN: I only have catalog records for Computer Systems Technology, Mathematics, "
    "Electrical and Telecommunications Engineering Technology, and Dental Hygiene, so I can't "
    "tell you about {code}. The City Tech catalog is at {url}."
)


def known_prefixes(records: dict[str, dict]) -> set[str]:
    """The subject prefixes of the catalog records we hold, read from the data (never typed)."""
    return {code.split()[0] for code in records}


def catalog_url() -> str:
    """The City Tech catalog address, from config/sources.yaml (`catalog_api.origin`)."""
    import yaml

    config = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))
    return config["catalog_api"]["origin"]


def outside_departments(code: str, records: dict[str, dict]) -> bool:
    """True when the prefix of the code the student typed appears in no record we hold."""
    return code.split()[0] not in known_prefixes(records)


def outside_text(code: str) -> str:
    return OUTSIDE_TEXT.format(code=code, url=catalog_url())


def outside_sentence(code: str) -> str:
    """The same text without the "ABSTAIN:" marker, for a section of a longer answer."""
    return outside_text(code).removeprefix("ABSTAIN: ")
