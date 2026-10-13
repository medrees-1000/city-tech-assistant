"""Dev comparison of the chain layout (docs/chain-layout-plan.md, item 1): the code renderer's two runs
against the three 4b runs on the 8 CH questions (+ q83, q87). Deterministic results and the judge's
verdicts are printed in separate sections.   uv run python scripts/chain_render_report.py
"""

import json
from statistics import mean

from cta.eval.chain_report import coverage, gold_catalog, question_sets
from cta.eval.questions import load_questions
from cta.index.db import connect
from cta.redact import redact
from cta.settings import ROOT

R = ROOT / "eval" / "results"
OLD = ["4b-run1", "4b-run2", "4b-run3"]
NEW = ["chain-code-run1", "chain-code-run2"]


def load(label):
    return {q["id"]: q for q in json.loads((R / f"{label}.json").read_text())["per_question"]}


def answers(label, questions):
    out = {}
    with connect() as conn:
        run_id = conn.execute("SELECT id FROM eval_runs WHERE label = %s", (label,)).fetchone()[0]
        for qid, text in questions.items():
            out[qid] = conn.execute(
                "SELECT answer FROM request_logs WHERE run_id = %s AND question = %s ORDER BY id DESC LIMIT 1",
                (run_id, redact(text)),
            ).fetchone()[0]
    return out


def main():
    rows = {q["id"]: q for q in load_questions() if q["split"] == "dev"}
    ch = question_sets(list(rows.values()))["CH"]
    old = {label: load(label) for label in OLD}
    new = {label: load(label) for label in NEW}
    print("CH questions:", ch)

    print("\n=== DETERMINISTIC RESULTS (no judge) ===")
    # M1: every CH question answered by the chain node
    for label, run in {**old, **new}.items():
        n = sum(run[i]["route"] == "chain" for i in ch)
        print(f"M1 {label}: {n} of {len(ch)} CH questions answered by the chain node")
    # M3: gold catalog sources among the sources the answerer received
    many = [i for i in ch if len(gold_catalog(rows[i])) >= 2]
    for label, run in {**old, **new}.items():
        got = {i: run[i]["router"]["chain"]["source_ids"] for i in ch if run[i]["route"] == "chain"}
        cov = [coverage(got.get(i, []), gold_catalog(rows[i])) for i in many]
        print(f"M3 {label}: gold catalog sources received on {sum(cov)} of {len(many)} questions with 2+ gold sources")
    # M6
    for label, run in {**old, **new}.items():
        r = run["q83"]
        print(f"M6 {label}: q83 abstained={r['abstained']} route={r['route']}")
    # determinism
    qtext = {i: rows[i]["question"] for i in ch}
    a1, a2 = answers(NEW[0], qtext), answers(NEW[1], qtext)
    print(f"determinism: the two code runs wrote identical text for {sum(a1[i] == a2[i] for i in ch)} of {len(ch)} CH questions")
    print("no 'Level' wording in any code answer:", all("Level" not in a for a in a1.values()))
    print("sources identical to the 4b runs' sources (ids and order):", all(
        new[NEW[0]][i]["router"]["chain"]["source_ids"] == old[OLD[0]][i]["router"]["chain"]["source_ids"] for i in ch))
    # K4 cost
    def cost(run):
        return mean(run[i]["answer_cost"] for i in ch)
    old_cost = mean(cost(r) for r in old.values())
    new_cost = mean(cost(r) for r in new.values())
    def ms(run):
        return mean(run[i]["latency_ms"] for i in ch)
    print(f"K4 cost per chain question (route cost, judge excluded): 4b ${old_cost:.6f}, code ${new_cost:.6f} (lower: {new_cost < old_cost})")
    print(f"latency per chain question, mean: 4b {mean(ms(r) for r in old.values()):.0f} ms, code {mean(ms(r) for r in new.values()):.0f} ms")

    print("\n=== THE JUDGE'S VERDICTS (rubric v3; known to be unreliable on 'the sources do not state X' sentences) ===")
    def count(run, field, good):
        return sum(run[i][field] == good for i in ch)
    for field, good in (("correctness", "correct"), ("faithfulness", "yes")):
        olds = [count(r, field, good) for r in old.values()]
        news = [count(r, field, good) for r in new.values()]
        print(f"{field} '{good}' on the {len(ch)} CH questions: 4b runs {olds} (mean {mean(olds):.2f}); code runs {news} (mean {mean(news):.2f}); "
              f"difference {mean(news) - mean(olds):+.2f} questions")
    print("per question (4b run1, run2, run3 | code run1, run2) correctness / faithfulness:")
    for i in ch:
        o = " ".join(f"{old[l][i]['correctness'][:4]}/{old[l][i]['faithfulness'] or '-'}" for l in OLD)
        n = " ".join(f"{new[l][i]['correctness'][:4]}/{new[l][i]['faithfulness'] or '-'}" for l in NEW)
        print(f"  {i}: {o} | {n}")
    print("controls: q87 (not a chain question) route:", {l: r['q87']['route'] for l, r in new.items()}, "correctness:", {l: r['q87']['correctness'] for l, r in new.items()})
    for label, run in new.items():
        for i in ch:
            if run[i]["faithfulness"] != "yes" or run[i]["correctness"] != "correct":
                print(f"  {label} {i}: correctness={run[i]['correctness']} ({(run[i]['correctness_reason'] or '')[:150]}) faithfulness={run[i]['faithfulness']} ({(run[i]['faithfulness_reason'] or '')[:150]})")


if __name__ == "__main__":
    main()
