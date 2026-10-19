"""Compare saved answer-level runs (no database, no network). Used for step 3b.

    uv run python -m cta.eval.answer_compare report --off A B C --on D E F [--judge-repeat G]
    uv run python -m cta.eval.answer_compare v3-check OLD NEW  # -> docs/archive/judge-check-v3.md

`report` prints, for two arms of three runs each: the metrics (mean and range over the runs), the
rule written in docs/experiments.md (step 3b), the cost and latency split, a per-question table of
verdicts across the runs with the real changes and the unstable questions, and the judge noise.
"""

import argparse
import json
import sys
from statistics import mean

from cta.eval.questions import load_questions
from cta.eval.run_answers import aggregate, percentile
from cta.eval.run_retrieval import RESULTS
from cta.settings import ROOT

CORRECTNESS = {"incorrect": 0, "partial": 1, "correct": 2}
FAITHFULNESS = {"no": 0, "partly": 1, "yes": 2}
EPS = 1e-9
ONE_QUESTION = 1 / 26  # one judged normal-gold question's share (docs/experiments.md, step 3b)


def load_run(label: str) -> dict:
    return json.loads((RESULTS / f"{label}.json").read_text(encoding="utf-8"))


# ---- metrics per run ----


def run_metrics(run: dict) -> dict[str, float]:
    """The numbers the rule and the report use, from one run's aggregate and records."""
    a, rows = run["answers"], run["per_question"]
    wrongly = a["wrongly_abstained"]
    return {
        "correct": a["correctness"]["correct"],
        "partial": a["correctness"]["partial"],
        "incorrect": a["correctness"]["incorrect"],
        "faithful_yes": a["faithfulness"]["yes"],
        "abstention_accuracy": a["abstention_accuracy"]["share"],
        "wrongly_abstained": wrongly["share"] * wrongly["n"],
        "citation_rate": a["citation_rate"]["share"],
        "invalid_citations": a["citation_rate"]["invalid_citations"],
        "no_advice_correct": a["no_advice_correct"]["correct"],
        "answer_usd_per_request": sum(r["answer_cost"] - r.get("rerank_cost", 0.0) for r in rows)
        / len(rows),
        "rerank_usd_per_request": sum(r.get("rerank_cost", 0.0) for r in rows) / len(rows),
        "judge_usd_per_request": sum(r["judge_cost"] for r in rows) / len(rows),
    }


def latency_metrics(run: dict) -> dict[str, float | None]:
    """Median and p95 of the total, search, rerank and answer (chat) time per request, in ms."""
    rows = run["per_question"]
    out = {}
    parts = {
        "total": [r["latency_ms"] for r in rows],
        "search": [
            r["retrieval_ms"] - r.get("rerank_ms", 0.0)
            for r in rows
            if r.get("retrieval_ms") is not None
        ],
        "rerank": [r["rerank_ms"] for r in rows if r.get("rerank_ms")],
        "answer": [r["chat_ms"] for r in rows if r["chat_ms"]],
    }
    for name, values in parts.items():
        ordered = sorted(values)
        out[f"{name}_median"] = ordered[len(ordered) // 2] if ordered else None
        out[f"{name}_p95"] = percentile(values, 95)
    return out


def spread(values: list[float | None]) -> tuple[float, float, float] | None:
    """(mean, min, max) of the known values."""
    known = [v for v in values if v is not None]
    return (mean(known), min(known), max(known)) if known else None


def arm_summary(runs: list[dict]) -> dict[str, tuple[float, float, float] | None]:
    per_run = [run_metrics(r) | latency_metrics(r) for r in runs]
    return {name: spread([m[name] for m in per_run]) for name in per_run[0]}


# ---- the rule ----


def apply_rule(off: dict, on: dict) -> list[tuple[str, bool, str]]:
    """(name, passed, text) for (a) to (d) of the step 3b rule, on the arm means."""

    def m(arm, name):
        return arm[name][0]

    checks = []
    d = m(on, "correct") - m(off, "correct")
    checks.append(
        ("a: correct share", d >= -ONE_QUESTION - EPS, f"{d:+.3f} (limit -{ONE_QUESTION:.3f})")
    )
    d = m(on, "faithful_yes") - m(off, "faithful_yes")
    checks.append(("b: faithfulness yes share", d >= -EPS, f"{d:+.3f} (must not fall)"))
    d1 = m(on, "abstention_accuracy") - m(off, "abstention_accuracy")
    d2 = m(on, "wrongly_abstained") - m(off, "wrongly_abstained")
    checks.append(
        (
            "c: abstention",
            d1 >= -EPS and d2 <= EPS,
            f"accuracy {d1:+.3f}, wrongly abstained {d2:+.2f} per run",
        )  # fmt: skip
    )
    d1 = m(on, "citation_rate") - m(off, "citation_rate")
    d2 = m(on, "invalid_citations") - m(off, "invalid_citations")
    checks.append(
        (
            "d: citation validity",
            d1 >= -EPS and d2 <= EPS,
            f"citation rate {d1:+.3f}, invalid citations {d2:+.2f} per run",
        )  # fmt: skip
    )
    return checks


# ---- per-question verdicts, noise ----


def verdicts(runs: list[dict], field: str) -> dict[str, list]:
    """question id -> that field's value in each run."""
    out: dict[str, list] = {}
    for run in runs:
        for r in run["per_question"]:
            out.setdefault(r["id"], []).append(r[field])
    return out


def sign(x: float) -> int:
    return (x > 0) - (x < 0)


def classify(off: list, on: list, order: dict[str, int]) -> str:
    """same | real better | real worse | unstable (leaning better) | unstable (leaning worse) |
    unstable. Real = identical in all runs of each arm and different between the arms."""
    if None in off or None in on:
        return "same"  # not judged (rule-graded or CLARIFY): no verdict to compare
    stable = len(set(off)) == 1 and len(set(on)) == 1
    if stable:
        diff = order[on[0]] - order[off[0]]
        return "same" if diff == 0 else ("real better" if diff > 0 else "real worse")
    signs = [sign(order[b] - order[a]) for a, b in zip(off, on, strict=True)]
    for direction, name in ((1, "better"), (-1, "worse")):
        if signs.count(direction) >= 2:
            return f"unstable (leaning {name})"
    return "unstable"


def judge_noise(first: dict, second: dict) -> list[str]:
    """Verdicts that differ between two judgements of the same answers."""
    older = {r["id"]: r for r in first["per_question"]}
    lines = []
    for r in second["per_question"]:
        o = older[r["id"]]
        for field in ("correctness", "faithfulness"):
            if o[field] != r[field]:
                lines.append(f"{r['id']} {field}: {o[field]} -> {r[field]}")
    return lines


# ---- v2 against v3 (the judge-check file) ----


def verdict_diff_markdown(old: dict, new: dict, questions: dict) -> str:
    older = {r["id"]: r for r in old["per_question"]}
    out = [
        "# Judge check: rubric v2 against v3 on the stored `baseline-dev-60` answers",
        "",
        "The answers are the same in both columns (nothing was regenerated); only the rubric "
        "differs. Each question below is one where the correctness or faithfulness verdict "
        "changed. The judge's one-line reasons are copied unedited. This file does not say which "
        "version is right: check them by hand against the gold answer and the sources.",
        "",
    ]
    changed = 0
    for r in new["per_question"]:
        o = older[r["id"]]
        if (o["correctness"], o["faithfulness"]) == (r["correctness"], r["faithfulness"]):
            continue
        changed += 1
        q = questions[r["id"]]
        out += [
            f"## {r['id']} ({q['type']})",
            "",
            f"**Question:** {q['question']}",
            "",
            f"**Gold answer:** {q['gold_answer']}",
            "",
            "| | v2 | v3 |",
            "|---|---|---|",
            f"| correctness | {o['correctness']} | {r['correctness']} |",
            f"| correctness reason | {o['correctness_reason']} | {r['correctness_reason']} |",
            f"| faithfulness | {o['faithfulness']} | {r['faithfulness']} |",
            f"| faithfulness reason | {o['faithfulness_reason']} | {r['faithfulness_reason']} |",
            "",
        ]
    out.insert(
        3, f"Questions with a changed verdict: **{changed}** of {len(new['per_question'])}.\n"
    )
    return "\n".join(out) + "\n"


# ---- the report ----


def fmt(v, digits=3) -> str:
    return "-" if v is None else f"{v:.{digits}f}"


def cell(s) -> str:
    return "-" if s is None else f"{s[0]:.3f} ({s[1]:.3f} to {s[2]:.3f})"


def common_question_ids(runs: list[dict]) -> list[str]:
    sets = [{r["id"] for r in run["per_question"]} for run in runs]
    return sorted(set.intersection(*sets))


def restrict(run: dict, ids: list[str]) -> dict:
    """The run limited to these questions, its aggregate numbers recomputed from the records."""
    rows = [r for r in run["per_question"] if r["id"] in set(ids)]
    return {**run, "per_question": rows, "answers": aggregate(rows)}


def report(off_runs: list[dict], on_runs: list[dict], repeat: dict | None, first_on: dict) -> str:
    everything = [*off_runs, *on_runs, *([repeat] if repeat else [])]
    ids = common_question_ids(everything)
    sizes = sorted({len(run["per_question"]) for run in everything})
    notice = []
    if len(sizes) > 1 or len(ids) != sizes[0]:
        notice = [
            f"> The runs answered different question sets (sizes {sizes}). Everything below uses "
            f"only the {len(ids)} common ids; the aggregates are recomputed from the records.",
            "",
        ]
        off_runs, on_runs = (
            [restrict(r, ids) for r in off_runs],
            [restrict(r, ids) for r in on_runs],
        )
        repeat = restrict(repeat, ids) if repeat else None
        first_on = restrict(first_on, ids)
    off, on = arm_summary(off_runs), arm_summary(on_runs)
    out = ["# Answer-level comparison: reranker off against pool_a", "", *notice]
    out.append("## Metrics, mean (min to max) over the 3 runs of each arm\n")
    out += ["| metric | OFF | ON |", "|---|---|---|"]
    rows = [
        ("correct share", "correct"), ("partial share", "partial"),
        ("incorrect share", "incorrect"), ("faithfulness yes share", "faithful_yes"),
        ("abstention accuracy", "abstention_accuracy"),
        ("wrongly abstained (count per run)", "wrongly_abstained"),
        ("citation rate", "citation_rate"), ("invalid citations (per run)", "invalid_citations"),
        ("NO ADVICE correct share", "no_advice_correct"),
    ]  # fmt: skip
    out += [f"| {label} | {cell(off[k])} | {cell(on[k])} |" for label, k in rows]
    out += ["", "## Latency per request in ms: median / p95, mean over the runs\n"]
    out += ["| part | OFF | ON |", "|---|---|---|"]
    for part in ("total", "search", "rerank", "answer"):

        def lat(arm, part=part):
            med, p95 = arm[f"{part}_median"], arm[f"{part}_p95"]
            return "-" if med is None else f"{med[0]:.0f} / {p95[0]:.0f}"

        out.append(f"| {part} | {lat(off)} | {lat(on)} |")
    out += [
        "",
        "## Cost per request in USD (mean over the runs)\n",
        "| part | OFF | ON |",
        "|---|---|---|",
    ]
    for label, k in (("answers", "answer_usd_per_request"), ("rerank", "rerank_usd_per_request"),
                     ("judge", "judge_usd_per_request")):  # fmt: skip
        out.append(f"| {label} | {fmt(off[k][0], 5)} | {fmt(on[k][0], 5)} |")
    out += ["", "## Failure labels per run (count)\n"]
    for name, runs in (("OFF", off_runs), ("ON", on_runs)):
        for i, r in enumerate(runs, 1):
            out.append(f"- {name} run {i} (`{r['label']}`): {r['failure_labels']}")
    out += ["", "## The rule (docs/experiments.md, step 3b), on the arm means\n"]
    checks = apply_rule(off, on)
    out += [f"- {'PASS' if ok else 'FAIL'}  {name}: {text}" for name, ok, text in checks]
    verdict = "KEEP pool_a" if all(ok for _, ok, _ in checks) else "REVERT the default to off"
    out += ["", f"**Verdict by the rule: {verdict}.**", ""]
    out += ["## Per question: verdict in each run (c = correct, p = partial, i = incorrect; "
            "y = faithful yes, ~ = partly, n = no; - = not judged)\n"]  # fmt: skip
    out += [
        "| id | type | OFF corr | ON corr | OFF faith | ON faith | change |",
        "|---|---|---|---|---|---|---|",
    ]
    short = {
        "correct": "c",
        "partial": "p",
        "incorrect": "i",
        "yes": "y",
        "partly": "~",
        "no": "n",
        None: "-",
    }
    types = {r["id"]: r["type"] for r in off_runs[0]["per_question"]}
    c_off, c_on = verdicts(off_runs, "correctness"), verdicts(on_runs, "correctness")
    f_off, f_on = verdicts(off_runs, "faithfulness"), verdicts(on_runs, "faithfulness")
    real, unstable = [], []
    for qid in c_off:
        kinds = [
            classify(c_off[qid], c_on[qid], CORRECTNESS),
            classify(f_off[qid], f_on[qid], FAITHFULNESS),
        ]
        note = "; ".join(
            f"{d}: {k}"
            for d, k in zip(("correctness", "faithfulness"), kinds, strict=True)
            if k != "same"
        )
        for k in kinds:
            if k.startswith("real"):
                real.append(qid)
            elif k.startswith("unstable"):
                unstable.append(qid)

        def row(values):
            return " ".join(short[v] for v in values)

        cells = [row(c_off[qid]), row(c_on[qid]), row(f_off[qid]), row(f_on[qid])]
        out.append(f"| {qid} | {types[qid]} | " + " | ".join(cells) + f" | {note} |")
    out += [
        "",
        f"Real changes: {sorted(set(real)) or 'none'}",
        f"Unstable (not counted): {sorted(set(unstable)) or 'none'}",
        "",
    ]
    if repeat:
        diff = judge_noise(first_on, repeat)
        total = 2 * len(first_on["per_question"])
        out += [
            f"## Judge noise: `on-run1` judged twice, {len(diff)} of {total} "
            "correctness and faithfulness verdicts differ\n"
        ]
        out += [f"- {line}" for line in diff] or ["- none"]
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m cta.eval.answer_compare")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report")
    r.add_argument("--off", nargs=3, required=True)
    r.add_argument("--on", nargs=3, required=True)
    r.add_argument("--judge-repeat")
    v = sub.add_parser("v3-check")
    v.add_argument("old")
    v.add_argument("new")
    args = p.parse_args(argv[1:])
    if args.cmd == "report":
        off, on = [load_run(x) for x in args.off], [load_run(x) for x in args.on]
        repeat = load_run(args.judge_repeat) if args.judge_repeat else None
        print(report(off, on, repeat, on[0]))
        return 0
    questions = {q["id"]: q for q in load_questions()}
    text = verdict_diff_markdown(load_run(args.old), load_run(args.new), questions)
    (ROOT / "docs" / "archive" / "judge-check-v3.md").write_text(text, encoding="utf-8")
    print("wrote docs/archive/judge-check-v3.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
