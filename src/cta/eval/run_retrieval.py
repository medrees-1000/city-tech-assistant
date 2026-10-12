"""Run the retrieval-only evaluation (no LLM call): search k = 10 once per question, then score.

    uv run python -m cta.eval.run_retrieval --split dev --label baseline-retrieval-dev

--split test is refused unless --final is also given (only the final baseline run uses it).
Saves a row in eval_runs and a summary (ids and ranks only, no chunk text) in
eval/results/<label>.json.
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict

from psycopg.types.json import Jsonb

from cta.eval.metrics import KS, average, question_metrics, scorable_gold
from cta.eval.questions import load_questions
from cta.index.db import connect
from cta.index.embed import ApiError
from cta.index.search import search
from cta.settings import ROOT, load_models

RESULTS = ROOT / "eval" / "results"
RETRIEVE_K = 10
SHOWN = ("recall@{k}", "precision@{k}", "hit@{k}")


def check_split(split: str, final: bool) -> str | None:
    """An error message, or None when the run may go ahead."""
    if split == "test" and not final:
        return (
            "refused: --split test is only for the final baseline run (step 9). "
            "Pass --final if this really is that run."
        )
    return None


def git_state() -> dict:
    def git(*args):
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, cwd=ROOT
        ).stdout.strip()

    return {
        "commit": git("rev-parse", "--short", "HEAD"),
        "dirty": bool(git("status", "--porcelain")),
    }


def score(questions: list[dict], retrieved: dict[str, list[dict]]):
    """(scored per-question results, ids of the excluded questions)."""
    scored, excluded = [], []
    for q in questions:
        m = question_metrics(retrieved[q["id"]], scorable_gold(q))
        if m is None:
            excluded.append(q["id"])
        else:
            scored.append(
                {
                    "id": q["id"],
                    "type": q["type"],
                    "department": q["department"],
                    "tags": q.get("tags", []),
                    **m,
                }
            )
    return scored, excluded


def group_by(scored: list[dict], key: str) -> dict[str, dict]:
    groups = defaultdict(list)
    for r in scored:
        groups[r[key] or "(none)"].append(r)
    return {name: average(rows) for name, rows in sorted(groups.items())}


def fmt(x) -> str:
    return "-" if x is None else f"{x:.3f}"


def metrics_table(rows: dict[str, dict]) -> str:
    head = (
        f"{'':16}{'n':>3}  "
        + "  ".join(f"{m}@{k}" for k in KS for m in ("R", "P", "H"))
        + "     MRR"
    )
    lines = [head]
    for name, a in rows.items():
        cells = "  ".join(
            f"{fmt(a[f'{m}@{k}']):>5}" for k in KS for m in ("recall", "precision", "hit")
        )
        lines.append(f"{name:16}{a['n']:>3}  {cells}   {fmt(a['mrr'])}")
    return "\n".join(lines)


def per_question_table(scored: list[dict], retrieved: dict[str, list[dict]]) -> str:
    lines = [f"{'id':5}{'type':16}{'first relevant rank':>20}"]
    for r in scored:
        rank = r["first_rank"] if r["first_rank"] and r["first_rank"] <= RETRIEVE_K else "miss"
        lines.append(f"{r['id']:5}{r['type']:16}{rank!s:>20}")
        if rank == "miss":
            for c in retrieved[r["id"]][:3]:
                lines.append(f"      top: {c['similarity']:.3f}  {c['source_id']}")
    return "\n".join(lines)


def run(conn, questions: list[dict], label: str, split: str, cfg: dict, out=print) -> dict:
    retrieved, calls, hits, cost = {}, 0, 0, 0.0
    for q in questions:
        found = search(conn, q["question"], RETRIEVE_K, cfg=cfg)
        retrieved[q["id"]] = found.results
        calls += found.api_calls
        hits += found.cache_hit
        cost += found.cost
    scored, excluded = score(questions, retrieved)
    overall = average(scored)
    by_type, by_dept = group_by(scored, "type"), group_by(scored, "department")
    gone = ", ".join(excluded)
    out(f"split {split}: {len(questions)} questions, {len(scored)} scored, "
        f"{len(excluded)} excluded (no scorable gold source): {gone}")  # fmt: skip
    chain_rows = [r for r in scored if "chain" in r.get("tags", [])]
    chain = average(chain_rows) if chain_rows else None
    rows = {"all": overall} | ({"chain (tagged)": chain} if chain else {})
    out("\nOverall (the chain row is also counted inside 'all')\n" + metrics_table(rows))
    out("\nBy type (groups are small: read n before the numbers)\n" + metrics_table(by_type))
    out("\nBy department\n" + metrics_table(by_dept))
    out("\nPer question\n" + per_question_table(scored, retrieved))
    out(f"\nquery embeddings: {hits} cache hits, {calls} API calls, real cost ${cost:.7f}")
    ranks = [
        {
            "id": r["id"],
            "type": r["type"],
            "department": r["department"],
            "first_rank": r["first_rank"],
            "retrieved_ids": [c["source_id"] for c in retrieved[r["id"]]],
        }
        for r in scored
    ]
    return {
        "label": label,
        "split": split,
        "retrieve_k": RETRIEVE_K,
        "n_scored": len(scored),
        "excluded": excluded,
        "metrics": overall,
        "metrics_chain": chain,
        "by_type": by_type,
        "by_department": by_dept,
        "per_question": ranks,
        "cost": {"usd": cost, "api_calls": calls, "cache_hits": hits},
    }


def save(conn, summary: dict, cfg: dict) -> None:
    git = git_state()
    config = {
        "embedding_model": cfg["embedding_model"], "ks": list(KS), "retrieve_k": RETRIEVE_K,
        "git_dirty": git["dirty"], "search": "vector only, exact cosine, no filters",
    }  # fmt: skip
    values = (
        summary["label"],
        git["commit"],
        summary["split"],
        Jsonb(config),
        Jsonb(summary["metrics"]),
        Jsonb(summary["per_question"]),
        Jsonb(summary["cost"]),
    )
    conn.execute(
        "INSERT INTO eval_runs (label, git_commit, split, config, metrics, per_question, cost) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        values,
    )
    conn.commit()
    path = RESULTS / f"{summary['label']}.json"
    path.write_text(
        json.dumps({**summary, "git": git, "config": config}, indent=1) + "\n", encoding="utf-8"
    )


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m cta.eval.run_retrieval")
    p.add_argument("--split", choices=("dev", "test"), required=True)
    p.add_argument("--label", required=True)
    p.add_argument("--final", action="store_true", help="allow --split test (step 9 only)")
    args = p.parse_args(argv[1:])
    if error := check_split(args.split, args.final):
        print(error)
        return 2
    if (RESULTS / f"{args.label}.json").exists():
        print(f"refused: eval/results/{args.label}.json already exists; use a new label")
        return 2
    cfg = load_models()
    questions = [q for q in load_questions() if q["split"] == args.split]
    try:
        with connect() as conn:
            summary = run(conn, questions, args.label, args.split, cfg)
            save(conn, summary, cfg)
    except ApiError as e:
        print(f"failed: {e}")
        return 1
    print(f"saved eval_runs row and eval/results/{args.label}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
