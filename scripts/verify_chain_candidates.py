"""Independent check of docs/chain-candidates.md against the raw saved catalog JSON (step 4b-1).

    uv run python scripts/verify_chain_candidates.py

Standard library only, and deliberately NOT built on make_chain_candidates.py: it reads the raw
course search pages (data/raw/app.coursedog.com), the raw requirement-group (rule) files, the rule
cache and the contact chunks itself, and re-derives each chain with its own code reading.
Checks per candidate: a) records equal raw; b) codes in prerequisite texts are in the chain, an
exclusion or "no record", and the chain has no extras; c) gold sources; d) no lost prerequisite field
(q79, q81); e) CST 4999 absent from the full raw list (q83); f) ENG 1101 in the full list? (q84);
g) the title "Database Design" is unique among the four departments' records (q85); h) contact lines
equal the contact chunks. Prints a table and exits 1 if anything fails.
"""

import json
import re
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "app.coursedog.com"
CACHE = ROOT / "data" / "processed" / "rules_cache.json"
CHUNKS = ROOT / "data" / "processed" / "chunks.jsonl"
CANDIDATES = ROOT / "docs" / "chain-candidates.md"
FOUR = {"CST-NYT", "MATH-NYT", "EET-NYT", "DENT-NYT"}
CHECKS = "abcdefgh"
LEVEL_LIMIT = 4
STOP = {"OR", "AND", "OF", "TO", "IN", "FOR", "WITH", "BY", "ON", "AT", "IS", "AS", "TWO", "ONE"}
PRE_WORDS = re.compile(r"prereq|corequisite|pre-?req", re.I)


@dataclass
class Result:
    qid: str
    passed: dict[str, bool | None] = field(default_factory=dict)  # None = not applicable
    notes: list[str] = field(default_factory=list)

    def fail(self, check: str, note: str) -> None:
        self.passed[check] = False
        self.notes.append(f"{check}: {note}")


# ---- raw data ----


def load_raw_courses(raw: Path = RAW) -> dict[str, list[dict]]:
    """code -> every raw record with that code (the saved pages overlap, so a code repeats)."""
    out: dict[str, list[dict]] = {}
    for path in sorted(raw.glob("api-v1-cm-nyt01-courses-search*.json")):
        for rec in json.loads(path.read_text(encoding="utf-8")).get("data", []):
            out.setdefault(rec["code"], []).append(rec)
    return out


def load_raw_rules(raw: Path = RAW) -> dict[str, str]:
    """rule id -> text, read from the raw requirement-group files."""
    out: dict[str, str] = {}
    for path in sorted(raw.glob("api-v1-nyt01-requirementGroups-*.json")):
        for rid, body in json.loads(path.read_text(encoding="utf-8")).get("data", {}).items():
            out[rid] = body.get("descriptionLong") or body.get("catalogDisplayName") or ""
    return out


def distinct(records: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in records:
        if r["_id"] not in seen:
            seen.add(r["_id"])
            out.append(r)
    return out


def in_four(rec: dict) -> bool:
    return any(d.get("id") in FOUR for d in rec.get("departments", []))


# ---- the candidate file ----


def split_row(line: str) -> list[str]:
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def parse_candidates(text: str) -> dict[str, dict]:
    """qid -> {question, gold_sources, rows, gold (blockquote lines), body}."""
    out = {}
    for block in re.split(r"(?m)^## (?=q\d+ )", text)[1:]:
        qid = block.split(" ", 1)[0]
        sources = re.search(r"\*\*Gold sources:\*\* (.*)", block)
        rows = []
        for line in block.splitlines():
            if re.match(r"\| \d+ \|", line):
                level, code, title, ptext, rule, group = split_row(line)
                rows.append({"level": int(level), "code": code, "title": title, "text": ptext, "rule": rule, "group": group})
        tags = re.search(r"\*\*Tags:\*\* ([^|\n]*)", block)
        kind = re.search(r"\*\*Type:\*\* (\w+)", block)
        out[qid] = {
            "chain": bool(tags and "chain" in tags.group(1)),
            "type": kind.group(1) if kind else "",
            "gold_sources": re.findall(r"`catalog:([^`]+)`", sources.group(1)) if sources else [],
            "rows": rows,
            "gold": [ln[2:] for ln in block.splitlines() if ln.startswith("> ")],
            "body": block,
        }
    return out


# ---- reading prerequisite texts (own implementation) ----


def read_text(text: str, own: str) -> tuple[list[str], list[str], str | None]:
    """(codes to follow, exclusions, unparsed reason) from a prerequisite text."""
    if not text.strip():
        return [], [], None
    if re.search(r"PRE_|\b[A-Z]{2,5}\d{3,4}_[A-Z]", text):
        return [], [], "shorthand"
    if re.search(r"[A-Za-z]{2,5}\d{1,2}\s*$", text.strip()):
        return [], [], "truncated"
    follow, exclude = [], []
    for clause in re.split(r"[.;\n]", text):
        neg = re.search(r"\b(must not|not have|not)\b", clause, re.I)
        last_prefix = None
        for m in re.finditer(r"\b([A-Za-z]{2,5})\s?(\d{3,4})([A-Za-z]{0,2})\b(?!-?\s*level)|(?<![\w-])(\d{4})(?![\w-])(?!\s*-?\s*level)", clause, re.I):
            if m.group(1) and m.group(1).upper() in STOP:  # "or 2415": a bare number after a joining word
                if not last_prefix or m.group(3):
                    continue
                code = f"{last_prefix} {m.group(2)}"
            elif m.group(1):
                last_prefix = m.group(1).upper()
                code = f"{last_prefix} {m.group(2)}{m.group(3).upper()}"
            elif last_prefix:
                code = f"{last_prefix} {m.group(4)}"
            else:
                continue
            if code == own:
                continue
            bucket = exclude if neg and m.start() >= neg.end() else follow
            if code not in bucket:
                bucket.append(code)
    return follow, exclude, None


def my_chain(root: str, texts: dict[str, str]) -> tuple[dict[str, int], dict[str, list[str]]]:
    """(code -> level, code -> exclusions) by breadth-first reading; `texts` holds the rule text of
    every code that has a record. Level limit 4: courses at level 4 are not read."""
    levels, exclusions = {root: 0}, {}
    queue = deque([root])
    while queue:
        code = queue.popleft()
        if code not in texts or levels[code] >= LEVEL_LIMIT:
            continue
        follow, exclude, _ = read_text(texts[code], code)
        exclusions[code] = exclude
        for nxt in follow:
            if nxt not in levels:
                levels[nxt] = levels[code] + 1
                queue.append(nxt)
    return levels, exclusions


# ---- the checks ----


def record_text(raw_rec: dict, cache: dict, raw_rules: dict) -> tuple[str, list[str]]:
    """The prerequisite text of a raw record: the cached rule text, which must equal the raw rule file's text."""
    rid, problems = raw_rec.get("requirementGroup"), []
    if not rid:
        return "", problems
    cached, raw = (cache.get(rid) or {}).get("text"), raw_rules.get(rid)
    if cached is None or raw is None or cached != raw:
        problems.append(f"rule {rid}: cache {cached!r} against raw rule file {raw!r}")
    return cached or raw or "", problems


def check_candidate(qid: str, sec: dict, raw: dict[str, list[dict]], cache: dict, raw_rules: dict) -> Result:
    res = Result(qid, {c: True for c in "abc"})
    rows = sec["rows"]
    four_codes = {c for c, recs in raw.items() if any(in_four(r) for r in recs)}
    texts: dict[str, str] = {}
    for row in rows:
        code, recs = row["code"], distinct(raw.get(row["code"], []))
        if row["title"] == "-":  # a "no record" row
            if code in four_codes:
                res.fail("a", f"{code} is shown as no record but the raw data has it in the four departments")
            continue
        if len(recs) != 1:
            res.fail("a", f"{code}: {len(recs)} distinct raw records")
            continue
        rec = recs[0]
        text, problems = record_text(rec, cache, raw_rules)
        for p in problems:
            res.fail("a", p)
        texts[code] = text
        shown = row["text"] if row["text"] != "-" else ""
        if row["title"].strip() != rec["name"].strip():
            res.fail("a", f"{code} title {row['title']!r} against raw {rec['name']!r}")
        if shown != text.replace("\n", " / "):
            res.fail("a", f"{code} prerequisite text differs from raw rule text")
        if (row["rule"] if row["rule"] != "-" else None) != (rec.get("requirementGroup") or None):
            res.fail("a", f"{code} requirementGroup id differs")
        if row["group"] != rec["courseGroupId"]:
            res.fail("a", f"{code} courseGroupId differs")
    if not rows:  # an abstain candidate has no table
        res.passed["a"] = res.passed["b"] = None
        res.passed["c"] = not sec["gold_sources"]
        if sec["gold_sources"]:
            res.fail("c", "an abstain candidate lists gold sources")
        return res
    if not sec["chain"]:  # a boundary control or similar: one record, no chain expected
        res.passed["b"] = None
        res.notes.append("b: not a chain question (no chain tag); only the single record is checked")
        expected = [r["code"] for r in rows if r["title"] != "-"]
        if len(rows) != 1 or sec["gold_sources"] != expected:
            res.fail("c", f"gold sources {sec['gold_sources']} against the single record {expected}")
        return res
    root = rows[0]["code"]
    levels, exclusions = my_chain(root, texts)
    table = {r["code"]: r["level"] for r in rows}
    if levels != table:
        res.fail("b", f"chain differs: only in my reading {sorted(set(levels) - set(table))}, only in the file {sorted(set(table) - set(levels))}, level differences {[c for c in set(levels) & set(table) if levels[c] != table[c]]}")
    for code, excluded in exclusions.items():
        for x in excluded:
            if x in table:
                res.fail("b", f"{x} is an exclusion of {code} but is in the chain")
    for code, text in texts.items():
        follow, _, why = read_text(text, code)
        for nxt in follow:
            if levels.get(code, 99) < LEVEL_LIMIT and nxt not in table:
                res.fail("b", f"{nxt} is named in {code} but is not in the chain")
    expected = [r["code"] for r in rows if r["title"] != "-"]
    if sec["type"] == "unanswerable":  # the convention of existing unanswerable questions: no gold sources
        if sec["gold_sources"] or f"catalog:{root}" not in sec["body"]:
            res.fail("c", "an unanswerable candidate must list no gold sources and name its reference record in the note")
    elif sec["gold_sources"] != expected:
        res.fail("c", f"gold sources {sec['gold_sources']} against chain records {expected}")
    return res


def lost_field_check(res: Result, code: str, raw: dict[str, list[dict]], cache: dict) -> None:
    """d) the raw record has no requirementGroup and no prerequisite wording in any field except the description."""
    recs = distinct(raw.get(code, []))
    res.passed["d"] = True
    if len(recs) != 1:
        res.fail("d", f"{code}: {len(recs)} distinct raw records")
        return
    rec = recs[0]
    names = sorted(rec)
    res.notes.append(f"d: fields checked for {code}: {', '.join(names)}; requirementGroup = {rec.get('requirementGroup')!r}")
    if rec.get("requirementGroup"):
        res.fail("d", f"{code} has requirementGroup {rec['requirementGroup']}")
    for key, value in rec.items():
        if key != "description" and PRE_WORDS.search(json.dumps(value)):
            res.fail("d", f"{code}: field {key} mentions prerequisites")
    if PRE_WORDS.search(rec.get("description") or ""):
        res.notes.append(f"d: the description of {code} mentions prerequisites (read it)")


def absent_check(res: Result, code: str, raw_dir: Path, raw: dict[str, list[dict]]) -> None:
    """e) the code appears nowhere in the full raw list, in any field or form."""
    res.passed["e"] = True
    compact = code.replace(" ", "")
    for recs in raw.values():
        for rec in recs:
            blob = json.dumps(rec)
            if code in blob or compact in blob or code.replace(" ", "-") in blob:
                res.fail("e", f"{code} appears in raw record {rec['code']}")
    hits = [p.name for p in raw_dir.glob("api-v1-cm-nyt01-courses-search*.json") if code in p.read_text(encoding="utf-8") or compact in p.read_text(encoding="utf-8")]
    if hits:
        res.fail("e", f"{code} appears in raw files {hits[:3]}")
    records = {r["_id"] for recs in raw.values() for r in recs}
    statuses = {r.get("status") for recs in raw.values() for r in recs}
    dupes = sorted(c for c, recs in raw.items() if len(distinct(recs)) > 1)
    res.notes.append(f"e: {len(records)} distinct records ({len(raw)} distinct codes; codes with two records: {dupes or 'none'}) in the saved raw pages (the search reported 1445 courses), statuses {sorted(statuses)}; no inactive or legacy forms are saved; searched every field of every record and the raw files as text for {code}")


def exists_check(res: Result, code: str, raw: dict[str, list[dict]]) -> None:
    """f) report whether the code exists in the full raw list (either answer passes)."""
    res.passed["f"] = True
    recs = distinct(raw.get(code, []))
    if recs:
        res.notes.append(f"f: {code} exists in the full raw list ({recs[0]['name']}; departments {[d['id'] for d in recs[0].get('departments', [])]}), outside the four departments")
    else:
        res.notes.append(f"f: {code} is not in the full raw list")


def title_check(res: Result, phrase: str, raw: dict[str, list[dict]]) -> None:
    """g) the exact title belongs to one record among the four departments'; other titles containing it."""
    res.passed["g"] = True
    four = [r for recs in raw.values() for r in distinct(recs) if in_four(r)]
    four = list({r["_id"]: r for r in four}.values())
    exact = [r["code"] for r in four if r["name"].strip().lower() == phrase.lower()]
    other = [r["code"] for r in four if phrase.lower() in r["name"].lower() and r["code"] not in exact]
    if len(exact) != 1:
        res.fail("g", f"title {phrase!r} belongs to {exact}")
    res.notes.append(f"g: {len(four)} records in the four departments; exact title {exact}; other titles containing the phrase: {other or 'none'}")


def contact_check(res: Result, body: str, chunks: dict[str, str], key: str) -> None:
    """h) the emails and phones in the candidate equal the contact chunk's, with no stray spaces."""
    res.passed["h"] = True
    chunk = chunks.get(key)
    if chunk is None:
        res.fail("h", f"no contact chunk {key}")
        return
    line = re.search(r"(?:contact the department|Contact the answer should name \([^)]*\)): ([^\n]*?)\.?\s*$", body, re.M)
    if not line:
        res.fail("h", "no contact line found")
        return
    parts = line.group(1).rstrip(".").split(", ")
    for part in parts:
        if part != part.strip() or " " in part:
            res.fail("h", f"stray space in {part!r}")
        if part not in chunk:
            res.fail("h", f"{part!r} is not in the {key} contact chunk")
    in_chunk = set(re.findall(r"[\w.]+@[\w.]+", chunk)) | set(re.findall(r"\d{3}-\d{3}-\d{4}", chunk))
    if not set(parts) <= in_chunk:
        res.fail("h", f"{sorted(set(parts) - in_chunk)} not an email or phone of the chunk")
    res.notes.append(f"h: {key}: {', '.join(parts)}")


def load_contact_chunks(path: Path = CHUNKS) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        chunk = json.loads(line)
        if chunk["id"].startswith("contact:"):
            out[chunk["id"]] = chunk["text"]
    return out


def verify(candidates: dict[str, dict], raw: dict[str, list[dict]], cache: dict, raw_rules: dict,
           chunks: dict[str, str], raw_dir: Path = RAW) -> list[Result]:  # fmt: skip
    results = {qid: check_candidate(qid, sec, raw, cache, raw_rules) for qid, sec in candidates.items()}
    for qid, code in (("q79", "EET 3572"), ("q81", "CST 2304")):
        if qid in results:
            lost_field_check(results[qid], code, raw, cache)
    if "q83" in results:
        absent_check(results["q83"], "CST 4999", raw_dir, raw)
    if "q84" in results:
        exists_check(results["q84"], "ENG 1101", raw)
    if "q85" in results:
        title_check(results["q85"], "Database Design", raw)
    for qid, key in (("q82", "contact:CST-NYT"), ("q83", "contact:CST-NYT"), ("q84", "contact:registrar")):
        if qid in results:
            contact_check(results[qid], candidates[qid]["body"], chunks, key)
    return list(results.values())


def table(results: list[Result]) -> str:
    mark = {True: "pass", False: "FAIL", None: "-"}
    lines = ["| id | " + " | ".join(CHECKS) + " | notes |", "|---|" + "---|" * len(CHECKS) + "---|"]
    for r in results:
        cells = [mark[r.passed.get(c)] if c in r.passed else "-" for c in CHECKS]
        lines.append(f"| {r.qid} | " + " | ".join(cells) + " | " + "; ".join(r.notes).replace("|", "/") + " |")
    return "\n".join(lines)


def main() -> int:
    candidates = parse_candidates(CANDIDATES.read_text(encoding="utf-8"))
    results = verify(
        candidates, load_raw_courses(), json.loads(CACHE.read_text(encoding="utf-8")), load_raw_rules(), load_contact_chunks()
    )
    print(table(results))
    failed = [r.qid for r in results if any(v is False for v in r.passed.values())]
    print(f"\n{len(results)} candidates checked; failed: {failed or 'none'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
