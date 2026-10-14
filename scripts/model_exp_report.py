"""Model experiment (docs/decisions.md, "Model experiment: gpt-6-luna against gpt-6-sol ..."): the rule B1 to B6
evaluated from the six stored runs, and the answers where the arms differ.   uv run python scripts/model_exp_report.py
"""

import json
import sys
from statistics import mean, median

from cta.eval.questions import load_questions
from cta.index.db import connect
from cta.redact import redact
from cta.settings import ROOT

R = ROOT / "eval" / "results"
ARMS = {"luna": [f"modelexp-luna-run{i}" for i in (1, 2, 3)], "sol": [f"modelexp-sol-run{i}" for i in (1, 2, 3)]}
RETRIEVAL = ("other", "calendar_fallthrough")


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


def share(rows, field, good):
    judged = [r for r in rows if r[field] is not None]
    return sum(r[field] == good for r in judged) / len(judged) if judged else float("nan")


def metrics(run, ids):
    rows = [run[i] for i in ids]
    answerable = [r for r in rows if r["gold_kind"] in ("normal", "calendar_only", "no_advice")]
    abstain_gold = [r for r in rows if r["gold_kind"] == "abstain"]
    return {
        "correct": share(rows, "correctness", "correct"),
        "partial": share(rows, "correctness", "partial"),
        "faithful": share(rows, "faithfulness", "yes"),
        "wrongly_abstained": mean(r["abstained"] for r in answerable) if answerable else 0.0,
        "abstention_acc": mean(r["abstained"] for r in abstain_gold) if abstain_gold else float("nan"),
        "citation_rate": mean(bool(r["citations"]) and not r["invalid_citations"] for r in rows if not r["abstained"]),
        "invalid": sum(len(r["invalid_citations"]) for r in rows),
        "cost": mean(r["answer_cost"] for r in rows),
        "lat_median": median(r["latency_ms"] for r in rows),
    }


def main():
    rows = {q["id"]: q for q in load_questions() if q["split"] == "dev"}
    runs = {label: load(label) for labels in ARMS.values() for label in labels}
    ids = list(runs[ARMS["luna"][0]])
    primary = [i for i in ids if all(runs[l][i]["route"] in RETRIEVAL for l in runs)]
    print(f"38-question set: {len(ids)}; primary set (retrieval route in all six runs): {len(primary)}")
    print("primary ids:", " ".join(primary))
    print("answered by code or abstain-route in at least one run:", " ".join(i for i in ids if i not in primary))
    for name, sel in (("PRIMARY", primary), ("ALL 38 (reported, not used)", ids)):
        print(f"\n=== {name} ===")
        table = {arm: [metrics(runs[l], sel) for l in labels] for arm, labels in ARMS.items()}
        for key in table["luna"][0]:
            def fmt(arm):
                vals = [m[key] for m in table[arm]]
                return " ".join(f"{v:.4f}" for v in vals) + f" | mean {mean(vals):.4f}"
            print(f"{key:18} luna {fmt('luna')}   ||   sol {fmt('sol')}")
        if name == "PRIMARY":
            prim = table
    # length
    text = {l: answers(l, {i: rows[i]["question"] for i in primary}) for l in runs}
    words = {arm: mean(len(text[l][i].split()) for l in labels for i in primary) for arm, labels in ARMS.items()}
    print(f"\nmean answer length (words, primary): luna {words['luna']:.1f}, sol {words['sol']:.1f}, ratio {words['sol'] / words['luna']:.2f}")
    # rule
    L, S = prim["luna"], prim["sol"]
    gain = mean(m["correct"] for m in S) - mean(m["correct"] for m in L)
    wins = sum(s["correct"] > l["correct"] for s, l in zip(S, L, strict=True))
    one_q = 1 / len(primary)
    print("\n=== THE RULE ===")
    print(f"B1 gain {gain:+.4f} (need >= +0.05); sol higher in {wins} of 3 paired passes (need >= 2): {'PASS' if gain >= 0.05 and wins >= 2 else 'FAIL'}")
    d = mean(m["faithful"] for m in S) - mean(m["faithful"] for m in L)
    print(f"B2 faithfulness difference {d:+.4f} (need >= -0.03): {'PASS' if d >= -0.03 else 'FAIL'}")
    wa = mean(m["wrongly_abstained"] for m in S) - mean(m["wrongly_abstained"] for m in L)
    aa = mean(m["abstention_acc"] for m in S) - mean(m["abstention_acc"] for m in L)
    print(f"B3 wrongly-abstained difference {wa:+.4f} (need <= +{one_q:.4f}), abstention accuracy difference {aa:+.4f} (need >= -0.03): {'PASS' if wa <= one_q and aa >= -0.03 else 'FAIL'}")
    cr = mean(m["citation_rate"] for m in S) - mean(m["citation_rate"] for m in L)
    iv = mean(m["invalid"] for m in S) - mean(m["invalid"] for m in L)
    print(f"B4 citation rate difference {cr:+.4f} (need >= -0.03), invalid citations difference {iv:+.2f} (need <= 0): {'PASS' if cr >= -0.03 and iv <= 0 else 'FAIL'}")
    cs = mean(m["cost"] for m in S)
    print(f"B5 sol cost per retrieval-route request ${cs:.5f} (need <= $0.01); luna ${mean(m['cost'] for m in L):.5f}: {'PASS' if cs <= 0.01 else 'FAIL'}")
    ratio = words["sol"] / words["luna"]
    print(f"B6 length ratio {ratio:.2f} (need <= 1.30 or owner accepts): {'PASS' if ratio <= 1.3 else 'FLAG'}")
    borderline = 0.03 <= gain <= 0.07 or (wins == 2 and gain < 0.05)
    print(f"borderline (gain between 0.03 and 0.07, or 2 of 3 with gain < 0.05): {borderline}")
    # differing answers
    print("\n=== QUESTIONS WHERE THE ARMS DIFFER IN THE JUDGED VERDICT IN A MAJORITY OF PAIRED PASSES ===")
    full = {l: answers(l, {i: rows[i]["question"] for i in primary}) for l in runs}
    shown = 0
    for i in primary:
        diff = sum(
            (runs[s][i]["correctness"], runs[s][i]["faithfulness"]) != (runs[l][i]["correctness"], runs[l][i]["faithfulness"])
            for l, s in zip(ARMS["luna"], ARMS["sol"], strict=True)
        )
        verdicts = lambda arm: [f"{runs[l][i]['correctness'][:4]}/{runs[l][i]['faithfulness'] or '-'}" for l in ARMS[arm]]
        if diff >= 2:
            shown += 1
            print(f"\n##### {i} ({rows[i]['type']}): {rows[i]['question']}\ngold: {rows[i]['gold_answer']}")
            print("luna verdicts:", verdicts("luna"), " sol verdicts:", verdicts("sol"))
            for arm in ("luna", "sol"):
                l = ARMS[arm][0]
                r = runs[l][i]
                print(f"--- {arm} run1 answer ({len(full[l][i].split())} words) ---\n{full[l][i]}")
                print(f"    judge: {r['correctness']}: {r['correctness_reason']}\n    faithfulness {r['faithfulness']}: {r['faithfulness_reason']}")
    print(f"\n{shown} questions shown")
    if "--costs" in sys.argv:
        pass
    print("\n=== COST PER RUN (answer pipeline + judge, from the run files) ===")
    for l in runs:
        pq = runs[l].values()
        print(l, f"${sum(q['answer_cost'] + q['judge_cost'] for q in pq):.4f}")


if __name__ == "__main__":
    main()
