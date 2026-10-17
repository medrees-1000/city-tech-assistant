"""Free replay of explain_shorthand over every stored answer (no model call, no network).

    uv run python scripts/shorthand_replay.py

Prints how many stored answers would change, and for each: log id, run, route, the sentence
before and after. Rows whose text holds the chain renderer's '**Catalog says:**' lines are marked:
the renderer's verbatim text never passes through explain_shorthand in the live path.
"""

import sys

from cta.graph.chain import SHORTHAND_REPLACEMENT, explain_shorthand
from cta.index.db import connect


def main() -> int:
    with connect() as conn:
        rows = conn.execute(
            "SELECT l.id, e.label, l.route, l.answer FROM request_logs l "
            "JOIN eval_runs e ON e.id = l.run_id ORDER BY l.id"
        ).fetchall()
    changed = [(i, lab, route, a, explain_shorthand(a)) for i, lab, route, a in rows if a]
    changed = [r for r in changed if r[3] != r[4]]
    print(f"{len(rows)} stored answers with a run label; {len(changed)} would change")
    for i, lab, route, before, after in changed:
        renderer = "**Catalog says:**" in before
        k = after.find(SHORTHAND_REPLACEMENT)
        b = before.find("PRE_")
        print(
            f"- log id {i} | run {lab} | route {route} | {'chain renderer, unchanged live' if renderer else 'model-written'}"
        )
        print(f"    before: ...{before[max(0, b - 60) : b + 45]!r}")
        print(f"    after:  ...{after[max(0, k - 60) : k + 90]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
