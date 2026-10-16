"""A second judge pass over the stored answers of a router run (final milestone, part 2).

    uv run python -m cta.eval.rejudge_stored final-run --dry-run     # estimate, nothing called
    uv run python -m cta.eval.rejudge_stored final-run --yes         # the paid judge pass

`run_answers --rejudge` rebuilds the shown sources by searching again, which fails for a run made
with the router (calendar rows and chain courses are not search results). This module judges the
SAME answers with the SAME judge model, rubric, prompt and settings (it reuses `judge`,
`judge_messages` and `make_judge_call` from run_answers), and rebuilds the sources from stored data
only: the chunk ids in request_logs plus the chunks table (retrieve route), or the deterministic
calendar renderer and chain walk (no model, no search, no embedding, no rerank). A rebuilt source
list is used only if it reproduces the stored answer text exactly (and the stored source ids);
otherwise the question is skipped and the reason is printed. The answer model is never called and
nothing is written to the database.
"""

import argparse
import json
import sys
from datetime import date
from types import SimpleNamespace

from cta.eval.questions import load_questions
from cta.eval.run_answers import (
    JUDGE_ESTIMATE_OUTPUT_TOKENS,
    gold_kind,
    judge,
    judge_messages,
    make_judge_call,
)
from cta.eval.run_retrieval import RESULTS
from cta.graph import chain as chains
from cta.graph import chain_render, render
from cta.graph.build import load_events
from cta.index.chunks import token_counter
from cta.index.db import connect
from cta.index.embed import make_client
from cta.index.search import RESULT_COLUMNS
from cta.redact import redact
from cta.settings import cost_usd, load_models, refuse_tracing


class CannotRebuild(Exception):
    """The shown sources cannot be reproduced exactly from stored data."""


def same_text(rebuilt: str, stored: str) -> bool:
    """The log stores the redacted answer, so compare after the same redaction."""
    return redact(rebuilt).strip() == stored.strip()


def chunk_sources(conn, ids: list[str]) -> list[dict]:
    """The chunk dicts of the retrieve route, in the logged order (the shown top 5)."""
    rows = conn.execute(
        f"SELECT {', '.join(RESULT_COLUMNS)} FROM chunks WHERE id = ANY(%s)", (ids,)
    ).fetchall()
    by_id = {r[0]: dict(zip(RESULT_COLUMNS, r, strict=True)) for r in rows}
    if set(by_id) != set(ids):
        raise CannotRebuild(f"chunks missing from the table: {sorted(set(ids) - set(by_id))}")
    return [by_id[i] for i in ids]


def calendar_sources(row_ids: list[str], answer: str, events: list[dict]) -> list[dict]:
    """Render the logged rows again with the code that wrote the answer; the text must match."""
    by_id = {e["id"]: e for e in events}
    if not row_ids or any(i not in by_id for i in row_ids):
        raise CannotRebuild("calendar rows not found in the calendar data")
    rows = [by_id[i] for i in row_ids]
    for assumed in (None, *sorted({r["term"] for r in rows})):
        rendered = render.render_rows(rows, render.registrar_contact(), assumed)
        if same_text(rendered.text, answer):
            return rendered.sources
    raise CannotRebuild("the re-rendered calendar answer differs from the stored answer")


def chain_sources(info: dict, answer: str, stored_ids: list[str]) -> list[dict]:
    """Walk the chain again (plain code) and render it; the text and source ids must match."""
    records = chains.load_records()
    if info.get("extraction") == "codes":
        result = chains.combined_chain(info["detail"])
    else:
        result = chains.prerequisite_chain.invoke({"course_code": info["code"]})
    sources = chains.sources_of(result, records)
    if [s["id"] for s in sources] != stored_ids:
        raise CannotRebuild("the re-walked chain has other courses than the stored sources")
    if not same_text(chain_render.render(result, records), answer):
        raise CannotRebuild("the re-rendered chain answer differs from the stored answer")
    return sources


def rebuild(conn, row: dict, events: list[dict]) -> list[dict]:
    """The sources the judge saw in the original run, or CannotRebuild."""
    route, ids = row["route"], row["sources_shown"]
    if route == "advice":
        return []  # the NO ADVICE judge sees the answer text only
    if route == "calendar":
        return calendar_sources(ids, row["answer"], events)
    if route == "chain":
        return chain_sources(row["router"]["chain"], row["answer"], ids)
    if route == "other":
        return chunk_sources(conn, ids)
    raise CannotRebuild(f"route {route} is not handled")


def load_rows(conn, label: str, pass1: dict) -> list[dict]:
    """The judged questions of the run (judge_status ok) with their stored log rows."""
    run_id = conn.execute("SELECT max(id) FROM eval_runs WHERE label = %s", (label,)).fetchone()[0]
    logs = {
        r[0]: r[1:]
        for r in conn.execute(
            "SELECT question, route, answer, retrieved, router FROM request_logs WHERE run_id = %s",
            (run_id,),
        )
    }
    questions = {q["id"]: q for q in load_questions() if q["split"] == pass1["split"]}
    rows = []
    for rec in pass1["per_question"]:
        if rec["judge_status"] != "ok":
            continue
        route, answer, retrieved, router = logs[redact(questions[rec["id"]]["question"])]
        rows.append({
            "id": rec["id"], "q": questions[rec["id"]], "route": route, "answer": answer,
            "sources_shown": [c["id"] for c in retrieved or []], "router": router or {},
            "pass1": rec,
        })  # fmt: skip
    return rows


def judge_rows(conn, rows: list[dict], events: list[dict], call, estimate_only=None) -> tuple:
    """(results, skipped). With estimate_only(messages) -> cost nothing is judged."""
    results, skipped, total = [], [], 0.0
    for row in rows:
        try:
            sources = rebuild(conn, row, events)
        except CannotRebuild as e:
            skipped.append({"id": row["id"], "reason": str(e)})
            continue
        ans = SimpleNamespace(text=row["answer"], sources=sources)
        kind = gold_kind(row["q"])
        if estimate_only:
            total += estimate_only(judge_messages(kind, row["q"], ans), kind)
            continue
        verdict, cost = judge(kind, row["q"], ans, call)
        p1 = row["pass1"]
        results.append({
            "id": row["id"], "gold_kind": kind, "route": row["route"],
            "pass1": {k: p1[k] for k in ("correctness", "faithfulness")},
            "pass2": {k: verdict[k] for k in ("correctness", "faithfulness")},
            "pass2_correctness_reason": verdict["correctness_reason"],
            "pass2_faithfulness_reason": verdict["faithfulness_reason"],
            "pass2_status": verdict["judge_status"], "judge_cost": cost,
        })  # fmt: skip
    return (total if estimate_only else results), skipped


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m cta.eval.rejudge_stored")
    p.add_argument("label")
    p.add_argument("--out", help="results label to write (default <label>-pass2)")
    p.add_argument("--max-usd", type=float, default=0.20, help="refuse above this estimate")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true")
    args = p.parse_args(argv[1:])
    refuse_tracing()
    out_path = RESULTS / f"{args.out or args.label + '-pass2'}.json"
    if out_path.exists():
        print(f"refused: {out_path.name} already exists")
        return 2
    cfg = load_models()
    pass1 = json.loads((RESULTS / f"{args.label}.json").read_text(encoding="utf-8"))
    count = token_counter()

    def estimate(messages, kind):
        tokens = sum(count(m["content"]) for m in messages)
        return cost_usd(cfg, cfg["judge_model"], tokens, JUDGE_ESTIMATE_OUTPUT_TOKENS)

    with connect() as conn:
        rows, events = load_rows(conn, args.label, pass1), load_events()
        total, skipped = judge_rows(conn, rows, events, None, estimate_only=estimate)
        print(f"{len(rows) - len(skipped)} of {len(rows)} judged questions rebuildable, "
              f"estimated judge cost ${total:.4f} (stop above ${args.max_usd})")  # fmt: skip
        for s in skipped:
            print(f"  skipped {s['id']}: {s['reason']}")
        if total > args.max_usd:
            print("refused: estimate is above the limit")
            return 1
        if args.dry_run or not args.yes:
            print("dry run: nothing called" if args.dry_run else "nothing was run; add --yes")
            return 0
        call = make_judge_call(cfg, make_client())
        results, skipped = judge_rows(conn, rows, events, call)
    record = {
        "label": args.out or args.label + "-pass2", "pass2_of": args.label,
        "judge_model": cfg["judge_model"], "judge_settings": cfg["judge"],
        "run_date": date.today().isoformat(), "judged": len(results), "skipped": skipped,
        "judge_cost_usd": round(sum(r["judge_cost"] for r in results), 6), "per_question": results,
    }  # fmt: skip
    out_path.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out_path.name}: {len(results)} judged, cost ${record['judge_cost_usd']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
