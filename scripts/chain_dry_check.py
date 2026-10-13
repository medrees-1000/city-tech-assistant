"""Dry check of the chain tool (step 4b, part 3): the walk and the extraction against the golds. No model call.

    uv run python scripts/chain_dry_check.py        # prints the table and writes docs/step4b-dry-check.md
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cta.graph import chain  # noqa: E402

OUT = ROOT / "docs" / "step4b-dry-check.md"
IDS = [f"q{n}" for n in range(76, 88)] + ["q22", "q39", "q40"]  # the 12 candidates, then the older dev chain ones
EXPLAIN = {
    "q82": "unanswerable: the text is shorthand (UNPARSED), the walk shows it verbatim; the gold has no sources by the unanswerable convention (reference record catalog:CST 3508)",
    "q83": "ABSTAIN: no record, the chain node abstains; the gold has no sources",
    "q84": "ABSTAIN: no record in the four departments; the chain node abstains; the gold has no sources",
    "q87": "control, not a chain question: the classifier must not send it to the chain tool; the gold is the root record only",
    "q22": "older gold lists the root only (its gold answer text names the chain); the walk adds the whole chain",
    "q39": "older gold has MAT 1275 and MAT 1275CO at level 5, beyond the depth limit of 4 (the walk records the cut)",
}


def main() -> int:
    records = chain.load_records()
    questions = {q["id"]: q for q in map(json.loads, (ROOT / "eval" / "questions.jsonl").read_text().splitlines())}
    rows = ["| id | extraction | walk (records) | levels | truncated | gold sources | missing from walk | extra in walk | note |", "|---|---|---|---|---|---|---|---|---|"]
    problems = []
    for qid in IDS:
        q = questions[qid]
        gold = [g["id"].removeprefix("catalog:") for g in q["gold_sources"]]
        found = chain.extract_course(q["question"], records)
        result = chain.prerequisite_chain.invoke({"course_code": found.code}) if found.code else {"found": False}
        walk = [c["code"] for c in result.get("courses", [])]
        missing, extra = [g for g in gold if g not in walk], [w for w in walk if w not in gold]
        levels = max((c["level"] for c in result.get("courses", [])), default="-")
        note = EXPLAIN.get(qid, "")
        if (missing or extra) and not note:
            problems.append(qid)
            note = "UNEXPLAINED"
        if found.status not in ("code", "title"):
            problems.append(qid)
            note += " EXTRACTION FAILED"
        rows.append(f"| {qid} | {found.status} {found.code} | {', '.join(walk) or '-'} | {levels} | {result.get('truncated', '-')} | {', '.join(gold) or '-'} | {', '.join(missing) or '-'} | {', '.join(extra) or '-'} | {note} |")
    text = "# Dry check of the chain walk against the golds (step 4b, part 3)\n\nThe walk is `cta.graph.chain` (the tool), the extraction runs on the question text. No model call.\n\n" + "\n".join(rows) + f"\n\nUnexplained differences: {sorted(set(problems)) or 'none'}.\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
