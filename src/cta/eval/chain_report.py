# ruff: noqa: E501
"""Report on the step 4b runs: the measures M1 to M6 and the keep rule R1 to R6 of docs/archive/step4b-plan.md.

    uv run python -m cta.eval.chain_report --runs 4b-run1 4b-run2 4b-run3 --router2 router2-run1 router2-run2 router2-run3

Reads the results files and request_logs (the ids of the sources each answerer received). No model call.
"""

import argparse
import sys
from statistics import mean

from cta.eval import answer_compare as ac
from cta.eval import router_report as rr
from cta.eval.questions import load_questions
from cta.eval.run_answers import percentile

OLD_CALENDAR_MISROUTES = {"q09", "q13", "q30"}


def question_sets(rows: list[dict]) -> dict[str, list[str]]:
    """CH, AB and CTRL of the plan, computed from the dev questions."""
    dev = [q for q in rows if q["split"] == "dev"]
    ch = [q["id"] for q in dev if "chain" in q.get("tags", []) and q["type"] != "unanswerable"]
    ab = ["q83"] if any(q["id"] == "q83" for q in dev) else []
    ctrl = [q["id"] for q in dev if q["id"] not in ch and q["id"] not in ab]
    return {"CH": ch, "AB": ab, "CTRL": ctrl}


def gold_catalog(q: dict) -> list[str]:
    return [g["id"] for g in q["gold_sources"] if g["id"].startswith("catalog:")]


def answered_by_chain(record: dict) -> bool:
    """The chain node answered (a chain answer, or the no-record abstain), not a fall-through."""
    router = record.get("router") or {}
    chain = router.get("chain") or {}
    return record.get("route") == "chain" or bool(chain.get("no_record"))


def calendar_misroutes(run: dict, intents: dict[str, str]) -> list[str]:
    """Questions whose gold intent is not calendar that the classifier sent to the calendar node. The
    route name 'abstain' is shared by the calendar node and the chain node, so the classifier's
    intent says where the question went (the first version of this report counted the chain node's
    no-record abstain of q83 as a calendar misroute)."""
    return sorted(
        r["id"]
        for r in run["per_question"]
        if (r.get("router") or {}).get("intent") == "calendar" and intents[r["id"]] == "other"
    )


def prerequisite_intent(record: dict) -> bool:
    return (record.get("router") or {}).get("intent") == "prerequisite"


def coverage(received: list[str], gold: list[str]) -> bool:
    """Every gold source was among the sources the answerer received."""
    return set(gold) <= set(received)


def m3(sources: dict[str, list[str]], questions: dict[str, dict], ids: list[str]) -> float | None:
    """Chain coverage over the questions of `ids` with two or more gold catalog sources."""
    eligible = [i for i in ids if len(gold_catalog(questions[i])) >= 2 and i in sources]
    if not eligible:
        return None
    return sum(coverage(sources[i], gold_catalog(questions[i])) for i in eligible) / len(eligible)


def route_stats(run: dict) -> dict[str, dict]:
    """Per route: n, latency p50/p95 (total ms), mean tokens-free cost per request (answer cost)."""
    out = {}
    for route in sorted({r.get("route") for r in run["per_question"] if r.get("route")}):
        rows = [r for r in run["per_question"] if r.get("route") == route]
        lat = [r["latency_ms"] for r in rows]
        out[route] = {
            "n": len(rows),
            "p50": sorted(lat)[len(lat) // 2],
            "p95": percentile(lat, 95),
            "cost": mean(r["answer_cost"] for r in rows),
        }
    return out


def received_sources(conn, label: str, questions: dict[str, dict]) -> dict[str, list[str]]:
    """question id -> ids of the numbered sources the answerer received (request_logs.retrieved)."""
    from cta.redact import redact

    run_id = conn.execute(
        "SELECT id FROM eval_runs WHERE label = %s ORDER BY id DESC LIMIT 1", (label,)
    ).fetchone()[0]
    out = {}
    for qid, q in questions.items():
        row = conn.execute(
            "SELECT retrieved FROM request_logs WHERE run_id = %s AND question = %s ORDER BY id DESC LIMIT 1",
            (run_id, redact(q["question"])),
        ).fetchone()
        if row:
            out[qid] = [r["id"] for r in row[0]]
    return out


def answers_of(conn, label: str, questions: dict[str, dict]) -> dict[str, str]:
    from cta.redact import redact

    run_id = conn.execute(
        "SELECT id FROM eval_runs WHERE label = %s ORDER BY id DESC LIMIT 1", (label,)
    ).fetchone()[0]
    out = {}
    for qid, q in questions.items():
        row = conn.execute(
            "SELECT answer FROM request_logs WHERE run_id = %s AND question = %s ORDER BY id DESC LIMIT 1",
            (run_id, redact(q["question"])),
        ).fetchone()
        out[qid] = row[0] if row else ""
    return out


def verdict(rules: dict[str, bool]) -> str:
    return "KEEP" if all(rules.values()) else "REJECT"


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m cta.eval.chain_report")
    p.add_argument("--runs", nargs=3, required=True)
    p.add_argument("--router2", nargs=3, required=True)
    args = p.parse_args(argv[1:])
    from cta.index.db import connect

    rows = load_questions()
    questions = {q["id"]: q for q in rows if q["split"] == "dev"}
    sets = question_sets(rows)
    runs, base = [rr.load(x) for x in args.runs], [rr.load(x) for x in args.router2]
    events, today = rr.load_events(), __import__("datetime").date(2026, 10, 11)
    intents = {i: rr.gold_intent(q, events, today) for i, q in questions.items()}
    out = [
        "# Step 4b results",
        "",
        f"CH ({len(sets['CH'])}): {', '.join(sets['CH'])}; AB: {', '.join(sets['AB'])}; CTRL: {len(sets['CTRL'])} questions (q87 in it).",
        "",
    ]
    with connect() as conn:
        got = [received_sources(conn, label, questions) for label in args.runs]
        old = [received_sources(conn, label, questions) for label in args.router2]
    rules: dict[str, bool] = {}
    by_id = [{r["id"]: r for r in run["per_question"]} for run in runs]
    # M1, M2
    out += [
        "## M1 and M2",
        "",
        "| run | M1 CH answered by the chain node | CH with intent prerequisite | M2 CTRL answered by the chain node | CTRL intent prerequisite but fell through |",
        "|---|---|---|---|---|",
    ]
    m1, m2ids, q87 = [], [], []
    for run, rec in zip(args.runs, by_id, strict=True):
        a = [i for i in sets["CH"] if answered_by_chain(rec[i])]
        b = [i for i in sets["CH"] if prerequisite_intent(rec[i])]
        c = [i for i in sets["CTRL"] if answered_by_chain(rec[i])]
        f = [
            i for i in sets["CTRL"] if prerequisite_intent(rec[i]) and not answered_by_chain(rec[i])
        ]
        m1.append(len(sets["CH"]) - len(a))
        m2ids.append(c)
        q87.append("q87" in c)
        out.append(
            f"| {run} | {len(a)} of {len(sets['CH'])} (missed: {[i for i in sets['CH'] if i not in a]}) | {len(b)} | {c} | {f} |"
        )
    rules["R1"] = not any(q87) and all(len([i for i in ids if i != "q87"]) <= 1 for ids in m2ids)
    rules["R2"] = all(x <= 1 for x in m1)
    # M3
    m3_runs = [m3(g, questions, sets["CH"]) for g in got]
    base_ids = [i for i in sets["CH"] if all(i in o for o in old)]
    m3_base = [m3(o, questions, base_ids) for o in old]
    m3_new_on_base = [m3(g, questions, base_ids) for g in got]
    out += [
        "",
        "## M3 chain coverage (CH questions with 2 or more gold catalog sources)",
        "",
        f"- 4b runs, all eligible CH questions: {[None if x is None else round(x, 2) for x in m3_runs]}",
    ]
    for i in sets["CH"]:
        if len(gold_catalog(questions[i])) >= 2:
            out.append(
                f"  - {i}: "
                + ", ".join(
                    f"{'covered' if coverage(g.get(i, []), gold_catalog(questions[i])) else 'NOT covered'}"
                    for g in got
                )
            )
    out.append(
        f"- on the questions the router2 logs also contain ({base_ids}): 4b {[None if x is None else round(x, 2) for x in m3_new_on_base]}, router2 {[None if x is None else round(x, 2) for x in m3_base]}"
    )
    mean_new = (
        mean(x for x in m3_new_on_base if x is not None)
        if any(x is not None for x in m3_new_on_base)
        else None
    )
    mean_old = (
        mean(x for x in m3_base if x is not None) if any(x is not None for x in m3_base) else None
    )
    rules["R3"] = (
        all(x is not None and x >= 0.80 for x in m3_runs)
        and mean_new is not None
        and mean_old is not None
        and mean_new > mean_old
    )
    # M4
    cal = sorted(i for i, q in questions.items() if rr.gold_kind(q) == "calendar_only")
    cs = [rr.calendar_summary(run, cal, 2) for run in runs]
    mis = [sorted(set(calendar_misroutes(run, intents)) - OLD_CALENDAR_MISROUTES) for run in runs]
    out += [
        "",
        "## M4 calendar-only dev questions under scoring v2",
        "",
        f"- correct per run: {[s['correct'] for s in cs]} of {len(cal)}; wrong rows: {[s['wrong_dates'] for s in cs]}; new calendar misroutes beyond q09 q13 q30: {mis}",
    ]
    rules["R4"] = all(s["correct"] >= 12 and s["wrong_dates"] == 0 for s in cs) and all(
        not m for m in mis
    )
    # M5
    common = ac.common_question_ids([*runs, *base])
    new, old_runs = [ac.restrict(r, common) for r in runs], [ac.restrict(r, common) for r in base]
    sn, so = ac.arm_summary(new), ac.arm_summary(old_runs)
    out += [
        "",
        f"## M5 judged questions on the {len(common)} dev ids common to the router2 runs",
        "",
        "| metric | router2 | 4b |",
        "|---|---|---|",
    ]
    for label, k in (
        ("correct share", "correct"),
        ("faithfulness yes", "faithful_yes"),
        ("abstention accuracy", "abstention_accuracy"),
        ("wrongly abstained", "wrongly_abstained"),
        ("citation rate", "citation_rate"),
        ("invalid citations", "invalid_citations"),
    ):
        out.append(f"| {label} | {ac.cell(so[k])} | {ac.cell(sn[k])} |")
    rules["R5"] = sn["correct"][0] >= so["correct"][0] - 0.03
    # M6
    q83 = [r["q83"] for r in by_id if "q83" in r]
    out += [
        "",
        "## M6 q83",
        "",
        f"- abstained: {[r['abstained'] for r in q83]}, route: {[r['route'] for r in q83]}",
    ]
    rules["R6"] = len(q83) == 3 and all(r["abstained"] for r in q83)
    out += ["", "## Extras (no rule)", ""]
    out.append(
        f"- calendar misroutes by classifier intent (all, including q09 q13 q30): {[calendar_misroutes(run, intents) for run in runs]}"
    )
    for run in runs:
        out.append(
            f"- {run['label']} per route (n, p50 ms, p95 ms, mean answer-side cost per request): "
            + "; ".join(
                f"{k}: {v['n']}, {v['p50']}, {v['p95']}, ${v['cost']:.5f}"
                for k, v in route_stats(run).items()
            )
        )
    for label, group in (("router2", base), ("4b", runs)):
        cls = [
            mean(r["router"]["classify"]["cost"] for r in run["per_question"] if r.get("router"))
            for run in group
        ]
        out.append(f"- classifier cost per request, {label}: {[round(c, 6) for c in cls]}")
    out += ["", "## Every CH and AB question, per run", ""]
    with connect() as conn:
        texts = [answers_of(conn, label, questions) for label in args.runs]
    for qid in sets["CH"] + sets["AB"]:
        out.append(f"### {qid}: {questions[qid]['question']}")
        out.append(f"gold sources: {gold_catalog(questions[qid]) or '(none)'}")
        for n, (run, rec) in enumerate(zip(runs, by_id, strict=True)):
            r = rec[qid]
            first = (
                (texts[n].get(qid, "") or "").strip().splitlines()[0][:220]
                if texts[n].get(qid)
                else ""
            )
            out.append(
                f"- {run['label']}: route {r['route']}, intent {(r.get('router') or {}).get('intent')}, answered by chain {answered_by_chain(r)}; sources received {got[n].get(qid, [])}; verdict {r['correctness']} / {r['faithfulness']}; first line: {first}"
            )
        out.append("")
    out.append(
        "CTRL questions with classifier intent prerequisite: "
        + "; ".join(
            f"{run['label']}: {[i for i in sets['CTRL'] if prerequisite_intent(rec[i])]}"
            for run, rec in zip(runs, by_id, strict=True)
        )
    )
    out += ["", "## Keep rule", "", "| rule | pass |", "|---|---|"] + [
        f"| {k} | {'pass' if v else 'FAIL'} |" for k, v in rules.items()
    ]
    out += ["", f"**Verdict by the pre-registered rule: {verdict(rules)}**", ""]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
