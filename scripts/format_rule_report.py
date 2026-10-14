"""Step 5b (answer-prompt formatting rule): F1 to F6 from the stored runs (docs/decisions.md, "Step 5b" and its
addendum). Deterministic results and the judge's verdicts are printed separately.
    uv run python scripts/format_rule_report.py
"""

import hashlib
import json
from statistics import mean

from cta.eval import format_check as fc
from cta.eval.questions import load_questions
from cta.settings import ROOT

from model_exp_report import answers, load, share  # scripts/ is on the path when run as a script

BEFORE = [f"modelexp-luna-run{i}" for i in (1, 2, 3)]
ON = [f"fmt-on-run{i}" for i in (1, 2, 3)]
PRIMARY = ("q01 q03 q04 q05 q06 q08 q13 q14 q15 q16 q18 q19 q24 q27 q28 q44 q45 q47 q49 q51 q52 q53 "
           "q54 q56 q57 q58 q59 q87").split()  # fmt: skip
CODE_ROUTES = ("calendar", "chain", "abstain")


def main():
    rows = {q["id"]: q for q in load_questions() if q["split"] == "dev"}
    runs = {label: load(label) for label in BEFORE + ON}
    ids = list(runs[BEFORE[0]])
    text = {label: answers(label, {i: rows[i]["question"] for i in ids}) for label in runs}

    print("=== DETERMINISTIC RESULTS (no judge) ===")
    # F1 on q13, F3 on q13, F2 on the other 27
    before13 = [text[label]["q13"] for label in BEFORE]
    f1_ok = f3_ok = True
    for label in ON:
        ok1, why1 = fc.f1(text[label]["q13"], before13)
        ok3, why3 = fc.f3(text[label]["q13"])
        f1_ok &= ok1
        f3_ok &= ok3
        print(f"F1 {label} q13: {'PASS' if ok1 else 'FAIL'} ({why1}); F3: {'PASS' if ok3 else 'FAIL'}")
    print(f"F1 over three passes: {'PASS' if f1_ok else 'FAIL'}; F3: {'PASS' if f3_ok else 'FAIL'}")
    f2_fail = []
    for label in ON:
        for i in PRIMARY:
            if i == "q13":
                continue
            ok, why = fc.f2(text[label][i])
            if not ok:
                f2_fail.append((label, i, why))
    print(f"F2 (27 questions x 3 passes): {'PASS' if not f2_fail else 'FAIL'} {f2_fail}")
    bullets = {i: [len(fc.bullet_lines(text[label][i])) for label in ON] for i in PRIMARY}
    print("bullet lines per on pass, questions with any bullet:", {i: v for i, v in bullets.items() if any(v)})
    # F6 hash check of code-route answers
    code_ids = [i for i in ids if all(runs[label][i]["route"] in CODE_ROUTES for label in BEFORE + ON)]
    same = {i: len({hashlib.sha256(text[label][i].encode()).hexdigest() for label in BEFORE + ON}) == 1 for i in code_ids}
    print(f"F6 code-route answers byte-identical in all six runs: {sum(same.values())} of {len(code_ids)} questions {[i for i, v in same.items() if not v]}")
    moved = [i for i in ids if len({runs[label][i]["route"] for label in BEFORE + ON}) > 1]
    print("questions whose route differs between runs:", moved)

    print("\n=== THE JUDGE'S VERDICTS (primary set, 28) ===")
    def m(label):
        pq = [runs[label][i] for i in PRIMARY]
        answerable = [r for r in pq if r["gold_kind"] in ("normal", "calendar_only", "no_advice")]
        abst = [r for r in pq if r["gold_kind"] == "abstain"]
        return {"correct": share(pq, "correctness", "correct"), "faithful": share(pq, "faithfulness", "yes"),
                "wrongly_abstained": mean(r["abstained"] for r in answerable),
                "abstention_acc": mean(r["abstained"] for r in abst),
                "cost": mean(r["answer_cost"] for r in pq)}  # fmt: skip
    table = {arm: [m(label) for label in labels] for arm, labels in (("before", BEFORE), ("on", ON))}
    for key in table["before"][0]:
        fmt = lambda arm: " ".join(f"{x[key]:.4f}" for x in table[arm]) + f" | mean {mean(x[key] for x in table[arm]):.4f}"
        print(f"{key:18} before {fmt('before')}   ||   on {fmt('on')}")
    c, f = (mean(x[k] for x in table["on"]) for k in ("correct", "faithful"))
    print(f"F4 correct {c:.4f} (need >= 0.893): {'PASS' if c >= 0.893 else 'FAIL'}; faithful {f:.4f} (need >= 0.907): {'PASS' if f >= 0.907 else 'FAIL'}")
    wa = mean(x["wrongly_abstained"] for x in table["on"])
    aa = mean(x["abstention_acc"] for x in table["on"])
    print(f"F5 wrongly-abstained {wa:.4f} (need <= 0.091), abstention accuracy {aa:.4f} (need >= 0.97): {'PASS' if wa <= 0.0911 and aa >= 0.97 else 'FAIL'}")
    words = {arm: mean(len(text[label][i].split()) for label in labels for i in PRIMARY) for arm, labels in (("before", BEFORE), ("on", ON))}
    print(f"mean answer length (words): before {words['before']:.1f}, on {words['on']:.1f}; cost per request: before ${mean(x['cost'] for x in table['before']):.5f}, on ${mean(x['cost'] for x in table['on']):.5f}")
    print("F6 retrieval metrics: unchanged by construction (the prompt acts after retrieval)")

    print("\n=== q13 BEFORE (luna, run 1) AND AFTER (rule on, run 1) ===")
    print(f"--- before ---\n{text[BEFORE[0]]['q13']}\n--- after, three passes ---")
    for label in ON:
        print(f"[{label}]\n{text[label]['q13']}\n")
    print("\n=== QUESTIONS WHERE THE JUDGED VERDICT DIFFERS IN A MAJORITY OF PAIRED PASSES ===")
    shown = 0
    for i in PRIMARY:
        verdict = lambda label: (runs[label][i]["correctness"], runs[label][i]["faithfulness"])
        diff = sum(verdict(b) != verdict(o) for b, o in zip(BEFORE, ON, strict=True))
        if diff >= 2:
            shown += 1
            tag = lambda label: f"{runs[label][i]['correctness'][:4]}/{runs[label][i]['faithfulness'] or '-'}"
            print(f"\n##### {i}: {rows[i]['question']}\ngold: {rows[i]['gold_answer']}\nbefore {[tag(b) for b in BEFORE]} on {[tag(o) for o in ON]}")
            for arm, label in (("before", BEFORE[0]), ("on", ON[0])):
                r = runs[label][i]
                print(f"--- {arm} run1 answer ---\n{text[label][i]}\n    judge: {r['correctness']}: {r['correctness_reason']}\n    faithfulness {r['faithfulness']}: {r['faithfulness_reason']}")
    print(f"\n{shown} questions shown")
    print("\n=== COST PER RUN ===")
    for label in ON:
        print(label, f"${sum(q['answer_cost'] + q['judge_cost'] for q in runs[label].values()):.4f}")


if __name__ == "__main__":
    main()
