"""Independent recomputation of the final-run headline numbers (docs/decisions.md, "Final run").

Plain Python: reads eval/results/<label>.json and eval/questions.jsonl, imports nothing from `cta`.
It recomputes retrieval metrics (recall@k, precision@k, hit rate, MRR), judged correctness and
faithfulness and abstention accuracy, overall, by question type and by department, and compares
them with the numbers the runner stored in the same file.

    python3 scripts/recompute_final.py final-run [merged.json]

merged.json (optional) maps a chunk id to the section ids merged into it (a table merged into its
parent section still counts for the table's own id). It is read from the database with:
    docker compose exec -T db psql -U cta -d cta -At -c "select coalesce(json_object_agg(id,
    merged_section_ids),'{}') from chunks where cardinality(merged_section_ids)>0"
The per-question results store only chunk ids, not the merged ids.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CALENDAR = re.compile(r"^(fall|winter|spring|summer)-\d{4}-\d+$")
KS = (1, 3, 5, 10)


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def retrieval_row(rec, gold_ids, merged):
    """Metrics of one question from its stored ranked chunk ids."""
    ranked = [c["id"] for c in rec["retrieved"]]
    stands = [({i, *merged.get(i, [])}) & gold_ids for i in ranked]  # gold ids each chunk stands for
    hit = [bool(x) for x in stands]
    first = next((n for n, h in enumerate(hit, 1) if h), None)
    row = {"mrr": 1 / first if first and first <= 10 else 0.0, "first": first}
    for k in KS:
        found = set().union(*stands[:k]) if stands[:k] else set()
        row[f"recall@{k}"] = len(found) / len(gold_ids)
        row[f"precision@{k}"] = sum(hit[:k]) / k
        row[f"hit@{k}"] = 1.0 if any(hit[:k]) else 0.0
    return row


def summarize(rows):
    names = [f"{m}@{k}" for k in KS for m in ("recall", "precision", "hit")] + ["mrr"]
    return {"n": len(rows)} | {n: mean([r[n] for r in rows]) for n in names}


def share(records, field, value):
    xs = [r[field] for r in records if r[field] is not None]
    return (sum(x == value for x in xs), len(xs))


def correctness_counts(records, owner_grades=None):
    """(n, correct, partial, incorrect) of the normal-gold questions; with owner grades (a dict
    id -> 'correct'|'partial'|'incorrect') the questions the harness left ungraded are added."""
    grades = [r["correctness"] for r in records if r["gold_kind"] == "normal"]
    for r in records:
        if owner_grades and r["id"] in owner_grades and r["correctness"] is None:
            grades.append(owner_grades[r["id"]])
    return (len(grades), *(grades.count(g) for g in ("correct", "partial", "incorrect")))


def main(label, merged_path=None):
    merged = json.loads(Path(merged_path).read_text()) if merged_path else {}
    results = json.loads((ROOT / "eval" / "results" / f"{label}.json").read_text())
    questions = {}
    for line in (ROOT / "eval" / "questions.jsonl").read_text().splitlines():
        q = json.loads(line)
        questions[q["id"]] = q
    recs = results["per_question"]
    scored, notes = [], []
    for r in recs:
        gold = list(dict.fromkeys(
            g["id"] for g in questions[r["id"]]["gold_sources"] if not CALENDAR.match(g["id"])
        ))
        excluded = r["id"] in results["excluded_from_retrieval"]
        if gold and not excluded:
            row = retrieval_row(r, set(gold), merged)
            scored.append({"id": r["id"], "type": r["type"], "dept": r["department"], **row})
            if row["first"] != r["first_gold_rank"]:
                notes.append(f"first gold rank {r['id']}: mine {row['first']}, runner {r['first_gold_rank']}")
        elif gold != [] and excluded:
            notes.append(f"{r['id']} has scorable gold but the runner excluded it")
        elif not gold and not excluded:
            notes.append(f"{r['id']} has no scorable gold but the runner scored it")
    print(f"== retrieval, my set n={len(scored)}, runner n={results['retrieval']['n']}")
    mine = summarize(scored)
    bad = 0
    for k, v in mine.items():
        theirs = results["retrieval"][k]
        flag = "" if abs(v - theirs) < 1e-6 else "  <-- MISMATCH"
        bad += bool(flag)
        print(f"  {k:14s} mine {v:.4f}  runner {theirs:.4f}{flag}" if k != "n" else f"  n mine {v} runner {theirs}{flag}")
    for group, key in (("type", "type"), ("department", "dept")):
        print(f"== retrieval by {group}")
        for g in sorted({str(s[key]) for s in scored}):
            rows = [s for s in scored if str(s[key]) == g]
            m = summarize(rows)
            print(f"  {g:14s} n={m['n']:2d} R@5 {m['recall@5']:.3f} P@5 {m['precision@5']:.3f} H@5 {m['hit@5']:.3f} MRR {m['mrr']:.3f}")
    normal = [r for r in recs if r["gold_kind"] == "normal"]
    answerable = [r for r in recs if r["gold_kind"] in ("normal", "no_advice")]
    abstain_gold = [r for r in recs if r["gold_kind"] == "abstain"]
    ans = results["answers"]
    print("== answers (normal gold)")
    for name in ("correct", "partial", "incorrect"):
        c, n = share(normal, "correctness", name)
        print(f"  correctness {name:9s} {c}/{n} = {c / n:.3f}")
    for name in ("yes", "partly", "no"):
        c, n = share(normal, "faithfulness", name)
        print(f"  faithfulness {name:6s} {c}/{n} = {c / n:.3f}")
    owner_path = ROOT / "eval" / "results" / f"{label}-owner-grades.json"
    owner = {}
    if owner_path.exists():
        owner = {k: v["correctness"] for k, v in json.loads(owner_path.read_text())["grades"].items()}
    n, c, p, i = correctness_counts(recs)
    print(f"== headline, harness-only:       n={n}  correct {c}  partial {p}  incorrect {i}")
    if owner:
        n, c, p, i = correctness_counts(recs, owner)
        print(f"== headline, with owner grades:  n={n}  correct {c}  partial {p}  incorrect {i}"
              f"  (owner grades for {sorted(owner)}, given after seeing results)")
    print(f"  runner (as printed in the stored summary): {json.dumps({k: ans[k] for k in ans if 'correct' in k or 'faith' in k})[:400]}")
    abst = sum(r["abstained"] for r in abstain_gold)
    print(f"== abstention accuracy {abst}/{len(abstain_gold)}; "
          f"wrongly abstained {sum(r['abstained'] for r in answerable)}/{len(answerable)}")
    print("== by type (all records): correctness counts")
    for t in sorted({r["type"] for r in recs}):
        sub = [r for r in recs if r["type"] == t]
        cnt = {}
        for r in sub:
            cnt[r["correctness"]] = cnt.get(r["correctness"], 0) + 1
        print(f"  {t:14s} n={len(sub):2d} {cnt}")
    print("== by department (all records): correctness counts")
    for d in sorted({str(r["department"]) for r in recs}):
        sub = [r for r in recs if str(r["department"]) == d]
        cnt = {}
        for r in sub:
            cnt[r["correctness"]] = cnt.get(r["correctness"], 0) + 1
        print(f"  {d:12s} n={len(sub):2d} {cnt}")
    cost = sum((r["answer_cost"] or 0) + (r["judge_cost"] or 0) + (r["rerank_cost"] or 0) for r in recs)
    lat = sorted(r["latency_ms"] for r in recs)
    print(f"== per-question costs summed (answer+judge+rerank): ${cost:.5f}, per request ${cost / len(recs):.5f}")
    print(f"== latency median {lat[len(lat) // 2]} ms, max {lat[-1]} ms")
    print("== notes:" if notes else "== no notes")
    for n in notes:
        print("  " + n)
    print(f"retrieval mismatches: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
