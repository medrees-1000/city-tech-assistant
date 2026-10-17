"""Blind export for hand grading (docs/decisions.md, "Version 2, casual wording: pre-registration").

    uv run python -m cta.eval.blind_export BASELINE-answers.jsonl FIX-answers.jsonl OUT-PREFIX

Reads the two answer files written by scripts/export_final_answers.py and writes
OUT-PREFIX-blind.jsonl (one row per question: the two answers as "A" and "B", the configuration
hidden, the A/B assignment random per question) and OUT-PREFIX-key.json (which configuration is
A for each question). Open the key file only after grading. Calls no model and no database.
Fields that would give the configuration away (route, abstain reason) are left out.
"""

import json
import random
import sys
from pathlib import Path

SHOWN = ("answer", "citations", "sources_shown")


def load_answers(path: Path) -> dict[str, dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return {r["id"]: r for r in rows}


def blind_rows(
    baseline: dict[str, dict], fix: dict[str, dict], rng: random.Random
) -> tuple[list[dict], dict[str, dict[str, str]]]:
    """(rows to grade, key). The same question ids must be in both runs. Rows are shuffled too,
    so the file order does not follow the run order."""
    if baseline.keys() != fix.keys():
        only = sorted(baseline.keys() ^ fix.keys())
        raise ValueError(f"the two runs do not have the same questions: {', '.join(only)}")
    rows, key = [], {}
    for qid in baseline:
        baseline_is_a = rng.random() < 0.5
        a, b = (baseline[qid], fix[qid]) if baseline_is_a else (fix[qid], baseline[qid])
        key[qid] = {
            "A": "baseline" if baseline_is_a else "fix",
            "B": "fix" if baseline_is_a else "baseline",
        }
        rows.append({
            "id": qid, "question": baseline[qid]["question"],
            **{f"{f}_A": a.get(f) for f in SHOWN}, **{f"{f}_B": b.get(f) for f in SHOWN},
        })  # fmt: skip
    rng.shuffle(rows)
    return rows, key


def main(argv: list[str], rng: random.Random | None = None) -> int:
    if len(argv) != 4:
        print("usage: blind_export BASELINE-answers.jsonl FIX-answers.jsonl OUT-PREFIX")
        return 2
    baseline, fix = load_answers(Path(argv[1])), load_answers(Path(argv[2]))
    out = Path(argv[3])
    blind, key = out.with_name(out.name + "-blind.jsonl"), out.with_name(out.name + "-key.json")
    if blind.exists() or key.exists():
        print(f"refused: {blind.name} or {key.name} already exists")
        return 2
    try:
        rows, assignment = blind_rows(baseline, fix, rng or random.SystemRandom())
    except ValueError as e:
        print(f"refused: {e}")
        return 2
    blind.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    key.write_text(json.dumps(assignment, indent=1) + "\n", encoding="utf-8")
    print(f"{len(rows)} questions written to {blind.name}; the key is in {key.name} (not yet)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
