"""Append the 12 verified chain candidates (q76 to q87) to eval/questions.jsonl (step 4b-1).

    uv run python scripts/merge_chain_questions.py

Rows come from scripts/make_chain_candidates.py. The script only appends, refuses if any id is already
in the file, never changes an existing line, and writes the same compact JSON as the other rows.
"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    chain = load("make_chain_candidates")
    merge = load("merge_calendar_questions").merge  # the same append-only helper as step 4a-1
    rows = chain.question_rows(chain.load_records())
    try:
        ids = merge(chain.QUESTIONS, rows)
    except ValueError as e:
        print(f"refused: {e}")
        return 1
    print(f"appended {len(ids)} questions: {', '.join(ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
