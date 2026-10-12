"""Compare two retrieval-only runs (the output of cta.eval.run_retrieval) and apply a decision rule.

    uv run python -m cta.eval.compare eval/results/OLD.json eval/results/NEW.json

Prints the overall and chain-row metrics with their change, the change by question type, the first
relevant rank of every question before and after (a question that is not found in the top 10 is
"miss"), the improved and worsened questions, and the verdict of the rule written in
docs/experiments.md before the run (step 1: hybrid search).
"""

import json
import sys
from pathlib import Path

METRICS = (
    "recall@1",
    "hit@1",
    "recall@3",
    "hit@3",
    "recall@5",
    "hit@5",
    "recall@10",
    "hit@10",
    "mrr",
)
MISS = 11  # a question not found in the top 10 counts as rank 11 when ranks are compared
MIN_GAIN = 0.01  # the rule: MRR or recall@5 must improve by at least this much
MAX_DROP = 0.02  # and neither may drop by more than this


def rank_of(value: int | None) -> int:
    return MISS if value is None or value > 10 else value


def shown(value: int | None) -> str:
    return "miss" if rank_of(value) == MISS else str(value)


def deltas(old: dict, new: dict) -> dict[str, float]:
    return {m: new[m] - old[m] for m in METRICS}


def verdict(old: dict, new: dict) -> tuple[bool, str]:
    """The step 1 rule: keep if MRR or recall@5 improves by >= 0.01 and neither drops by > 0.02."""
    d = deltas(old, new)
    gain = max(d["mrr"], d["recall@5"]) >= MIN_GAIN - 1e-12
    drop = min(d["mrr"], d["recall@5"]) < -MAX_DROP - 1e-12
    text = (
        f"MRR {d['mrr']:+.3f}, recall@5 {d['recall@5']:+.3f}: "
        f"{'an improvement of at least 0.01' if gain else 'no improvement of 0.01'}; "
        f"{'a drop of more than 0.02' if drop else 'no drop of more than 0.02'}"
    )
    return gain and not drop, text


def changes(old_q: list[dict], new_q: list[dict]) -> tuple[list, list, list]:
    """(improved, worsened, same) as (id, rank before, rank after) over questions in both runs."""
    before = {q["id"]: q["first_rank"] for q in old_q}
    improved, worsened, same = [], [], []
    for q in new_q:
        a, b = before[q["id"]], q["first_rank"]
        bucket = (
            improved if rank_of(b) < rank_of(a) else worsened if rank_of(b) > rank_of(a) else same
        )
        bucket.append((q["id"], a, b))
    return improved, worsened, same


def metric_rows(label: str, old: dict | None, new: dict | None) -> list[str]:
    if not old or not new:
        return [f"{label}: not available in one of the runs"]
    lines = [
        f"{label} (n={old['n']} before, {new['n']} after)",
        f"  {'':10}{'before':>8}{'after':>8}{'change':>9}",
    ]
    for m in METRICS:
        lines.append(f"  {m:10}{old[m]:>8.3f}{new[m]:>8.3f}{new[m] - old[m]:>+9.3f}")
    return lines


def report(old: dict, new: dict) -> str:
    out = [
        f"before: {old['label']} (mode {old.get('retrieval_mode', '?')})   "
        f"after: {new['label']} (mode {new.get('retrieval_mode', '?')})",
        "",
    ]
    out += metric_rows("Overall", old["metrics"], new["metrics"]) + [""]
    out += metric_rows(
        "Chain-tagged row (reported separately, not part of the rule)",
        old.get("metrics_chain"),
        new.get("metrics_chain"),
    ) + [""]
    out.append("By type (small groups: read n)")
    out.append(f"  {'type':16}{'n':>3}{'MRR before':>12}{'after':>8}{'R@5 before':>12}{'after':>8}")
    for t, a in old["by_type"].items():
        b = new["by_type"].get(t)
        if b:
            out.append(
                f"  {t:16}{a['n']:>3}{a['mrr']:>12.3f}{b['mrr']:>8.3f}"
                f"{a['recall@5']:>12.3f}{b['recall@5']:>8.3f}"
            )
    improved, worsened, same = changes(old["per_question"], new["per_question"])
    out += [
        "",
        "First relevant rank per question (miss = not in the top 10)",
        f"  {'id':5}{'type':16}{'before':>8}{'after':>8}  change",
    ]
    types = {q["id"]: q["type"] for q in new["per_question"]}
    for qid, a, b in sorted(improved + worsened + same):
        mark = "better" if (qid, a, b) in improved else "WORSE" if (qid, a, b) in worsened else ""
        out.append(f"  {qid:5}{types[qid]:16}{shown(a):>8}{shown(b):>8}  {mark}")
    fmt = lambda rows: ", ".join(f"{q} ({shown(a)}->{shown(b)})" for q, a, b in rows) or "none"  # noqa: E731
    out += [
        "",
        f"Improved ({len(improved)}): {fmt(improved)}",
        f"Worsened ({len(worsened)}): {fmt(worsened)}",
        f"Unchanged: {len(same)}",
    ]
    la, lb = old.get("retrieval_latency_ms"), new.get("retrieval_latency_ms")
    if la and lb and la["median"] is not None and lb["median"] is not None:
        out += [
            "",
            f"Search time per question: median {la['median']:.1f} -> {lb['median']:.1f} ms, "
            f"p95 {la['p95']:.1f} -> {lb['p95']:.1f} ms (n={lb['n']})",
        ]
    keep, why = verdict(old["metrics"], new["metrics"])
    out += [
        "",
        f"Pre-registered rule (docs/experiments.md, steps 1 and 1b): {why}",
        f"=> {'KEEP' if keep else 'REJECT'} for retrieval",
    ]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: python -m cta.eval.compare OLD.json NEW.json")
        return 2
    old, new = (json.loads(Path(p).read_text(encoding="utf-8")) for p in argv[1:])
    print(report(old, new))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
