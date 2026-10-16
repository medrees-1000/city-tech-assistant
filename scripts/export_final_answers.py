"""Export the stored answers of an eval run to eval/results/<label>-answers.jsonl (read-only SQL).

    uv run python scripts/export_final_answers.py final-run

request_logs is purged after 30 days and eval/results/<label>.json holds no answer text, so this
keeps the answers. Fields: id, question, route, abstained, abstain_reason, citations (from the
results file), answer (as stored, i.e. redacted), sources_shown (the chunk, course or calendar-row
ids the log holds for the request; their text is not stored in the log).
"""

import json
import re
import sys
from pathlib import Path

from cta.index.db import connect
from cta.redact import redact

ROOT = Path(__file__).resolve().parent.parent
PERSONAL = re.compile(
    r"\[(EMAIL|PHONE|SSN|ID|NAME)\]|[\w.+-]+@[\w-]+\.[\w.]+|\d{3}[-. ]\d{3}[-. ]\d{4}|\b\d{8,}\b"
    r"|my name is|\bssn\b",
    re.I,
)


def main(label: str) -> int:
    results = json.loads((ROOT / "eval" / "results" / f"{label}.json").read_text())
    questions = {}
    for line in (ROOT / "eval" / "questions.jsonl").read_text().splitlines():
        q = json.loads(line)
        questions[q["id"]] = q
    rows = []
    with connect() as conn:
        run_id = conn.execute(
            "SELECT max(id) FROM eval_runs WHERE label = %s", (label,)
        ).fetchone()[0]
        logs = {}
        for r in conn.execute(
            "SELECT question, route, abstained, abstain_reason, answer, retrieved "
            "FROM request_logs WHERE run_id = %s",
            (run_id,),
        ):
            logs.setdefault(r[0], []).append(r[1:])
    for rec in results["per_question"]:
        q = questions[rec["id"]]
        found = logs[redact(q["question"])]
        assert len(found) == 1, rec["id"]
        route, abstained, reason, answer, retrieved = found[0]
        hits = [t for t in (q["question"], answer) if PERSONAL.search(t)]
        if hits:
            print(f"personal-data pattern in {rec['id']}: {PERSONAL.search(hits[0]).group(0)!r}")
        rows.append({
            "id": rec["id"], "question": q["question"], "route": route, "abstained": abstained,
            "abstain_reason": reason, "citations": rec["citations"], "answer": answer,
            "sources_shown": [c["id"] for c in retrieved or []],
        })  # fmt: skip
    out = ROOT / "eval" / "results" / f"{label}-answers.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    ids_file = [r["id"] for r in results["per_question"]]
    print(f"run_id {run_id}: {len(rows)} rows written; ids match results file: {ids_file == [r['id'] for r in rows]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
