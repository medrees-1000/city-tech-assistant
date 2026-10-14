"""Step 2 (two-course questions): J1 evaluated condition by condition (docs/decisions.md, "Step 2 ... keep rule").
Deterministic results and the judge's verdicts are printed separately.   uv run python scripts/chain2_report.py
"""

import hashlib
import json

from cta.eval.chain_report import coverage, gold_catalog
from cta.eval.questions import load_questions
from cta.index.db import connect
from cta.redact import redact
from cta.settings import ROOT

R = ROOT / "eval" / "results"
NEW = ["chain2-run1", "chain2-run2"]
OLD = ["chain-code-run1", "chain-code-run2"]  # step 1 code runs (8 earlier CH answers)
CH = ["q22", "q39", "q40", "q76", "q77", "q79", "q81", "q85", "q93", "q94"]
EARLIER = CH[:8]


def load(label):
    return {q["id"]: q for q in json.loads((R / f"{label}.json").read_text())["per_question"]}


def answer(label, question):
    with connect() as conn:
        run_id = conn.execute("SELECT id FROM eval_runs WHERE label = %s", (label,)).fetchone()[0]
        return conn.execute(
            "SELECT answer FROM request_logs WHERE run_id = %s AND question = %s ORDER BY id DESC LIMIT 1",
            (run_id, redact(question)),
        ).fetchone()[0]


def main():
    rows = {q["id"]: q for q in load_questions() if q["split"] == "dev"}
    new = {l: load(l) for l in NEW}
    old = {l: load(l) for l in OLD}
    print("=== DETERMINISTIC RESULTS (no judge) ===")
    for l, run in new.items():
        print(f"M1 {l}: {sum(run[i]['route'] == 'chain' for i in CH)} of {len(CH)} CH questions answered by the chain node")
    for l, run in new.items():
        routed = sorted(i for i, q in run.items() if q["route"] == "chain" and i not in CH)
        print(f"R1 {l}: q87 route={run['q87']['route']}; non-CH ids answered by the chain node: {routed}")
    many = [i for i in CH if len(gold_catalog(rows[i])) >= 2]
    for l, run in new.items():
        got = {i: run[i]["router"]["chain"]["source_ids"] for i in CH if run[i]["route"] == "chain"}
        cov = {i: coverage(got.get(i, []), gold_catalog(rows[i])) for i in many}
        n = sum(cov.values())
        print(f"M3 {l}: {n} of {len(many)} = {n / len(many):.2f} (missing: {[i for i, v in cov.items() if not v]})")
    for l, run in new.items():
        r = run["q83"]
        print(f"M6 {l}: q83 abstained={r['abstained']} route={r['route']}")
    same = {i: answer(NEW[0], rows[i]["question"]) == answer(NEW[1], rows[i]["question"]) for i in CH + ["q42"]}
    print("two runs identical text:", same)
    # K2 hashes: the single-course render at f6cdbdc (after C1/C2); the step 1 runs predate C1/C2 (they still say "chain")
    golden = json.loads((ROOT / "tests/fixtures/chain_single_render_sha256.json").read_text())["sha256"]
    for l, run in new.items():
        ok = {}
        for i in EARLIER:
            code = run[i]["router"]["chain"]["code"]
            ok[i] = hashlib.sha256(answer(l, rows[i]["question"]).encode()).hexdigest() == golden[code]
        print(f"earlier 8 CH answers equal the f6cdbdc hash, {l}: {sum(ok.values())} of 8 {[i for i, v in ok.items() if not v]}")
    print(f"step 1 runs ({OLD[0]}) still contain the word 'chain' (predate C1): {sum('chain' in answer(OLD[0], rows[i]['question']).lower() for i in EARLIER)} of 8")

    print("\n=== THE JUDGE'S VERDICTS ===")
    for i in CH + ["q42", "q21", "q83", "q87"]:
        print(f"  {i}: " + " | ".join(f"{new[l][i]['correctness']}/{new[l][i]['faithfulness'] or '-'}" for l in NEW))
    for l, run in new.items():
        bad = [i for i in ("q93", "q94") if run[i]["faithfulness"] != "yes" or run[i]["correctness"] == "incorrect"]
        print(f"q93/q94 faithful yes and not incorrect, {l}: {not bad} {bad}")
        print(f"q42 {l}: {run['q42']['correctness']} (J1 fails only if 'incorrect')")

    print("\n=== q42, q93, q94: ANSWERS AND JUDGE REASONS ===")
    for i in ("q42", "q93", "q94"):
        print(f"\n##### {i}: {rows[i]['question']}")
        for l in NEW:
            print(f"--- {l} answer ---\n{answer(l, rows[i]['question'])}")
            r = new[l][i]
            print(f"--- {l} judge: correctness={r['correctness']}: {r['correctness_reason']}\n    faithfulness={r['faithfulness']}: {r['faithfulness_reason']}")


if __name__ == "__main__":
    main()
