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
from pathlib import Path
from statistics import median

from psycopg.types.json import Jsonb

from cta.eval.metrics import KS, average, matched_gold, question_metrics, scorable_gold
from cta.eval.questions import (
    load_questions,
    question_ids_record,
    questions_path,
    select_questions,
)
from cta.index.db import connect
from cta.index.embed import ApiError
from cta.index.rerank import SpendLimit
from cta.index.search import search
from cta.settings import ROOT, load_models, refuse_tracing

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


def latency(values: list[float]) -> dict:
    """Median and p95 (nearest rank) of search times in ms."""
    ordered = sorted(values)
    p95 = ordered[max(0, -(-95 * len(ordered) // 100) - 1)] if ordered else None
    return {"n": len(ordered), "median": median(ordered) if ordered else None, "p95": p95}


def pool_recall(pool: list[dict], gold: list[str]) -> float:
    """Share of the scorable gold sources that appear anywhere in the reranker's pool."""
    found = set().union(*(matched_gold(c, gold) for c in pool)) if pool else set()
    return len(found) / len(gold)


def rerank_summary(outcomes: dict, scored: list[dict], pools: dict, gold: dict) -> dict:
    """Totals over the questions that were reranked: calls, failures, cost, latency, pool recall."""
    cost = sum(o.cost for o in outcomes.values())
    api_ms = [o.api_ms for o in outcomes.values()]
    recalls = {r["id"]: pool_recall(pools[r["id"]], gold[r["id"]]) for r in scored}
    chain = [recalls[r["id"]] for r in scored if "chain" in r["tags"]]
    return {
        "calls": len(outcomes),
        "cache_hits": sum(o.cache_hit for o in outcomes.values()),
        "failed": {i: o.reason for i, o in outcomes.items() if o.failed},
        "cost_usd": cost,
        "prompt_tokens": sum(o.prompt_tokens for o in outcomes.values()),
        "completion_tokens": sum(o.completion_tokens for o in outcomes.values()),
        "api_latency_ms": latency(api_ms),
        "pool_size": median(len(p) for p in pools.values()),
        "pool_recall": sum(recalls.values()) / len(recalls) if recalls else None,
        "pool_recall_chain": sum(chain) / len(chain) if chain else None,
        "pool_recall_by_question": recalls,
    }


def run(
    conn,
    questions: list[dict],
    label: str,
    split: str,
    cfg: dict,
    out=print,
    rerank_budget: float | None = None,
) -> dict:
    retrieved, calls, hits, cost, timing = {}, 0, 0, 0.0, {}
    outcomes, pools, spent = {}, {}, 0.0
    for q in questions:
        allowance = None if rerank_budget is None else rerank_budget - spent
        found = search(conn, q["question"], RETRIEVE_K, cfg=cfg, rerank_limit=allowance)
        if found.rerank:
            outcomes[q["id"]], pools[q["id"]] = found.rerank, found.pool
            spent += found.rerank.cost
        retrieved[q["id"]] = found.results
        timing[q["id"]] = found.retrieval_ms
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
    summary_rerank = None
    if outcomes:
        gold = {q["id"]: scorable_gold(q) for q in questions}
        summary_rerank = rerank_summary(outcomes, scored, pools, gold)
        r = summary_rerank
        lat = r["api_latency_ms"]
        out(
            f"\nrerank {cfg['retrieval']['rerank']}: {r['calls']} calls "
            f"({r['cache_hits']} from cache), "
            f"{len(r['failed'])} failed {sorted(r['failed'])}, cost ${r['cost_usd']:.5f}, "
            f"tokens {r['prompt_tokens']} in / {r['completion_tokens']} out\n"
            f"rerank API latency: median {lat['median']:.0f} ms, p95 {lat['p95']:.0f} ms; "
            f"pool size {r['pool_size']:.0f}; pool recall (scored questions) {r['pool_recall']:.3f}"
            + (
                f", chain row {r['pool_recall_chain']:.3f}"
                if r["pool_recall_chain"] is not None
                else ""
            )
        )
    out(f"\nquery embeddings: {hits} cache hits, {calls} API calls, real cost ${cost:.7f}")
    lat = latency(list(timing.values()))
    out(
        f"search time median {lat['median']:.1f} ms, "
        f"p95 {lat['p95']:.1f} ms (n={lat['n']})"
    )
    ranks = [
        {
            "id": r["id"],
            "type": r["type"],
            "department": r["department"],
            "first_rank": r["first_rank"],
            "tags": r["tags"],
            "retrieval_ms": round(timing[r["id"]], 1),
            "retrieved_ids": [c["source_id"] for c in retrieved[r["id"]]],
            **(
                {
                    "pool_ids": [c["source_id"] for c in pools[r["id"]]],
                    "first_stage_ranks": [c["first_stage_rank"] for c in retrieved[r["id"]]],
                    "rerank_failed": r["id"] in summary_rerank["failed"],
                }
                if r["id"] in pools
                else {}
            ),
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
        "retrieval_latency_ms": latency(list(timing.values())),
        "rerank": summary_rerank,
        **question_ids_record(questions),
    }


def save(conn, summary: dict, cfg: dict) -> None:
    git = git_state()
    config = {
        "embedding_model": cfg["embedding_model"], "ks": list(KS), "retrieve_k": RETRIEVE_K,
        "git_dirty": git["dirty"], "retrieval": cfg["retrieval"], "filters": "none",
        "question_ids": summary["question_ids"], "question_ids_hash": summary["question_ids_hash"],
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
    p.add_argument("--split", choices=("dev", "test", "heldout"), required=True)
    p.add_argument("--questions", type=Path, help="questions file (default: the file of the split)")
    p.add_argument("--label", required=True)
    p.add_argument("--final", action="store_true", help="allow --split test (step 9 only)")
    p.add_argument("--ids", help="comma-separated question ids (within the split)")
    p.add_argument("--tag", help="only questions with this tag, for example calendar")
    p.add_argument(
        "--rerank", choices=("off", "pool_a"), help="override retrieval.rerank"
    )
    p.add_argument(
        "--rerank-budget", type=float, default=0.10,
        help="most the reranker may spend in this run, USD; a call that could pass it is refused",
    )  # fmt: skip
    args = p.parse_args(argv[1:])
    if error := check_split(args.split, args.final):
        print(error)
        return 2
    if (RESULTS / f"{args.label}.json").exists():
        print(f"refused: eval/results/{args.label}.json already exists; use a new label")
        return 2
    try:
        refuse_tracing()
    except RuntimeError as e:
        print(f"refused: {e}")
        return 2
    cfg = load_models()
    if args.rerank:
        cfg["retrieval"]["rerank"] = args.rerank
    try:
        ids = args.ids.split(",") if args.ids else None
        questions = select_questions(
            load_questions(args.questions or questions_path(args.split)), args.split, ids, args.tag
        )
    except ValueError as e:
        print(f"refused: {e}")
        return 2
    try:
        with connect() as conn:
            summary = run(
                conn, questions, args.label, args.split, cfg, rerank_budget=args.rerank_budget
            )
            save(conn, summary, cfg)
    except (ApiError, SpendLimit) as e:
        print(f"failed, nothing saved: {e}")
        return 1
    print(f"saved eval_runs row and eval/results/{args.label}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
