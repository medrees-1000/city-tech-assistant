"""Write docs/chain-candidates.md: about 12 prerequisite-chain question candidates for the owner.

    uv run python scripts/make_chain_candidates.py

Rules (docs/phase3-plan.md, step 4b-0):
- The roots are chosen by category (SPECS below) from the catalog data, never from any system output.
  Nothing here is added to eval/questions.jsonl.
- The DRAFT chain of a root is computed with one simple rule (documented in EXPANSION below). The gold
  answer is built mechanically from the course records (code, title, prerequisite text verbatim, in a
  fixed format), never from outside knowledge. The simple rule can be wrong on odd wording; the
  owner's check against the catalog is what makes a gold answer trustworthy.
- Output is deterministic: the same records give the same file. Data is never fixed here: odd records
  are listed at the end.
"""

import json
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COURSES = ROOT / "data" / "processed" / "courses"
RULES = ROOT / "data" / "processed" / "rules_cache.json"
CONTACTS = ROOT / "data" / "processed" / "contacts"
QUESTIONS = ROOT / "eval" / "questions.jsonl"
OUT = ROOT / "docs" / "chain-candidates.md"
MAX_DEPTH = 4
NO_RECORD = "no record in the catalog data of the four departments"

EXPANSION = """\
1. Take every explicit course code (for example `CST 1204`, `MAT1275CO`) from a record's resolved prerequisite text. A bare 3 or 4 digit number right after a code in the same text (`CST 1100 & 1101`, `2405 or 2415`) takes the prefix of the nearest code to its left; those are marked "(prefix inferred)". Numbers followed by `-LEVEL` or `XX` are not codes.
2. A code that appears after "MUST NOT", "NOT HAVE" or "NOT" in the same clause (clauses end at a period, semicolon or line break) is an **exclusion**: it is listed, never expanded, and is not a gold source.
   A code equal to the course's own code (for example "Meet the Math Placement for MAT 1375" inside MAT 1375) is skipped.
3. Breadth-first from the root with a visited set (a course already reached is not expanded again, so cycles end), depth at most 4 (the root is level 0; a course at level 4 is shown but not expanded).
4. Every course's prerequisite text is kept verbatim. Corequisite wording is not separated: a code in "Corequisite: X" is expanded like any other code (flagged "corequisite wording") because the simple rule does not read the meaning of the wording.
5. Clauses about placement, proficiency, GPA, approval, eligibility or a major or degree are listed as **conditions (text)**, not as courses.
6. A record whose text is shorthand (`PRE_CST1100_CST1101`), truncated (a code cut off, `MAT13`) or marked shorthand in the data is **UNPARSED**: its text is shown verbatim, nothing is expanded from it, and no meaning is guessed.
7. A code with no record in the four departments' data (for example `ENG 1101`, `PHYS 1433`) is shown as "no record" and not expanded.
8. gold_sources = `catalog:<CODE>` of every course in the chain that has a record (the root included, exclusions not).
"""

CODE = re.compile(r"\b([A-Za-z]{2,5}) ?(\d{3,4})([A-Za-z]{0,2})\b(?!-?\s*level)", re.I)
BARE = re.compile(r"(?<![\w-])(\d{4})(?![\w-])(?!\s*-?\s*level)", re.I)
NEGATION = re.compile(r"\b(MUST NOT|NOT HAVE|NOT)\b", re.I)
CLAUSE = re.compile(r"[.;\n]")
CONDITION = re.compile(
    r"placement|proficiency|gpa|regents|approval|permission|eligib|majors?\b|degree", re.I
)
COREQ = re.compile(r"co-?requisite|\bCO:|\bP/C\b|pre/co|pre- ?or ?co|\bPRE/CO\b|\bCOREQ", re.I)
OR_BRANCH = re.compile(r"\bor\b\s+(?:\(|[A-Za-z]{2,5} ?\d|\d{4}|meet)", re.I)
SHORTHAND = re.compile(r"\bPRE_\w*|\bP_\w*_|[A-Z]{2,5}\d{3,4}_[A-Z]")
TRUNCATED = re.compile(r"[A-Za-z]{2,5}\d{1,2}\s*$")


@dataclass
class Parsed:
    codes: list[str] = field(default_factory=list)  # to expand, in text order
    exclusions: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)  # clauses, verbatim
    inferred: list[str] = field(default_factory=list)  # codes whose prefix was inferred
    unparsed: str | None = None  # why nothing could be read, or None
    or_branch: bool = False
    coreq: bool = False


@dataclass
class Node:
    code: str
    level: int
    record: dict | None
    parsed: Parsed
    via: str | None  # the course whose text first named this one
    depth_limit: bool = False  # it has courses to expand but sits at the depth limit
    also_from: list[str] = field(default_factory=list)  # other courses that name it


def norm(prefix: str, number: str, suffix: str) -> str:
    return f"{prefix.upper()} {number}{suffix.upper()}"


NOT_PREFIXES = {"OR", "AND", "OF", "TO", "IN", "FOR", "WITH", "BY", "ON", "AT", "IS", "AS", "TWO", "ONE"}


def find_codes(clause: str) -> list[tuple[int, str, bool]]:
    """(position, code, prefix inferred) for every code in the clause, bare numbers included. A word
    such as "or" or "and" in front of a number is not a department prefix ("(2405 or 2415)")."""
    matches = [m for m in CODE.finditer(clause) if m.group(1).upper() not in NOT_PREFIXES]
    found = [(m.start(), norm(*m.groups()), False) for m in matches]
    taken = [(m.start(), m.end()) for m in matches]
    for m in BARE.finditer(clause):
        if any(a <= m.start() < b for a, b in taken):
            continue
        before = [f for f in found if f[0] < m.start()]
        if before:
            prefix = before[-1][1].split(" ")[0]
            found.append((m.start(), f"{prefix} {m.group(1)}", True))
    return sorted(found)


def parse_text(text: str | None, style: str = "text", own: str | None = None) -> Parsed:
    """Split a prerequisite text into course codes, exclusions, conditions and flags (EXPANSION).
    A code that is the course's own code ('Meet the Math Placement for MAT 1375' in MAT 1375) is skipped."""
    p = Parsed()
    text = text or ""
    if not text.strip():
        return p
    if style == "shorthand" or SHORTHAND.search(text):
        p.unparsed = "shorthand text"
        return p
    if TRUNCATED.search(text.strip()):
        p.unparsed = "truncated text"
        return p
    p.coreq = bool(COREQ.search(text))
    p.or_branch = bool(OR_BRANCH.search(text))
    for clause in (c for c in CLAUSE.split(text) if c.strip()):
        negation = NEGATION.search(clause)
        cut = negation.end() if negation else None
        if CONDITION.search(clause):
            p.conditions.append(clause.strip())
        for pos, code, inferred in find_codes(clause):
            if code == own:
                continue
            target = p.exclusions if cut is not None and pos >= cut else p.codes
            if code not in target:
                target.append(code)
            if inferred and code not in p.inferred:
                p.inferred.append(code)
    return p


def expand(root: str, records: dict[str, dict], max_depth: int = MAX_DEPTH) -> list[Node]:
    """The draft chain: nodes in breadth-first order, each course once (EXPANSION, rules 3 and 7)."""
    nodes: dict[str, Node] = {}
    queue: deque[str] = deque()

    def add(code: str, level: int, via: str | None) -> None:
        record = records.get(code)
        parsed = parse_text(record["prerequisite_text"], record.get("prereq_style", "text"), code) if record else Parsed()
        nodes[code] = Node(code, level, record, parsed, via, level >= max_depth and bool(parsed.codes))
        if record and level < max_depth:
            queue.append(code)

    add(root, 0, None)
    while queue:
        node = nodes[queue.popleft()]
        for code in node.parsed.codes:
            if code in nodes:
                if node.code not in nodes[code].also_from and node.code != nodes[code].via:
                    nodes[code].also_from.append(node.code)
            else:
                add(code, node.level + 1, node.code)
    return list(nodes.values())


def chain_depth(nodes: list[Node]) -> int:
    return max(n.level for n in nodes)


def gold_sources(nodes: list[Node]) -> list[str]:
    return [f"catalog:{n.code}" for n in nodes if n.record]


# ---- the gold text (fixed format) ----


def node_line(n: Node) -> str:
    """One line per course: level, code, title, the text verbatim, and what was read from it."""
    if n.record is None:
        return f"Level {n.level} - {n.code}: {NO_RECORD} (not expanded)."
    r = n.record
    text = (r["prerequisite_text"] or "").strip()
    head = f"Level {n.level} - {n.code} ({r['title'].strip()}): "
    if not text:
        return head + "no prerequisite is listed in the catalog."
    parts = [f"catalog text \"{' / '.join(text.splitlines())}\""]
    p = n.parsed
    if p.unparsed:
        parts.append(f"UNPARSED ({p.unparsed}); not expanded")
    if p.codes:
        parts.append("course codes named: " + ", ".join(p.codes))
    if p.exclusions:
        parts.append("exclusion, not a prerequisite: " + ", ".join(p.exclusions))
    if p.conditions:
        parts.append("conditions (not courses): " + " | ".join(p.conditions))
    if n.depth_limit:
        parts.append(f"the chain continues beyond level {MAX_DEPTH} (not expanded)")
    return head + "; ".join(parts) + "."


def chain_gold(nodes: list[Node]) -> str:
    root = nodes[0]
    head = f"Draft chain for {root.code} ({root.record['title'].strip()}), built from the catalog records:"
    return head + "\n" + "\n".join(node_line(n) for n in nodes)


def contact_line(dept: str, path: Path = CONTACTS) -> str:
    """The department's email and phone from its contact record, or a TODO."""
    try:
        record = json.loads((path / f"{dept}.json").read_text(encoding="utf-8"))
        return ", ".join([*record["emails"], *record["phones"]]) or "TODO"
    except (OSError, ValueError, KeyError):
        return "TODO"


def unparsed_gold(root: Node, contact: str) -> str:
    text = (root.record["prerequisite_text"] or "").strip()
    return (
        f"{root.code} ({root.record['title'].strip()}): the catalog text is \"{text}\". The prerequisites "
        f"cannot be determined from the catalog text; contact the department: {contact}."
    )


def control_gold(root: Node) -> str:
    r = root.record
    credits = r["credits"]
    return f"{root.code} ({r['title'].strip()}, {credits} credit{'s' if credits != 1 else ''}): {r['description'].strip()}"


# ---- the candidates (chosen by category) ----
# kind: chain | unparsed | abstain | control. Ids continue after the highest existing question id.
SPECS: list[dict] = [
    {"category": "linear chain, 3+ levels (CST)", "kind": "chain", "root": "CST 2412", "split": "dev", "type": "multi_chunk",
     "question": "What are all the courses I have to take before CST 2412, step by step?",
     "note": "Levels: CST 2412, CST 2402, then CST 1201, CST 1204 and MAT 1375, then their prerequisites. Shares CST 1201, CST 1100, CST 1101 and CST 1204 with the q40 chain and MAT 1275 with the math tail."},
    {"category": "linear chain, 3+ levels (EET)", "kind": "chain", "root": "EET 2150", "split": "dev", "type": "multi_chunk",
     "question": "What do I need to take before EET 2150?",
     "note": "A long EET chain with corequisite and OR wording and courses outside the four departments (PHYS, ENG); the depth limit may apply."},
    {"category": "OR-branch with math placement", "kind": "chain", "root": "MAT 1375", "split": "test", "type": "multi_chunk",
     "question": "What do I need to take before MAT 1375?",
     "note": "The text has 'OR Meet the Math Placement for MAT 1375': a placement alternative to the course. Shares MAT 1275 and MAT 1275CO with the q22, q39 and q41 tail (not MAT 1475 or MAT 1575)."},
    {"category": "no prerequisite listed", "kind": "chain", "root": "EET 3572", "split": "dev", "type": "lookup",
     "question": "What are the prerequisites for EET 3572?",
     "note": "The record has no rule id and no prerequisite text; the gold says none is listed (it does not claim there is none outside the catalog)."},
    {"category": "exclusion text", "kind": "chain", "root": "MAT 1372", "split": "test", "type": "multi_chunk",
     "question": "What do I need before MAT 1372, and is there anything I must not have taken?",
     "note": "'Must not have taken MAT 2572' is an exclusion, not a prerequisite: the draft lists it and does not expand it."},
    {"category": "cross-listed course (same description under two codes)", "kind": "chain", "root": "CST 2304", "split": "dev", "type": "lookup",
     "question": "What are the prerequisites for CST 2304?",
     "note": "CST 2304 and CST 1204 share a title and a description but have separate records and rules; the question names CST 2304, whose record lists no prerequisite. The answer must not borrow CST 1204's rule."},
    {"category": "truncated or shorthand prerequisite text", "kind": "unparsed", "root": "CST 3508", "split": "test", "type": "ambiguous",
     "question": "What do I need to take before CST 3508?",
     "note": "The text is shorthand and cut off ('...MAT13'). Gold = the verbatim text plus 'cannot be determined from the catalog text, contact the department' and the CST department contact. Type ambiguous (alternative: unanswerable)."},
    {"category": "unknown course code", "kind": "abstain", "root": "CST 4999", "split": "dev", "type": "unanswerable", "contact": "CST-NYT",
     "question": "What are the prerequisites for CST 4999?",
     "note": "No record with this code exists in the catalog data (Active courses of the four departments). Gold ABSTAIN with the CST department contact. Please confirm in the catalog that no such course exists."},
    {"category": "course outside the four departments", "kind": "abstain", "root": "ENG 1101", "split": "test", "type": "unanswerable", "contact": "registrar",
     "question": "What do I need to take before ENG 1101?",
     "note": "English is outside the four departments (out of scope): gold ABSTAIN with the Registrar contact. ENG 1101 is named inside several records' text but has no record of its own."},
    {"category": "course named by title only", "kind": "chain", "root": "CST 3504", "split": "dev", "type": "multi_chunk",
     "question": "What do I need to take before Database Design?",
     "note": "The title 'Database Design' belongs to one record only (CST 3504). Shares CST 1204, CST 1100 and CST 1101 with the q40 chain."},
    {"category": "corequisite cycle and non-course conditions", "kind": "chain", "root": "DEN 1100", "split": "test", "type": "multi_chunk",
     "question": "What do I need before DEN 1100?",
     "note": "DEN 1100 names DEN 1112 as a corequisite and DEN 1112 names DEN 1100: a cycle. The text also has non-course conditions (CUNY proficiency, department approval). The simple rule expands the corequisite like a prerequisite; the owner should decide what the gold should say about corequisites."},
    {"category": "boundary control, not a chain question", "kind": "control", "root": "MAT 2440", "split": "dev", "type": "lookup", "tags": [],
     "question": "What is MAT 2440 about, and how many credits is it?",
     "note": "A normal lookup about one course (description and credits); the router should not send it to the chain tool."},
]  # fmt: skip


def load_records(courses: Path = COURSES) -> dict[str, dict]:
    records = {}
    for path in sorted(courses.glob("*/*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        records[record["code"]] = record
    return records


def highest_question_number(path: Path = QUESTIONS) -> int:
    ids = [json.loads(line)["id"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return max(int(i[1:]) for i in ids)


def build(records: dict[str, dict], first_number: int, contacts: Path = CONTACTS) -> list[dict]:
    """The candidates with their draft chain, gold text and sources filled in."""
    out = []
    for n, spec in enumerate(SPECS):
        kind, root = spec["kind"], spec["root"]
        nodes = expand(root, records) if root in records else []
        if kind in ("control", "unparsed"):
            nodes = nodes[:1]  # one record only: a lookup, or text that cannot be expanded
        sources, gold = [], ""
        if kind == "chain":
            gold, sources = chain_gold(nodes), gold_sources(nodes)
        elif kind == "unparsed":
            dept = nodes[0].record["department"]
            gold, sources = unparsed_gold(nodes[0], contact_line(dept, contacts)), gold_sources(nodes)
        elif kind == "control":
            gold, sources = control_gold(nodes[0]), gold_sources(nodes)
        else:
            gold = "ABSTAIN"
        out.append({
            "id": f"q{first_number + n}", "spec": spec, "nodes": nodes, "gold": gold, "sources": sources,
            "tags": [] if kind == "control" else ["chain"], "split": spec["split"],
        })  # fmt: skip
    return out


# ---- the file ----


def cell(text: object) -> str:
    return str(text if text not in (None, "") else "-").replace("\n", " / ").replace("|", "\\|")


def existing_chain_sources(path: Path = QUESTIONS) -> dict[str, set[str]]:
    """question id -> course codes in the gold sources, for the chain-tagged questions."""
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        q = json.loads(line)
        if "chain" in q.get("tags", []):
            out[q["id"]] = {g["id"].removeprefix("catalog:") for g in q["gold_sources"] if g["id"].startswith("catalog:")}
    return out


def candidate_flags(c: dict, records: dict[str, dict], rules: dict) -> list[str]:
    flags = []
    for n in c["nodes"]:
        r = n.record
        if r and r["rule_id"] and not (rules.get(r["rule_id"]) or {}).get("text"):
            flags.append(f"{n.code}: rule id {r['rule_id']} did not resolve")
        if r and r["prerequisite_text"] and re.search(r"\b\d{6}\b", r["prerequisite_text"]):
            flags.append(f"{n.code}: an unresolved 6-digit rule id is in the text")
        if n.parsed.unparsed:
            flags.append(f"{n.code}: UNPARSED ({n.parsed.unparsed})")
        if n.parsed.inferred:
            flags.append(f"{n.code}: prefix inferred for {', '.join(n.parsed.inferred)}")
        if n.parsed.coreq:
            flags.append(f"{n.code}: corequisite wording (the simple rule expands it like a prerequisite)")
        if r and re.search(r"will not receive credit|is equivalent to", r["prerequisite_text"] or "", re.I):
            flags.append(f"{n.code}: 'equivalent' or 'no credit' wording: the codes in it are not prerequisites, but the simple rule expands them")
        if n.parsed.or_branch:
            flags.append(f"{n.code}: OR branch (any one of the alternatives; the draft lists all of them)")
        if n.depth_limit:
            flags.append(f"{n.code}: sits at the depth limit; the chain continues")
        if n.record is None and n.code != c["spec"]["root"]:
            flags.append(f"{n.code}: {NO_RECORD}")
    return flags


def render_candidate(c: dict, records: dict[str, dict], rules: dict, existing: dict[str, set[str]]) -> list[str]:
    s, nodes = c["spec"], c["nodes"]
    tags = c["tags"]
    out = [
        f"## {c['id']} — {s['category']}",
        "",
        f"- **Question:** {s['question']}",
        f"- **Type:** {s['type']}  |  **Tags:** {', '.join(tags) or '(none)'}  |  **Proposed split:** {s['split']}",
        f"- **Root:** {s['root']}  |  **Chain depth:** {chain_depth(nodes) if nodes else 'n/a'}  |  **Courses in the chain:** {len(nodes) or 'n/a'}",
        f"- **Gold sources:** {', '.join(f'`{x}`' for x in c['sources']) or '(none)'}",
        f"- **Note:** {s['note']}",
    ]
    shared = {q: sorted({n.code for n in nodes} & codes) for q, codes in existing.items()}
    shared = {q: v for q, v in shared.items() if v}
    if shared:
        out.append("- **Courses shared with existing chain questions:** " + "; ".join(f"{q}: {', '.join(v)}" for q, v in shared.items()))
    flags = candidate_flags(c, records, rules)
    if flags:
        out += ["- **FLAGS:**"] + [f"  - {f}" for f in flags]
    out += ["", f"**Draft gold answer (built from the records; DRAFT: owner must check against the catalog):**", ""]
    out += [f"> {line}" if line else ">" for line in c["gold"].splitlines()] + [""]
    if nodes:
        out += ["Records as stored:", "", "| level | code | title | prerequisite text | requirementGroup id | courseGroupId |", "|---|---|---|---|---|---|"]
        for n in nodes:
            r = n.record
            if r is None:
                out.append(f"| {n.level} | {n.code} | - | {NO_RECORD} | - | - |")
            else:
                out.append(f"| {n.level} | {n.code} | {cell(r['title'].strip())} | {cell(r['prerequisite_text'])} | {cell(r['rule_id'])} | {cell(r['course_group_id'])} |")
        out += ["", "Catalog page: the raw data has the courseGroupId (above) but no page slug, so no URL is given; search the catalog by course code.", ""]
    elif s["kind"] == "abstain":
        who = contact_line(s["contact"], CONTACTS)
        out += [
            f"No record for {s['root']} in the processed catalog data. Search the catalog by course code to confirm.",
            f"Contact the answer should name ({s['contact']}): {who}.",
            "",
        ]
    return out


def data_notes(records: dict[str, dict], rules: dict) -> list[str]:
    """Things noticed in the data (listed, never fixed)."""
    codes = set(records)
    shorthand = sorted(c for c, r in records.items() if r.get("prereq_style") == "shorthand")
    truncated = sorted(c for c, r in records.items() if r["prerequisite_text"] and TRUNCATED.search(r["prerequisite_text"].strip()))
    unresolved = sorted(c for c, r in records.items() if r["rule_id"] and not (rules.get(r["rule_id"]) or {}).get("text"))
    prefixes = {c.split(" ")[0] for c in codes}
    dangling: dict[str, list[str]] = {}
    for c, r in records.items():
        p = parse_text(r["prerequisite_text"], r.get("prereq_style", "text"))
        for code in p.codes + p.exclusions:
            if code.split(" ")[0] in prefixes and code not in codes:
                dangling.setdefault(code, []).append(c)
    by_description: dict[str, list[str]] = {}
    for c, r in records.items():
        by_description.setdefault(r["description"].strip(), []).append(c)
    same_description = [v for v in by_description.values() if len(v) > 1]
    credit_text = sorted(c for c, r in records.items() if re.search(r"will not receive credit|is equivalent to", r["prerequisite_text"] or "", re.I))
    return [
        f"- Records: {len(records)}. Shorthand prerequisite text (`PRE_...`, marked UNPARSED): {len(shorthand)} records, for example {', '.join(shorthand[:6])}.",
        f"- Truncated text (a code cut off at the end): {', '.join(truncated) or 'none'}.",
        f"- Records whose rule id did not resolve in the rule cache: {', '.join(unresolved) or 'none'}. A 6-digit rule id inside prerequisite text: none found.",
        "- Codes named in prerequisite text with an in-scope prefix but no record (possibly typos or retired courses): " + ("; ".join(f"{k} (in {', '.join(v)})" for k, v in sorted(dangling.items())) or "none") + ".",
        "- Same description under different codes (cross-listed or duplicate records, each with its own rule): " + "; ".join(", ".join(v) for v in same_description) + ".",
        f"- Wording the simple rule misreads, because the codes come BEFORE the negation or are 'equivalent' codes (they would be expanded as prerequisites): {', '.join(credit_text) or 'none'}.",
        "- Corequisite and prerequisite wording are mixed in one text in many records (`P/C:`, `Pre- or corequisite`, `CO:`); the draft does not separate them, which is why corequisite cycles (DEN 1100 and DEN 1112) appear.",
        "- Several records share one rule id and one text although their titles differ (for example the rule shared by MAT 2572 and MAT 2680, and by MAT 3050, MAT 3080, MAT 4030 and MEDU 3000).",
        "- A bare 4-digit number after a code (`CST 1100 & 1101`) is read as the same prefix; the draft marks every such case.",
    ]


def render(records: dict[str, dict], rules: dict, first_number: int, existing: dict[str, set[str]], contacts: Path = CONTACTS) -> str:
    items = build(records, first_number, contacts)
    dev = sum(c["split"] == "dev" for c in items)
    out = [
        "# Chain question candidates (for the owner to review)",
        "",
        f"Generated by `scripts/make_chain_candidates.py` from the processed catalog records. **{len(items)} candidates, ids q{first_number} to q{first_number + len(items) - 1}, proposed split {dev} dev / {len(items) - dev} test.** "
        "Nothing here is in `eval/questions.jsonl`. The roots were chosen by category from the data; no system output was used. The test split proposals are gold only: no test result was looked at.",
        "",
        "**How the gold is built, and why your check matters.** Each draft chain follows one simple rule (below). The gold answer is generated from the records in a fixed format (course code, title, the prerequisite text verbatim, what was read from it); no knowledge of the courses was used. "
        "A simple rule can misread odd wording, so **your check against the catalog is what makes a gold answer trustworthy**: please compare each chain course with its catalog entry (search by course code; the courseGroupId in each table helps).",
        "",
        "### The expansion rule",
        "",
        EXPANSION,
        "### Candidates",
        "",
    ]
    for c in items:
        out += render_candidate(c, records, rules, existing)
    out += [
        "## Checklist for the owner",
        "",
        "| id | chain courses match the catalog (yes/no) | question natural (yes/no) | keep / edit / drop |",
        "|---|---|---|---|",
    ] + [f"| {c['id']} | | | |" for c in items]
    out += ["", "## What looked inconsistent in the data (not fixed)", ""] + data_notes(records, rules) + [""]
    return "\n".join(out)


def main() -> int:
    records = load_records()
    rules = json.loads(RULES.read_text(encoding="utf-8"))
    OUT.write_text(render(records, rules, highest_question_number() + 1, existing_chain_sources()), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
