"""Answer every question of a split, judge the answers, and compute the baseline metrics.

    uv run python -m cta.eval.run_answers --split dev --label baseline-dev --dry-run
    uv run python -m cta.eval.run_answers --split dev --label baseline-dev --yes

--dry-run calls no chat model and writes nothing; a real run needs --yes and stops if the estimated
cost is above eval.max_cost_usd. --split test is refused unless --final is also given.

Special gold answers: "ABSTAIN" (no judge: correct if the answer starts with "ABSTAIN:"),
"CLARIFY..."
(no judge: not supported yet), "NO ADVICE..." (the judge only decides whether the answer gives
advice). Questions whose gold sources are all calendar events are judged but reported separately as
not supported yet (the calendar tool is Phase 3).
"""

import argparse
import json
import math
import sys
from datetime import date
from statistics import median
from types import SimpleNamespace

from psycopg.types.json import Jsonb

from cta.answer import Answer, answer, estimate_cost, format_source
from cta.eval.metrics import CALENDAR_ID, average, matched_gold, scorable_gold
from cta.eval.questions import load_questions, question_ids_record, select_questions
from cta.eval.rubric import ADVICE_INSTRUCTIONS, JUDGE_INSTRUCTIONS, RUBRIC_VERSION
from cta.eval.run_retrieval import RESULTS, check_split, git_state, metrics_table, score
from cta.index.chunks import token_counter
from cta.index.db import connect
from cta.index.embed import ApiError, make_client, with_retries
from cta.index.search import search
from cta.redact import redact
from cta.settings import ROOT, cost_usd, load_models, refuse_tracing

JUDGE_ESTIMATE_ANSWER_TOKENS = 150
JUDGE_ESTIMATE_OUTPUT_TOKENS = 150
CORRECTNESS = ("correct", "partial", "incorrect")
FAITHFULNESS = ("yes", "partly", "no")
NOT_SUPPORTED = "not supported yet"
CHAINED = "not supported yet (chained prerequisite)"
# Questions tagged "chain" in eval/questions.jsonl need the prerequisites of the prerequisites,
# which the baseline cannot follow (a prerequisite-chain tool is Phase 3). q22 was checked against
# its dev run; before the tag existed the rule named q20 and q22 in code.


# ---- classification and judging ----


def gold_kind(q: dict) -> str:
    """abstain | clarify | no_advice | calendar_only | normal"""
    gold = q["gold_answer"].strip()
    if gold.startswith("ABSTAIN"):
        return "abstain"
    if gold.startswith("CLARIFY"):
        return "clarify"
    if gold.startswith("NO ADVICE"):
        return "no_advice"
    ids = [g["id"] for g in q["gold_sources"]]
    if ids and all(CALENDAR_ID.match(i) for i in ids):
        return "calendar_only"
    return "normal"


def judge_messages(kind: str, q: dict, ans: Answer) -> list[dict]:
    sources = "\n\n---\n\n".join(format_source(n, c) for n, c in enumerate(ans.sources, 1))
    body = f"Question: {q['question']}\n\nAnswer to grade:\n{ans.text}\n"
    if kind != "no_advice":
        body = (
            f"Question: {q['question']}\n\nGold answer:\n{q['gold_answer']}\n\n"
            f"Answer to grade:\n{ans.text}\n\n"
            f"Numbered sources the assistant was given:\n\n{sources}\n"
        )
    system = ADVICE_INSTRUCTIONS if kind == "no_advice" else JUDGE_INSTRUCTIONS
    return [{"role": "system", "content": system}, {"role": "user", "content": body}]


def parse_verdict(text: str, kind: str) -> dict | None:
    """The judge's JSON as a verdict dict, or None if it is not valid or has a bad value."""
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if kind == "no_advice":
        if data.get("gives_advice") not in ("yes", "no"):
            return None
        return {
            "correctness": "incorrect" if data["gives_advice"] == "yes" else "correct",
            "correctness_reason": str(data.get("reason", "")),
            "faithfulness": None,
            "faithfulness_reason": None,
        }
    if data.get("correctness") not in CORRECTNESS or data.get("faithfulness") not in FAITHFULNESS:
        return None
    keys = ("correctness", "correctness_reason", "faithfulness", "faithfulness_reason")
    return {k: data.get(k) for k in keys}


def judge(kind: str, q: dict, ans: Answer, call) -> tuple[dict, float]:
    """(verdict, judge cost). `call(messages) -> (reply text, cost)`. A reply that is not valid JSON
    is retried once; then the question is recorded as 'judge failed' (never an exception)."""
    messages, cost = judge_messages(kind, q, ans), 0.0
    for _ in range(2):
        try:
            text, spent = call(messages)
        except ApiError:
            break
        cost += spent
        verdict = parse_verdict(text, kind)
        if verdict:
            return {**verdict, "judge_status": "ok"}, cost
    failed = {"correctness": None, "faithfulness": None, "judge_status": "judge failed"}
    return failed | {"correctness_reason": None, "faithfulness_reason": None}, cost


def make_judge_call(cfg: dict, client):
    j = cfg["judge"]

    def call(messages: list[dict]) -> tuple[str, float]:
        response = with_retries(
            lambda: client.chat.completions.create(
                model=cfg["judge_model"],
                messages=messages,
                temperature=j["temperature"],
                reasoning_effort=j["reasoning_effort"],
                max_completion_tokens=j["max_output_tokens"],
                response_format={"type": "json_object"},
            ),
            "judge request",
        )
        u = response.usage
        spent = cost_usd(cfg, cfg["judge_model"], u.prompt_tokens, u.completion_tokens)
        return response.choices[0].message.content or "", spent

    return call


# ---- failure labels ----


def label_failure(
    kind: str, q: dict, ans: Answer, top10: list[dict], verdict: dict
) -> tuple[str, str]:
    """(label, one-line reason) for a question that is not fully correct. Exactly one label, by the
    earliest failing stage (rule v2): not supported yet; abstention error for an ABSTAIN-gold
    question that was answered; retrieval miss if ANY scorable gold source is missing from the top
    10; ranking miss if any is missing from the top 5; abstention error if the model abstained;
    otherwise generation error."""
    if kind in ("clarify", "calendar_only"):
        return (
            NOT_SUPPORTED,
            "calendar-only gold" if kind == "calendar_only" else "CLARIFY question",
        )
    if kind == "abstain":
        return "abstention error", "answered a question that should be refused"
    if "chain" in q.get("tags", []) and not ans.abstained:
        return CHAINED, "needs the prerequisites of the prerequisites (chained prerequisite)"
    gold = scorable_gold(q)
    missing10 = [g for g in gold if not any(g in matched_gold(c, gold) for c in top10)]
    missing5 = [g for g in gold if not any(g in matched_gold(c, gold) for c in top10[:5])]
    if missing10:
        return "retrieval miss", f"not in the top 10: {', '.join(missing10)}"
    if missing5:
        return "ranking miss", f"in the top 10 but not the top 5: {', '.join(missing5)}"
    if ans.abstained:
        return "abstention error", f"abstained ({ans.abstain_reason})"
    return "generation error", verdict.get("correctness_reason") or "answer wrong or partial"


# ---- one question ----


def evaluate_question(q: dict, ans: Answer, top10: list[dict], judge_call) -> dict:
    kind = gold_kind(q)
    cost = 0.0
    if kind == "abstain":
        ok = ans.text.strip().startswith("ABSTAIN:")
        verdict = {
            "correctness": "correct" if ok else "incorrect",
            "faithfulness": None,
            "correctness_reason": "rule: starts with ABSTAIN:" if ok else "rule: did not abstain",
            "faithfulness_reason": None,
            "judge_status": "rule",
        }
    elif kind == "clarify":
        verdict = {
            "correctness": None,
            "faithfulness": None,
            "correctness_reason": None,
            "faithfulness_reason": None,
            "judge_status": "not judged",
        }
    else:
        verdict, cost = judge(kind, q, ans, judge_call)
    done = verdict["correctness"] == "correct"
    label = reason = None
    if not done:
        if verdict["judge_status"] == "judge failed":
            label, reason = "judge failed", "no valid verdict from the judge"
        else:
            label, reason = label_failure(kind, q, ans, top10, verdict)
    gold = scorable_gold(q)
    rerank = getattr(ans.search, "rerank", None)  # None when the reranker was off
    return {
        "id": q["id"],
        "type": q["type"],
        "department": q["department"],
        "gold_kind": kind,
        "tags": q.get("tags", []),
        "retrieved": [
            {"id": c["source_id"], "similarity": round(c["similarity"], 4)} for c in top10
        ],
        "first_gold_rank": next((i for i, c in enumerate(top10, 1) if matched_gold(c, gold)), None),
        "abstained": ans.abstained,
        "abstain_reason": ans.abstain_reason,
        "citations": ans.citations,
        "invalid_citations": ans.invalid_citations,
        **verdict,
        "label": label,
        "label_reason": reason,
        "answer_cost": ans.cost,
        "judge_cost": cost,
        "latency_ms": ans.latency_ms,
        "chat_ms": ans.chat_ms,
        "retrieval_ms": round(ans.search.retrieval_ms, 1)
        if hasattr(ans.search, "retrieval_ms")
        else None,
        "cache_hit": ans.search.cache_hit,
        "rerank_cost": rerank.cost if rerank else 0.0,
        "rerank_ms": round(rerank.ms, 1) if rerank else 0.0,
        "rerank_failed": bool(rerank and rerank.failed),
    }


# ---- aggregation ----


def share(values: list, options: tuple) -> dict:
    n = len(values)
    return {"n": n} | {o: (sum(v == o for v in values) / n if n else None) for o in options}


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def aggregate(records: list[dict]) -> dict:
    """Metrics over all records, plus a separate `chain` block for the questions tagged chain. The
    top-level numbers are unchanged by the tag (the chain questions are inside them as well)."""
    chain = [r for r in records if "chain" in r.get("tags", [])]
    return {**_aggregate(records), "chain": _aggregate(chain) if chain else None}


def chain_retrieval(scored: list[dict]) -> dict | None:
    rows = [r for r in scored if "chain" in r.get("tags", [])]
    return average(rows) if rows else None


def _aggregate(records: list[dict]) -> dict:
    normal = [r for r in records if r["gold_kind"] == "normal"]
    answerable = [r for r in records if r["gold_kind"] in ("normal", "no_advice")]
    abstain_gold = [r for r in records if r["gold_kind"] == "abstain"]
    answered = [r for r in records if not r["abstained"]]
    lat = [r["latency_ms"] for r in records]
    chat = [r["chat_ms"] for r in records if r["chat_ms"]]
    retr = [r["retrieval_ms"] for r in records if r.get("retrieval_ms") is not None]
    return {
        "correctness": share([r["correctness"] for r in normal if r["correctness"]], CORRECTNESS),
        "faithfulness": share(
            [r["faithfulness"] for r in normal if r["faithfulness"]], FAITHFULNESS
        ),
        "no_advice_correct": share(
            [r["correctness"] for r in records if r["gold_kind"] == "no_advice"], CORRECTNESS
        ),
        "abstention_accuracy": {
            "n": len(abstain_gold),
            "share": sum(r["correctness"] == "correct" for r in abstain_gold) / len(abstain_gold)
            if abstain_gold
            else None,
        },
        "wrongly_abstained": {
            "n": len(answerable),
            "share": sum(r["abstained"] for r in answerable) / len(answerable)
            if answerable
            else None,
        },
        "citation_rate": {
            "n": len(answered),
            "share": sum(
                any(c not in r["invalid_citations"] for c in r["citations"]) for r in answered
            )
            / len(answered)
            if answered
            else None,
            "invalid_citations": sum(len(r["invalid_citations"]) for r in records),
        },
        "judge_failed": sum(r["judge_status"] == "judge failed" for r in records),
        "cost": {
            "n": len(records),
            "per_request_usd": sum(r["answer_cost"] + r["judge_cost"] for r in records)
            / len(records),
            "answer_usd": sum(r["answer_cost"] for r in records),
            "judge_usd": sum(r["judge_cost"] for r in records),
        },
        "latency_ms": {
            "n": len(records),
            "total_median": median(lat),
            "total_p95": percentile(lat, 95),
            "chat_n": len(chat),
            "chat_median": median(chat) if chat else None,
            "chat_p95": percentile(chat, 95),
            "retrieval_n": len(retr),
            "retrieval_median": median(retr) if retr else None,
            "retrieval_p95": percentile(retr, 95),
            "query_cache_hits": sum(r["cache_hit"] for r in records),
        },
    }


def label_counts(records: list[dict]) -> dict[str, int]:
    labels = [r["label"] for r in records if r["label"]]
    return {name: labels.count(name) for name in sorted(set(labels))}


# ---- judge check (fixed rule) ----

JUDGE_CHECK_RULE = (
    "Pool: dev questions that went to the judge, in id order. (1) Up to 2 with faithfulness "
    "partly or "
    "no. (2) Then questions with correctness partial or incorrect, in id order, until 4 are chosen "
    "in total. (3) Then questions with correctness correct, in id order, until 8. (4) If still "
    "short, "
    "the remaining judged questions in id order."
)


def pick_judge_check(records: list[dict], n: int = 8) -> list[str]:
    pool = sorted((r for r in records if r["judge_status"] == "ok"), key=lambda r: r["id"])
    chosen: list[str] = []

    def add(rows, limit):
        for r in rows:
            if r["id"] not in chosen and len(chosen) < limit:
                chosen.append(r["id"])

    add([r for r in pool if r["faithfulness"] in ("partly", "no")], 2)
    add([r for r in pool if r["correctness"] in ("partial", "incorrect")], 4)
    add([r for r in pool if r["correctness"] == "correct"], n)
    add(pool, n)
    return sorted(chosen)


def judge_check_markdown(records: list[dict], questions: dict, answers: dict, label: str) -> str:
    chosen = pick_judge_check(records)
    out = [
        f"# Judge check for run `{label}`",
        "",
        f"Selection rule (fixed before the run): {JUDGE_CHECK_RULE}",
        "",
    ]
    out.append(
        "For each item, write your own verdict on the answer (correct / partial / incorrect, "
        "faithful yes / partly / no) and whether you agree with the judge.\n"
    )
    by_id = {r["id"]: r for r in records}
    for qid in chosen:
        r, q = by_id[qid], questions[qid]
        out += [
            f"## {qid} ({q['type']})",
            "",
            f"**Question:** {q['question']}",
            "",
            f"**Gold answer:** {q['gold_answer']}",
            "",
            f"**Model's answer:** {answers[qid]}",
            "",
            f"**Judge, correctness:** {r['correctness']}: {r['correctness_reason']}",
            "",
            f"**Judge, faithfulness:** {r['faithfulness']}: {r['faithfulness_reason']}",
            "",
            "**My verdict:** ",
            "",
        ]
    return "\n".join(out) + "\n"


# ---- printing ----


def fmt_share(d: dict, options: tuple) -> str:
    if not d["n"]:
        return "n=0"
    return f"n={d['n']}: " + ", ".join(f"{o} {d[o]:.2f}" for o in options)


def print_report(
    records: list[dict],
    agg: dict,
    retrieval: dict,
    excluded: list[str],
    out=print,
    retrieval_chain: dict | None = None,
) -> None:
    out(f"retrieval, scored questions n={retrieval['n']} (excluded: {', '.join(excluded)})")
    rows = {"all": retrieval} | ({"chain (tagged)": retrieval_chain} if retrieval_chain else {})
    out(metrics_table(rows))
    out("\nAnswers (small groups: read n before the numbers)")
    out(f"  correctness, normal gold   {fmt_share(agg['correctness'], CORRECTNESS)}")
    out(f"  faithfulness, normal gold  {fmt_share(agg['faithfulness'], FAITHFULNESS)}")
    out(
        f"  NO ADVICE gold (judge: gives no advice)  "
        f"{fmt_share(agg['no_advice_correct'], CORRECTNESS)}"
    )
    a, w, c = agg["abstention_accuracy"], agg["wrongly_abstained"], agg["citation_rate"]
    out(f"  abstention accuracy (ABSTAIN gold abstained)  n={a['n']}: {a['share']}")
    out(f"  wrongly abstained (answerable questions)      n={w['n']}: {w['share']}")
    out(
        f"  citation rate (answers with a valid [n])      n={c['n']}: {c['share']}; "
        f"invalid citations: {c['invalid_citations']}"
    )
    out(f"  judge failed: {agg['judge_failed']}")
    chain = agg.get("chain")
    if chain:
        out(
            f"  chain-tagged questions (also inside the numbers above): correctness "
            f"{fmt_share(chain['correctness'], CORRECTNESS)}; faithfulness "
            f"{fmt_share(chain['faithfulness'], FAITHFULNESS)}; "
            f"wrongly abstained n={chain['wrongly_abstained']['n']}: "
            f"{chain['wrongly_abstained']['share']}"
        )
    k, lat = agg["cost"], agg["latency_ms"]
    out(
        f"\nCost, n={k['n']} requests: ${k['per_request_usd']:.6f} per request "
        f"(answers ${k['answer_usd']:.5f} + judge ${k['judge_usd']:.5f})"
    )
    out(
        f"Latency ms, total n={lat['n']}: median {lat['total_median']}, p95 {lat['total_p95']}; "
        f"chat call alone n={lat['chat_n']}: median {lat['chat_median']}, p95 {lat['chat_p95']}; "
        f"search alone n={lat.get('retrieval_n', 0)}: median {lat.get('retrieval_median')} ms, "
        f"p95 {lat.get('retrieval_p95')} ms; "
        f"query-embedding cache hits {lat['query_cache_hits']}/{lat['n']} "
        "(a hit hides embedding time)"
    )
    ns = [
        r
        for r in records
        if (r["label"] or "").startswith(NOT_SUPPORTED)
        or r["gold_kind"] in ("clarify", "calendar_only")
    ]
    out(f"\nNot supported yet (reported separately, n={len(ns)}):")
    for r in ns:
        out(
            f"  {r['id']} {r['gold_kind']}: correctness {r['correctness']}, "
            f"abstained {r['abstained']}"
        )
    bad = [r for r in records if r["label"]]
    out(f"\nFailure labels (n={len(bad)} not fully correct): {label_counts(records)}")
    out(f"{'id':5}{'type':16}{'label':20}reason")
    for r in bad:
        out(f"{r['id']:5}{r['type']:16}{r['label']:20}{(r['label_reason'] or '')[:110]}")


# ---- the run ----


def estimate_run(conn, questions: list[dict], cfg: dict, today: date, count) -> tuple[float, list]:
    """(estimated dollars for answers + judge, per-question lines). Calls no chat model."""
    total, lines = 0.0, []
    # The estimate never calls the reranker (a paid call that would fill the run's own score
    # cache): it counts the prompt of the first-stage top 5 and adds a flat reranker allowance.
    plain = {**cfg, "retrieval": {**cfg["retrieval"], "rerank": "off"}}
    extra = RERANK_ESTIMATE_PER_QUESTION if cfg["retrieval"]["rerank"] != "off" else 0.0
    for q in questions:
        a = answer(conn, q["question"], today, cfg=plain, dry_run=True, log=False)
        chat = estimate_cost(a.prompt, cfg, count) if a.prompt else 0.0
        kind = gold_kind(q)
        judge_cost = 0.0
        if kind not in ("abstain", "clarify"):
            msgs = judge_messages(kind, q, a)
            tokens = sum(count(m["content"]) for m in msgs) + JUDGE_ESTIMATE_ANSWER_TOKENS
            judge_cost = cost_usd(cfg, cfg["judge_model"], tokens, JUDGE_ESTIMATE_OUTPUT_TOKENS)
        total += chat + judge_cost + a.search.cost + extra
        lines.append(
            f"{q['id']:5}{kind:14} chat ${chat:.5f}  judge ${judge_cost:.5f}  "
            f"{'(threshold abstain, no chat call)' if not a.prompt else ''}"
        )
    return total, lines


def start_run(conn, label: str, split: str, cfg: dict, extra: dict | None = None) -> int:
    git = git_state()
    config = {
        "rubric_version": RUBRIC_VERSION,
        "retrieval": cfg["retrieval"],
        **(extra or {}),
        "chat_model": cfg["chat_model"],
        "judge_model": cfg["judge_model"],
        "embedding_model": cfg["embedding_model"],
        "answer": cfg["answer"],
        "judge": cfg["judge"],
        "today": cfg["eval"]["today"],
        "git_dirty": git["dirty"],
        "status": "running",
    }
    row = conn.execute(
        "INSERT INTO eval_runs (label, git_commit, split, config) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (label, git["commit"], split, Jsonb(config)),
    ).fetchone()
    conn.commit()
    return row[0]


def finish_run(
    conn, run_id: int, config_update: dict, metrics: dict, per_q: list, cost: dict
) -> None:
    conn.execute(
        "UPDATE eval_runs SET config = config || %s, metrics = %s, per_question = %s, cost = %s "
        "WHERE id = %s",
        (Jsonb(config_update), Jsonb(metrics), Jsonb(per_q), Jsonb(cost), run_id),
    )
    conn.commit()


class BudgetStop(Exception):
    """The next question could take the step past its spend allowance."""


# Labels of the runs that count against the step 3b allowance (docs/decisions.md).
STEP_3B_LABELS = (
    "baseline-dev-60-v3", "off-run2", "off-run3", "on-run1", "on-run2", "on-run3", "judge-repeat",
)  # fmt: skip
# Rough cost of the reranker calls per question, used only in the estimate (measured in experiment 3
# at about $0.0005 per question; doubled here).
RERANK_ESTIMATE_PER_QUESTION = 0.001


def spent_so_far(conn, labels: tuple[str, ...] = STEP_3B_LABELS) -> float:
    """Dollars already spent by the finished runs with these labels (eval_runs.cost.usd)."""
    rows = conn.execute(
        "SELECT coalesce(sum((cost->>'usd')::float), 0) FROM eval_runs WHERE label = ANY(%s)",
        (list(labels),),
    )
    return rows.fetchone()[0]


def run(
    conn,
    questions,
    label,
    split,
    cfg,
    client_factory=make_client,
    out=print,
    judge_check=False,
    budget: float | None = None,
) -> dict:
    today = date.fromisoformat(cfg["eval"]["today"])
    run_id = start_run(conn, label, split, cfg, question_ids_record(questions))
    judge_call = make_judge_call(cfg, client_factory())
    qs = {q["id"]: q for q in questions}
    records, top10s, texts = [], {}, {}
    spent = priciest = 0.0
    for q in questions:
        if budget is not None and spent + priciest > budget:
            conn.execute(
                "UPDATE eval_runs SET config = config || %s WHERE id = %s",
                (Jsonb({"status": "stopped: budget"}), run_id),
            )
            conn.commit()
            raise BudgetStop(
                f"stopped before {q['id']}: spent ${spent:.4f} of the ${budget:.4f} allowance and "
                f"the dearest question so far cost ${priciest:.4f}; nothing saved"
            )
        ans = answer(
            conn, q["question"], today, cfg=cfg, client_factory=client_factory, run_id=run_id
        )
        top10 = search(conn, q["question"], 10, cfg=cfg, client_factory=client_factory).results
        top10s[q["id"]], texts[q["id"]] = top10, ans.text
        records.append(evaluate_question(q, ans, top10, judge_call))
        priciest = max(priciest, records[-1]["answer_cost"] + records[-1]["judge_cost"])
        spent += records[-1]["answer_cost"] + records[-1]["judge_cost"]
        out(
            f"  {q['id']} done: correctness {records[-1]['correctness']}, "
            f"label {records[-1]['label']}"
        )
    scored, excluded = score(questions, top10s)
    retrieval = average(scored)
    retrieval_chain = chain_retrieval(scored)
    agg = aggregate(records)
    print_report(records, agg, retrieval, excluded, out, retrieval_chain)
    summary = {
        "label": label,
        "split": split,
        "retrieval": retrieval,
        "retrieval_chain": retrieval_chain,
        "excluded_from_retrieval": excluded,
        "answers": agg,
        "failure_labels": label_counts(records),
        "per_question": records,
        **question_ids_record(questions),
    }
    git = git_state()
    cost = {"usd": agg["cost"]["answer_usd"] + agg["cost"]["judge_usd"], **agg["cost"]}
    finish_run(
        conn,
        run_id,
        {"status": "done"},
        {"retrieval": retrieval, "retrieval_chain": retrieval_chain, **agg},
        records,
        cost,
    )
    path = RESULTS / f"{label}.json"
    path.write_text(json.dumps({**summary, "git": git}, indent=1) + "\n", encoding="utf-8")
    if judge_check:  # dev only, and never over an existing file (it holds the owner's verdicts)
        path = ROOT / "docs" / "judge-check.md"
        path.write_text(judge_check_markdown(records, qs, texts, label), encoding="utf-8")
    return summary


# ---- re-judging a stored run (no answer calls, no embedding calls) ----


def no_api() -> None:
    raise ApiError("a re-judge must not call the embedding or answer API")


RERANK_CACHE_DIR = ROOT / "data" / "cache"


def rerank_cache_file(label: str) -> str:
    """The reranker's score cache of the run with this label (one file per run, not committed)."""
    return str(RERANK_CACHE_DIR / f"rerank-{label}.json")


def stored_config(cfg: dict, stored: dict, label: str) -> dict:
    """cfg with the reranker set as the stored run had it (a run made before the switch existed was
    off), so that a re-judge shows the judge the sources the answerer saw. An ON run is read back
    from its own score cache, never from the API."""
    mode = (stored.get("retrieval") or {}).get("rerank", "off")
    pinned = {**cfg, "retrieval": {**cfg["retrieval"], "rerank": mode}}
    if mode != "off":
        pinned["rerank"] = {**cfg["rerank"], "cache_path": rerank_cache_file(label)}
    return pinned


def find_run(conn, label: str) -> tuple[int, str, dict]:
    """(id, split, config) of the newest eval run with this label."""
    row = conn.execute(
        "SELECT id, split, config FROM eval_runs WHERE label = %s ORDER BY id DESC LIMIT 1",
        (label,),
    ).fetchone()
    if row is None:
        raise ValueError(f"no eval run labelled {label}")
    return row


def load_stored(conn, old_label: str, cfg: dict):
    """(questions, answers, top10s, old records) of a finished run, rebuilt from request_logs, the
    chunks table and the run's results file. Raises if the sources the answerer saw have changed."""
    old = json.loads((RESULTS / f"{old_label}.json").read_text(encoding="utf-8"))
    log_label = old.get("rejudge_of") or old_label  # a re-judge reuses the original run's logs
    run_id, split, stored = find_run(conn, log_label)
    cfg = stored_config(cfg, stored, log_label)
    old_records = {r["id"]: r for r in old["per_question"]}
    logs = {
        r[0]: r[1:]
        for r in conn.execute(
            "SELECT question, answer, abstained, abstain_reason, retrieved FROM request_logs "
            "WHERE run_id = %s",
            (run_id,),
        )
    }
    # only the questions this run answered (the split may have grown since)
    questions = [q for q in load_questions() if q["split"] == split and q["id"] in old_records]
    answers, top10s = {}, {}
    for q in questions:
        text, abstained, reason, retrieved = logs[redact(q["question"])]
        top10 = search(conn, q["question"], 10, cfg=cfg, client_factory=no_api).results
        shown = [c["id"] for c in top10[:5]]
        if shown != [r["id"] for r in retrieved]:
            raise ValueError(f"{q['id']}: the sources shown in the original run have changed")
        old_r = old_records[q["id"]]
        a = Answer(
            text, abstained, reason, top10[:5], old_r["citations"], old_r["invalid_citations"]
        )
        a.search = SimpleNamespace(cache_hit=old_r["cache_hit"], cost=0.0, total_cost=0.0)
        a.chat_cost, a.latency_ms, a.chat_ms = (
            old_r["answer_cost"],
            old_r["latency_ms"],
            old_r["chat_ms"],
        )
        answers[q["id"]], top10s[q["id"]] = a, top10
    return questions, answers, top10s, old


def estimate_rejudge(questions, answers, cfg, count) -> float:
    total = 0.0
    for q in questions:
        kind = gold_kind(q)
        if kind in ("abstain", "clarify"):
            continue
        tokens = sum(count(m["content"]) for m in judge_messages(kind, q, answers[q["id"]]))
        total += cost_usd(cfg, cfg["judge_model"], tokens, JUDGE_ESTIMATE_OUTPUT_TOKENS)
    return total


def verdict_changes(old_records: list[dict], new_records: list[dict]) -> list[str]:
    old = {r["id"]: r for r in old_records}
    lines = []
    for r in new_records:
        o = old[r["id"]]
        if (o["correctness"], o["faithfulness"]) != (r["correctness"], r["faithfulness"]):
            lines.append(
                f"{r['id']}: correctness {o['correctness']} -> {r['correctness']}, faithfulness "
                f"{o['faithfulness']} -> {r['faithfulness']}\n    new correctness: "
                f"{r['correctness_reason']}\n    new faithfulness: {r['faithfulness_reason']}"
            )
    return lines


def rejudge(conn, old_label: str, label: str, cfg: dict, out=print) -> dict:
    questions, answers, top10s, old = load_stored(conn, old_label, cfg)
    split = old["split"]
    markers = ("[EMAIL]", "[PHONE]", "[SSN]", "[ID]")
    redacted = [q["id"] for q in questions if any(m in answers[q["id"]].text for m in markers)]
    log_label = old.get("rejudge_of") or old_label
    cfg = stored_config(cfg, find_run(conn, log_label)[2], log_label)
    run_id = start_run(
        conn, label, split, cfg, {"rejudge_of": old_label} | question_ids_record(questions)
    )
    judge_call = make_judge_call(cfg, make_client())
    records = [
        evaluate_question(q, answers[q["id"]], top10s[q["id"]], judge_call) for q in questions
    ]
    scored, excluded = score(questions, top10s)
    retrieval, agg = average(scored), aggregate(records)
    retrieval_chain = chain_retrieval(scored)
    out(f"re-judge of {old_label} with rubric v{RUBRIC_VERSION}; stored answers containing a "
        f"redaction marker: {redacted or 'none'}")  # fmt: skip
    print_report(records, agg, retrieval, excluded, out, retrieval_chain)
    out(f"\nbefore ({old_label}) vs after (rubric v{RUBRIC_VERSION})")
    for name, options in (("correctness", CORRECTNESS), ("faithfulness", FAITHFULNESS)):
        out(f"  {name:13} before {fmt_share(old['answers'][name], options)}")
        out(f"  {'':13} after  {fmt_share(agg[name], options)}")
    changes = verdict_changes(old["per_question"], records)
    out(f"\nVerdicts that changed ({len(changes)}):")
    for line in changes:
        out("  " + line)
    old_labels = {r["id"]: r["label"] for r in old["per_question"]}
    out("\nFailure labels, old rule/rubric -> new")
    for r in records:
        if r["label"] or old_labels[r["id"]]:
            out(f"  {r['id']}: {old_labels[r['id']]} -> {r['label']}")
    cost = {"usd": agg["cost"]["judge_usd"], "judge_usd": agg["cost"]["judge_usd"]}
    summary = {
        "label": label,
        "split": split,
        "rejudge_of": old_label,
        "rubric_version": RUBRIC_VERSION,
        "retrieval": retrieval,
        "retrieval_chain": retrieval_chain,
        "answers": agg,
        "failure_labels": label_counts(records),
        "per_question": records,
        "git": git_state(),
        **question_ids_record(questions),
    }
    finish_run(
        conn,
        run_id,
        {"status": "done"},
        {"retrieval": retrieval, "retrieval_chain": retrieval_chain, **agg},
        records,
        cost,
    )
    (RESULTS / f"{label}.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    return summary


def main_rejudge(args, cfg: dict) -> int:
    try:
        with connect() as conn:
            questions, answers, _, old = load_stored(conn, args.rejudge, cfg)
            if old["split"] == "test" and not args.final:
                print("refused: re-judging a test run needs --final")
                return 2
            total = estimate_rejudge(questions, answers, cfg, token_counter())
            cap = cfg["eval"]["max_cost_usd"]
            print(
                f"re-judge {args.rejudge} ({old['split']}, {len(questions)} questions): "
                f"estimated ${total:.5f}, no answer or embedding calls (cap ${cap})"
            )
            if total > cap:
                print("refused: estimate is above eval.max_cost_usd")
                return 1
            if args.budget is not None and total > args.budget - spent_so_far(conn):
                print("refused: estimate is above the remaining step allowance")
                return 1
            if args.dry_run or not args.yes:
                print("dry run: nothing called" if args.dry_run else "nothing was run; add --yes")
                return 0
            rejudge(conn, args.rejudge, args.label, cfg)
    except (ApiError, ValueError) as e:
        print(f"failed: {e}")
        return 1
    return 0


def relabel(conn, label: str, cfg: dict) -> dict:
    """Recompute the failure labels of a finished run from its stored verdicts and sources. No
    judge, answer or embedding call. Rewrites the results file and the eval_runs row."""
    questions, answers, top10s, old = load_stored(conn, label, cfg)
    by_id = {r["id"]: r for r in old["per_question"]}
    changed = []
    for q in questions:
        r = by_id[q["id"]]
        new_label = new_reason = None
        if r["correctness"] != "correct" and r["judge_status"] != "judge failed":
            new_label, new_reason = label_failure(
                r["gold_kind"], q, answers[q["id"]], top10s[q["id"]], r
            )
        elif r["judge_status"] == "judge failed":
            new_label, new_reason = r["label"], r["label_reason"]
        if new_label != r["label"]:
            changed.append((q["id"], r["label"], new_label))
        r["label"], r["label_reason"] = new_label, new_reason
    old["failure_labels"] = label_counts(old["per_question"])
    (RESULTS / f"{label}.json").write_text(json.dumps(old, indent=1) + "\n", encoding="utf-8")
    conn.execute(
        "UPDATE eval_runs SET per_question = %s, config = config || %s "
        "WHERE id = (SELECT max(id) FROM eval_runs WHERE label = %s)",
        (Jsonb(old["per_question"]), Jsonb({"relabelled": "chained-prerequisite rule"}), label),
    )
    conn.commit()
    return {"changed": changed, "labels": old["failure_labels"]}


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m cta.eval.run_answers")
    p.add_argument("--split", choices=("dev", "test"))
    p.add_argument("--label")
    p.add_argument("--final", action="store_true", help="allow --split test (part B only)")
    p.add_argument("--rejudge", metavar="OLD_LABEL", help="re-judge a stored run, no answer calls")
    p.add_argument("--relabel", metavar="LABEL", help="recompute failure labels, no API call")
    p.add_argument(
        "--mode", choices=("vector", "hybrid", "hybrid_bm25"), help="override retrieval.mode"
    )
    p.add_argument("--dept-filter", choices=("off", "on"), help="override retrieval.dept_filter")
    p.add_argument("--ids", help="comma-separated question ids (within the split)")
    p.add_argument("--tag", help="only questions with this tag, for example calendar")
    p.add_argument(
        "--rerank", choices=("off", "pool_a", "pool_b"), help="override retrieval.rerank"
    )
    p.add_argument(
        "--budget", type=float, metavar="USD",
        help="total allowance of a multi-run step (docs/decisions.md): what the step's earlier "
        "runs cost is subtracted; the run refuses to start or stops by itself if it would not fit",
    )  # fmt: skip
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true")
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
    if args.mode:
        cfg["retrieval"]["mode"] = args.mode
    if args.dept_filter:
        cfg["retrieval"]["dept_filter"] = args.dept_filter
    if args.rerank:
        cfg["retrieval"]["rerank"] = args.rerank
    if args.relabel:
        with connect() as conn:
            print(relabel(conn, args.relabel, cfg))
        return 0
    if not args.split or not args.label:
        print("--split and --label are required")
        return 2
    if args.rejudge:
        return main_rejudge(args, cfg)
    try:
        ids = args.ids.split(",") if args.ids else None
        questions = select_questions(load_questions(), args.split, ids, args.tag)
    except ValueError as e:
        print(f"refused: {e}")
        return 2
    today = date.fromisoformat(cfg["eval"]["today"])
    if cfg["retrieval"]["rerank"] != "off":  # each run makes its own reranker calls
        cfg["rerank"] = {**cfg["rerank"], "cache_path": rerank_cache_file(args.label)}
    try:
        with connect() as conn:
            total, lines = estimate_run(conn, questions, cfg, today, token_counter())
            print("\n".join(lines))
            cap = cfg["eval"]["max_cost_usd"]
            print(f"\n{len(questions)} questions, estimated total ${total:.5f} (cap ${cap})")
            if total > cap:
                print("refused: estimate is above eval.max_cost_usd")
                return 1
            remaining = None
            if args.budget is not None:
                remaining = args.budget - spent_so_far(conn)
                print(f"step allowance ${args.budget:.2f}, remaining ${remaining:.4f}")
                if total > remaining:
                    print("refused: estimate is above the remaining step allowance")
                    return 1
            if args.dry_run:
                print("dry run: no chat or judge call, nothing written")
                return 0
            if not args.yes:
                print("nothing was run; add --yes to run")
                return 0
            check_file = ROOT / "docs" / "judge-check.md"
            run(
                conn,
                questions,
                args.label,
                args.split,
                cfg,
                judge_check=args.split == "dev" and not check_file.exists(),
                budget=remaining,
            )
    except BudgetStop as e:
        print(e)
        return 1
    except ApiError as e:
        print(f"failed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
