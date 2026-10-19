# ruff: noqa: E501  (long report strings)
"""Report on the router runs of step 4a (no network; reads results files and request_logs).

    uv run python -m cta.eval.router_report --router router-run1 router-run2 router-run3 \\
        --before on-run1 on-run2 on-run3 --new8 before-new8

Prints, for the pre-registered keep rule (docs/experiments.md, step 4a): the calendar-only questions
per run (returned rows against gold rows), wrong dates stated, fall-through and misroutes both ways,
classifier accuracy, rule (c) against the stored 3b arm-ON runs on the common questions, rule (d),
latency by component, cost by component, and three example calendar answers in full.
"""

import argparse
import json
import sys
from statistics import mean

from cta.eval import answer_compare as ac
from cta.eval.questions import load_questions
from cta.eval.run_answers import gold_kind, percentile
from cta.eval.run_retrieval import RESULTS
from cta.graph import terms
from cta.graph.build import load_events

NEW8 = ("q61", "q63", "q64", "q65", "q67", "q68", "q71", "q75")
ABSTAIN_CHECK = ("q27", "q28", "q34")  # rule (d), where present
CALENDAR_ROUTES = ("calendar", "calendar_fallthrough", "abstain")


def load(label: str) -> dict:
    return json.loads((RESULTS / f"{label}.json").read_text(encoding="utf-8"))


def gold_intent(q: dict, events: list[dict], today) -> str:
    """calendar = calendar-only gold, or a gold ABSTAIN question that names a term without a
    calendar; everything else = other (docs/experiments.md, step 4a)."""
    kind = gold_kind(q)
    if kind == "calendar_only":
        return "calendar"
    if (
        kind == "abstain"
        and terms.resolve_term(q["question"], today, events).status == "unsupported"
    ):
        return "calendar"
    return "other"


def calendar_rows(run: dict, ids: list[str]) -> list[dict]:
    by_id = {r["id"]: r for r in run["per_question"]}
    return [by_id[i] for i in ids if i in by_id]


def calendar_summary(run: dict, ids: list[str], version: int | None = None) -> dict:
    """Counts over the calendar-only questions. `version` 1 or 2 reads the scoring recorded for that
    version (every calendar-only record stores both); None reads the run's own verdict."""
    rows = calendar_rows(run, ids)
    if version:
        # runs made before both versions were recorded (4a, before-new8) keep their own verdict: it
        # is the same under v2 for them, because none returned a row outside the old gold
        rows = [
            r | {"correctness": r[k]["correctness"], "label": r[k]["label"]}
            if (k := f"calendar_v{version}") in r
            else r
            for r in rows
        ]
    grades = [r["correctness"] for r in rows]
    return {
        "n": len(rows),
        "correct": grades.count("correct"),
        "partial": grades.count("partial"),
        "incorrect": grades.count("incorrect"),
        "wrong_dates": sum(1 for r in rows if r["label"] == "calendar wrong row"),
        "labels": {
            k: [r["label"] for r in rows].count(k)
            for k in sorted({r["label"] for r in rows if r["label"]})
        },
    }


def misroutes(run: dict, intents: dict[str, str]) -> dict[str, list[str]]:
    """An 'other' question sent to the calendar node, a calendar question sent away from it."""
    to_calendar, sent_away = [], []
    for r in run["per_question"]:
        if not r.get("router"):
            continue
        went = r["route"] in CALENDAR_ROUTES
        if went and intents[r["id"]] == "other":
            to_calendar.append(r["id"])
        if not went and intents[r["id"]] == "calendar":
            sent_away.append(r["id"])
    return {"other_to_calendar": to_calendar, "calendar_sent_away": sent_away}


def classifier_accuracy(run: dict, intents: dict[str, str]) -> tuple[int, int]:
    rows = [r for r in run["per_question"] if r.get("router")]
    right = sum(r["router"]["intent"] == intents[r["id"]] for r in rows)
    return right, len(rows)


def fell_through(run: dict) -> list[str]:
    return [r["id"] for r in run["per_question"] if r.get("route") == "calendar_fallthrough"]


def component_latency(run: dict) -> dict[str, dict]:
    """Median and p95 (ms) of classify, select, render (calendar route) and the whole request, by route."""
    out: dict[str, dict] = {}
    for route in ("calendar", "other", "calendar_fallthrough", "abstain"):
        rows = [r for r in run["per_question"] if r.get("route") == route]
        if not rows:
            continue
        parts = {
            "classify": [r["router"]["classify"]["ms"] for r in rows],
            "select": [r["router"]["select"]["ms"] for r in rows if r["router"].get("select")],
            "render": [r["router"]["render_ms"] for r in rows if "render_ms" in r["router"]],
            "total": [r["latency_ms"] for r in rows],
        }
        out[route] = {"n": len(rows)} | {
            k: (sorted(v)[len(v) // 2], percentile(v, 95)) if v else None for k, v in parts.items()
        }
    return out


def component_cost(run: dict) -> dict[str, float]:
    """USD per request by component, over all records of the run."""
    rows = run["per_question"]
    classify = [r["router"]["classify"]["cost"] if r.get("router") else 0.0 for r in rows]
    select = [
        (r["router"].get("select") or {}).get("cost", 0.0) if r.get("router") else 0.0 for r in rows
    ]
    rerank = [r.get("rerank_cost", 0.0) for r in rows]
    answer = [
        r["answer_cost"] - c - s - k
        for r, c, s, k in zip(rows, classify, select, rerank, strict=True)
    ]
    judge = [r["judge_cost"] for r in rows]
    n = len(rows)
    return {
        "classify": sum(classify) / n, "select": sum(select) / n, "rerank": sum(rerank) / n,
        "answer": sum(answer) / n, "judge": sum(judge) / n,
        "total_usd": sum(r["answer_cost"] + r["judge_cost"] for r in rows),
    }  # fmt: skip


def per_question_table(runs: list[dict], ids: list[str], gold: dict[str, list[str]]) -> list[str]:
    out = [
        "| id | gold rows | " + " | ".join(r["label"] for r in runs) + " |",
        "|---|---|" + "---|" * len(runs),
    ]
    for qid in ids:
        cells = []
        for run in runs:
            r = next((x for x in run["per_question"] if x["id"] == qid), None)
            cells.append(
                "-" if r is None else f"{r['correctness']} [{r['route']}] {r['returned_rows']}"
            )
        out.append(f"| {qid} | {gold[qid]} | " + " | ".join(cells) + " |")
    return out


def selector_numbers(run: dict) -> dict:
    """Selector input size (prompt tokens) and latency over the calendar-node requests."""
    rows = [
        r["router"]["select"]
        for r in run["per_question"]
        if r.get("router") and r["router"].get("select")
    ]
    if not rows:
        return {"n": 0}
    tokens, ms = [x["prompt_tokens"] for x in rows], [x["ms"] for x in rows]
    return {
        "n": len(rows),
        "tokens": sorted(tokens)[len(tokens) // 2],
        "ms": (sorted(ms)[len(ms) // 2], percentile(ms, 95)),
    }


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m cta.eval.router_report")
    p.add_argument("--router", nargs=3, required=True)
    p.add_argument("--before", nargs=3, required=True)
    p.add_argument("--new8", required=True)
    p.add_argument("--prev", nargs=3, help="the 4a router runs, for selector size and latency")
    p.add_argument(
        "--scoring", type=int, default=1, choices=(1, 2), help="version that decides the rule"
    )
    args = p.parse_args(argv[1:])
    runs, before = [load(x) for x in args.router], [load(x) for x in args.before]
    new8 = load(args.new8)
    questions = {q["id"]: q for q in load_questions() if q["split"] == "dev"}
    events, today = load_events(), __import__("datetime").date(2026, 10, 11)
    intents = {qid: gold_intent(q, events, today) for qid, q in questions.items()}
    cal_ids = sorted(qid for qid, q in questions.items() if gold_kind(q) == "calendar_only")
    gold = {qid: [g["id"] for g in questions[qid]["gold_sources"]] for qid in cal_ids}
    out = [
        "# Router results (step 4a)\n",
        f"Calendar-only dev questions ({len(cal_ids)}): {', '.join(cal_ids)}\n",
    ]
    out += [
        "## (a) and (b): calendar-only questions per run\n",
        "| run | correct | partial | incorrect | wrong dates stated | labels |",
        "|---|---|---|---|---|---|",
    ]
    sums = [calendar_summary(r, cal_ids, args.scoring) for r in runs]
    for r, s in zip(runs, sums, strict=True):
        out.append(
            f"| {r['label']} | {s['correct']} | {s['partial']} | {s['incorrect']} | {s['wrong_dates']} | {s['labels']} |"
        )
    nb = calendar_summary(new8, list(NEW8), args.scoring)
    out.append(
        f"| {new8['label']} (current system, 8 new) | {nb['correct']} | {nb['partial']} | {nb['incorrect']} | {nb['wrong_dates']} | {nb['labels']} |"
    )
    means = mean(s["correct"] for s in sums)
    ok_a = means >= 11 and min(s["correct"] for s in sums) >= 10
    ok_b = all(s["wrong_dates"] == 0 for s in sums)
    out += [
        "",
        f"Mean correct {means:.2f} of {len(cal_ids)}; lowest run {min(s['correct'] for s in sums)}. Rule (a): {'PASS' if ok_a else 'FAIL'}. Rule (b) no wrong date stated: {'PASS' if ok_b else 'FAIL'}.",
        "",
    ]
    for v in (1, 2):
        vs = [calendar_summary(r, cal_ids, v) for r in runs]
        out.append(
            f"- scored under v{v}{' (decides the rule)' if v == args.scoring else ''}: correct {[x['correct'] for x in vs]}, "
            f"partial {[x['partial'] for x in vs]}, wrong rows stated {[x['wrong_dates'] for x in vs]}"
        )
    extras = {qid: questions[qid].get("calendar_acceptable_extra", []) for qid in cal_ids}
    out.append(f"- acceptable extras in the gold: { {k: v for k, v in extras.items() if v} }")
    if args.prev:
        for label, group in (
            ("4a (selector v1)", [load(x) for x in args.prev]),
            ("this experiment", runs),
        ):
            nums = [selector_numbers(r) for r in group]
            out.append(
                f"- selector input and latency, {label}: median prompt tokens {[n['tokens'] for n in nums]}, median latency ms {[round(n['ms'][0]) for n in nums]}, p95 {[round(n['ms'][1]) for n in nums]}"
            )
    out.append("")
    out += per_question_table(runs, cal_ids, gold) + [""]
    out += ["## Routes, misroutes, classifier accuracy, fall-through\n"]
    for run in runs:
        m = misroutes(run, intents)
        right, total = classifier_accuracy(run, intents)
        counts = {
            k: sum(r.get("route") == k for r in run["per_question"])
            for k in ("calendar", "other", "calendar_fallthrough", "abstain")
        }
        out.append(
            f"- {run['label']}: routes {counts}; classifier accuracy {right}/{total}; other sent to calendar {m['other_to_calendar']}; calendar sent away {m['calendar_sent_away']}; fell through {fell_through(run)}"
        )
    out.append("")
    # rule (c): the common 40 questions against the stored 3b arm-ON runs
    common = ac.common_question_ids([*runs, *before])
    old = [ac.restrict(r, common) for r in before]
    new = [ac.restrict(r, common) for r in runs]
    checks = ac.apply_rule(ac.arm_summary(old), ac.arm_summary(new))
    out += [
        f"## (c): the {len(common)} common questions, router runs against the stored 3b arm-ON runs ({', '.join(args.before)})\n"
    ]
    out += [f"- {'PASS' if ok else 'FAIL'}  {name}: {text}" for name, ok, text in checks]
    ok_c = all(ok for _, ok, _ in checks)
    summary_old, summary_new = ac.arm_summary(old), ac.arm_summary(new)
    out += ["", "| metric | before (3b ON) | router |", "|---|---|---|"]
    for label, k in (
        ("correct share", "correct"),
        ("faithfulness yes", "faithful_yes"),
        ("abstention accuracy", "abstention_accuracy"),
        ("wrongly abstained", "wrongly_abstained"),
        ("citation rate", "citation_rate"),
        ("invalid citations", "invalid_citations"),
    ):
        out.append(f"| {label} | {ac.cell(summary_old[k])} | {ac.cell(summary_new[k])} |")
    out.append("")
    c_off, c_on = ac.verdicts(old, "correctness"), ac.verdicts(new, "correctness")
    f_off, f_on = ac.verdicts(old, "faithfulness"), ac.verdicts(new, "faithfulness")
    changed = []
    for qid in c_off:
        if gold_kind(questions[qid]) == "calendar_only":
            continue
        kinds = [
            ac.classify(c_off[qid], c_on[qid], ac.CORRECTNESS),
            ac.classify(f_off[qid], f_on[qid], ac.FAITHFULNESS),
        ]
        if any(k != "same" for k in kinds):
            changed.append(
                f"{qid} correctness {c_off[qid]} -> {c_on[qid]}: {kinds[0]}; faithfulness {f_off[qid]} -> {f_on[qid]}: {kinds[1]}"
            )
    out += [
        "Questions whose verdict changed or is unstable (judged questions):",
        *[f"- {c}" for c in changed or ["none"]],
        "",
    ]
    ok_d = True
    out += ["## (d): abstain questions for unsupported terms and sections\n"]
    for qid in ABSTAIN_CHECK:
        cells = []
        for run in runs:
            r = next((x for x in run["per_question"] if x["id"] == qid), None)
            good = bool(r and r["abstained"])
            ok_d &= good
            cells.append(f"{'abstained' if good else 'ANSWERED'} [{r['route'] if r else '-'}]")
        out.append(f"- {qid}: " + ", ".join(cells))
    out += ["", f"Rule (d): {'PASS' if ok_d else 'FAIL'}.", ""]
    out += ["## Latency per route, median / p95 ms\n"]
    for run in runs:
        for route, v in component_latency(run).items():
            out.append(
                f"- {run['label']} {route} (n={v['n']}): "
                + ", ".join(f"{k} {x[0]:.0f} / {x[1]:.0f}" for k, x in v.items() if k != "n" and x)
            )
    out += [
        "",
        "## Cost per request (USD)\n",
        "| run | classify | select | rerank | answer | judge | total run |",
        "|---|---|---|---|---|---|---|",
    ]
    for run in runs:
        c = component_cost(run)
        out.append(
            f"| {run['label']} | {c['classify']:.5f} | {c['select']:.5f} | {c['rerank']:.5f} | {c['answer']:.5f} | {c['judge']:.5f} | {c['total_usd']:.4f} |"
        )
    keep = ok_a and ok_b and ok_c and ok_d
    out += [
        "",
        f"## Verdict by the pre-registered rule: (a) {ok_a}, (b) {ok_b}, (c) {ok_c}, (d) {ok_d} => {'KEEP router on' if keep else 'REJECT: the default stays off'}",
        "",
    ]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
