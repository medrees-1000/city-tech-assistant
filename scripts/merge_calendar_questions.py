"""Append the owner-approved calendar questions (step 4a-1) to eval/questions.jsonl.

    uv run python scripts/merge_calendar_questions.py

The rows come from scripts/make_calendar_candidates.py (decisions kept or edited, not dropped). The
script only appends: it refuses to run if any of the ids is already in the file, never changes an
existing line, and writes the same compact JSON as the existing rows.
"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_candidates():
    spec = importlib.util.spec_from_file_location(
        "make_calendar_candidates", ROOT / "scripts" / "make_calendar_candidates.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_calendar_candidates"] = module
    spec.loader.exec_module(module)
    return module


def merge(path: Path, rows: list[dict]) -> list[str]:
    """Append the rows to the JSONL file and return their ids. Refuses on a duplicate id."""
    text = path.read_text(encoding="utf-8")
    present = {json.loads(line)["id"] for line in text.splitlines() if line.strip()}
    clash = sorted(present & {r["id"] for r in rows})
    if clash:
        raise ValueError(f"already in {path.name}: {clash}")
    lines = [json.dumps(r, separators=(",", ":"), ensure_ascii=False) for r in rows]
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text + "\n".join(lines) + "\n", encoding="utf-8")
    return [r["id"] for r in rows]


def main() -> int:
    mcc = load_candidates()
    events = json.loads(mcc.CALENDAR.read_text(encoding="utf-8"))
    contact = None
    if mcc.REGISTRAR.exists():
        record = json.loads(mcc.REGISTRAR.read_text(encoding="utf-8"))
        contact = ", ".join([*record["emails"], *record["phones"]]) or None
    try:
        ids = merge(mcc.QUESTIONS, mcc.kept_rows(events, contact))
    except ValueError as e:
        print(f"refused: {e}")
        return 1
    print(f"appended {len(ids)} questions: {', '.join(ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
