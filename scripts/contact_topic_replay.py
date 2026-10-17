"""Free replay of the topic-cue contact logic over stored refusals (no model call, no network).

    uv run python scripts/contact_topic_replay.py [--table]

Reads the question, the abstain flag and the abstain reason of every stored request of the four
runs below from request_logs and runs them through cta.graph.contact.offices_for. Prints the
summary (how many refusals gained which office, how many got none); --table prints every row.
Nothing is written.
"""

import sys
from collections import Counter
from types import SimpleNamespace

from cta.graph import contact
from cta.index.db import connect

LABELS = ("final-config-dev", "final-run", "cv2-baseline", "cv2-fix")


def old_offices(question: str, reason: str, table: dict) -> list[str]:
    """What the code before batch 1 chose (rules 1 to 4 only)."""
    ans = SimpleNamespace(abstain_reason=reason)
    if reason.startswith("calendar_"):
        return ["registrar"]
    if reason == "chain_no_record":
        d = contact.named_department(question)
        return [d] if d else []
    if reason == "chain_outside_departments":
        return []
    first = contact.named_department(question) or contact.cue_office(question, table)
    return [first] if first else []


def main(argv: list[str]) -> int:
    table = contact.load_contacts()
    rows = []
    with connect() as conn:
        for label in LABELS:
            run = conn.execute(
                "SELECT max(id) FROM eval_runs WHERE label = %s", (label,)
            ).fetchone()[0]
            for q, abstained, reason in conn.execute(
                "SELECT question, abstained, coalesce(abstain_reason, '') FROM request_logs "
                "WHERE run_id = %s",
                (run,),
            ):
                if abstained:
                    ans = SimpleNamespace(abstain_reason=reason)
                    rows.append((label, q, old_offices(q, reason, table),
                                 contact.offices_for(q, ans, table)))  # fmt: skip
    gained = [r for r in rows if not r[2] and r[3]]
    changed = [r for r in rows if r[2] and r[2] != r[3]]
    none = [r for r in rows if not r[3]]
    print(f"{len(rows)} stored refusals in {len(LABELS)} runs")
    print(f"already had an office, unchanged: {sum(1 for r in rows if r[2] and r[2] == r[3])}")
    print(f"already had an office, changed (must be 0): {len(changed)}")
    print(f"gained an office: {len(gained)}  " + str(Counter(tuple(r[3]) for r in gained)))
    print(f"still no office: {len(none)}")
    if "--table" in argv:
        for label, q, old, new in rows:
            print(f"{label:17}| {q[:70]:70} | old {old or '-'} | new {new or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
