"""Print the tables the README needs, from the committed files in eval/results/ only.

    python3 scripts/readme_numbers.py [--dev-label final-config-dev]

Stdlib only. It reads no question file, so it never touches the test questions; the test numbers
come from final-run.json, final-run-pass2.json and final-run-owner-grades.json.
"""

import argparse
import json
from pathlib import Path
from statistics import median

RESULTS = Path(__file__).resolve().parent.parent / "eval" / "results"
GRADES = ("correct", "partial", "incorrect")
ANSWERABLE = ("normal", "no_advice")  # the runner's "wrongly abstained" denominator


def load(label: str) -> dict:
    return json.loads((RESULTS / f"{label}.json").read_text(encoding="utf-8"))


def correctness_counts(records: list[dict], owner: dict | None = None) -> tuple[int, ...]:
    """(n, correct, partial, incorrect) over the normal-gold questions; owner grades (id ->
    grade) are added only for questions the harness left ungraded."""
    grades = [r["correctness"] for r in records if r["gold_kind"] == "normal"]
    grades += [owner[r["id"]] for r in records if owner and r["id"] in owner and not r["correctness"]]
    return (len(grades), *(grades.count(g) for g in GRADES))


def faithfulness_counts(records: list[dict]) -> tuple[int, int]:
    """(n, yes) over the normal-gold questions."""
    values = [r["faithfulness"] for r in records if r["gold_kind"] == "normal"]
    return len(values), values.count("yes")


def abstention(records: list[dict]) -> tuple[int, int, int, int]:
    """(abstain-gold n, abstained, answerable n, wrongly abstained)."""
    gold = [r for r in records if r["gold_kind"] == "abstain"]
    answerable = [r for r in records if r["gold_kind"] in ANSWERABLE]
    return (len(gold), sum(r["abstained"] for r in gold), len(answerable),
            sum(r["abstained"] for r in answerable))  # fmt: skip


def rank_metrics(records: list[dict], excluded: list[str]) -> tuple[int, float, float]:
    """(n, hit@5, MRR) from the stored first gold rank of the retrieval-scored questions."""
    scored = [r for r in records if r["id"] not in excluded and r["gold_kind"] != "abstain"]
    ranks = [r["first_gold_rank"] for r in scored]
    n = len(ranks)
    hit5 = sum(1 for k in ranks if k is not None and k <= 5) / n
    mrr = sum(1 / k for k in ranks if k is not None and k <= 10) / n
    return n, hit5, mrr


def product_cost(records: list[dict]) -> float:
    """Mean cost of one request to the assistant, no judge. The runner's answer_cost already holds
    the classifier, the calendar selector, the reranker, the answer call and the query embedding,
    so nothing is added to it (adding rerank_cost would count the reranker twice)."""
    return sum(r["answer_cost"] or 0 for r in records) / len(records)


def without_tag(records: list[dict], tag: str) -> list[dict]:
    return [r for r in records if tag not in r["tags"]]


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def table_final() -> None:
    run, pass2, owner_file = load("final-run"), load("final-run-pass2"), None
    owner_file = json.loads((RESULTS / "final-run-owner-grades.json").read_text(encoding="utf-8"))
    owner = {k: v["correctness"] for k, v in owner_file["grades"].items()}
    recs, a, r = run["per_question"], run["answers"], run["retrieval"]
    print("### (a) Final test run, 31 questions, code frozen at the tag final-run-frozen (final-run)\n")
    print("| Answer correctness (normal-gold questions) | n | correct | partial | incorrect |")
    print("|---|---|---|---|---|")
    n, c, p, i = correctness_counts(recs)
    print(f"| harness-only | {n} | {c} | {p} | {i} |")
    n, c, p, i = correctness_counts(recs, owner)
    print(f"| with owner grades for q50, q74 (owner-graded after seeing results) | {n} | {c} | {p} | {i} |")
    fn, fy = faithfulness_counts(recs)
    an, ab, wn, ww = abstention(recs)
    print(f"\n- Faithfulness (judge says the answer is supported by its sources): {fy} of {fn}")
    print(f"- Abstention on questions that must abstain: {ab} of {an}; wrongly abstained: {ww} of {wn}")
    print(f"- Citation rate: {a['citation_rate']['share']:.2f} (n={a['citation_rate']['n']}), "
          f"invalid citations {a['citation_rate']['invalid_citations']}")  # fmt: skip
    print(f"- Retrieval on the {r['n']} retrieval-scored questions: recall@5 {r['recall@5']:.3f}, "
          f"precision@5 {r['precision@5']:.3f}, hit@5 {r['hit@5']:.3f}, MRR {r['mrr']:.3f}")  # fmt: skip
    lat, cost = a["latency_ms"], a["cost"]
    print(f"- Cost of one request to the assistant (classifier, selector, reranker, answer call and query embedding; no judge): ${product_cost(recs):.5f}")
    print(f"- Cost of the whole eval run including the judge: ${cost['answer_usd'] + cost['judge_usd']:.3f} "
          f"(${cost['per_request_usd']:.4f} per request; answers ${cost['answer_usd']:.4f}, judge ${cost['judge_usd']:.4f})")  # fmt: skip
    print(f"- Latency: median {lat['total_median'] / 1000:.1f} s, p95 {lat['total_p95'] / 1000:.1f} s")
    rows = pass2["per_question"]
    same = sum(x["pass1"] == x["pass2"] for x in rows)
    diff = [x["id"] for x in rows if x["pass1"] != x["pass2"]]
    print(f"- Judge pass 2 (same judge, same rubric, answers re-judged): {same} of {len(rows)} questions "
          f"agree on both verdicts; differs: {', '.join(diff) or 'none'} "
          f"(the log stores the answer with public contact details redacted, so pass 2 saw redacted text)")  # fmt: skip
    print(f"- Judge cost pass 2: ${pass2['judge_cost_usd']:.4f}")


def by_filter(records: list[dict], ids: set[str] | None = None, tag: str | None = None) -> list[dict]:
    return [r for r in records if (ids is None or r["id"] in ids) and (tag is None or tag in r["tags"])]


def summary_row(name: str, records: list[dict], excluded: list[str]) -> str:
    n, c, p, i = correctness_counts(records)
    fn, fy = faithfulness_counts(records)
    an, ab, wn, ww = abstention(records)
    _, hit5, mrr = rank_metrics(records, excluded)
    return (f"| {name} | {n} | {c} ({pct(c / n)}) | {p} | {i} | {fy} of {fn} | {ab} of {an} | "
            f"{ww} of {wn} | {pct(hit5)} | {mrr:.2f} |")  # fmt: skip


def table_dev(dev_label: str) -> None:
    base, final = load("baseline-dev-60-v3"), load(dev_label)
    base_ids = {r["id"] for r in base["per_question"]}
    print("\n### (b) Development set (the set I tuned on)\n")
    print("| Run | n normal | correct | partial | incorrect | faithful | abstained when it must | wrongly abstained | hit@5 | MRR |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    print(summary_row(f"Phase 2 baseline ({len(base_ids)} dev questions, vector search only, rubric v3)",
                      base["per_question"], base["excluded_from_retrieval"] if "excluded_from_retrieval" in base else []))  # fmt: skip
    ex = final["excluded_from_retrieval"]
    print(summary_row("Final configuration, the same questions", by_filter(final["per_question"], base_ids), ex))
    print(summary_row(f"Final configuration, all {len(final['per_question'])} dev questions", final["per_question"], ex))
    print(summary_row("Final configuration, dev questions without the casual-wording group", without_tag(final["per_question"], "casual"), ex))
    a = final["answers"]
    print(f"\n- Final dev run `{dev_label}`: cost of one request to the assistant ${product_cost(final['per_question']):.5f}, "
          f"median latency {a['latency_ms']['total_median'] / 1000:.1f} s, p95 {a['latency_ms']['total_p95'] / 1000:.1f} s")  # fmt: skip
    print(f"- Retrieval on its {final['retrieval']['n']} scored questions: recall@5 {final['retrieval']['recall@5']:.3f}, "
          f"precision@5 {final['retrieval']['precision@5']:.3f}, hit@5 {final['retrieval']['hit@5']:.3f}, MRR {final['retrieval']['mrr']:.3f}")  # fmt: skip


def table_compare(dev_label: str) -> None:
    final, dev = load("final-run"), load(dev_label)
    print("\n### (c) Test against dev (final configuration)\n")
    print("| Set | n normal | correct | faithful | recall@5 | hit@5 | MRR | wrongly abstained |")
    print("|---|---|---|---|---|---|---|---|")
    for name, run in (("dev (the set I tuned on)", dev), ("test (final run, code frozen)", final)):
        n, c, p, i = correctness_counts(run["per_question"])
        fn, fy = faithfulness_counts(run["per_question"])
        _, _, wn, ww = abstention(run["per_question"])
        r = run["retrieval"]
        print(f"| {name} | {n} | {c} ({pct(c / n)}) | {fy} of {fn} | {r['recall@5']:.2f} | {r['hit@5']:.2f} | {r['mrr']:.2f} | {ww} of {wn} |")  # fmt: skip
    plain = without_tag(dev["per_question"], "casual")
    n, c, p, i = correctness_counts(plain)
    fn, fy = faithfulness_counts(plain)
    _, _, wn, ww = abstention(plain)
    _, hit5, mrr = rank_metrics(plain, dev["excluded_from_retrieval"])
    print(f"| dev without the casual-wording group | {n} | {c} ({pct(c / n)}) | {fy} of {fn} | n/a | {hit5:.2f} | {mrr:.2f} | {ww} of {wn} |")  # fmt: skip


def table_casual(dev_label: str) -> None:
    dev, b0 = load(dev_label), load("casual-b0")
    print("\n### (d) Casual wording\n")
    casual = by_filter(dev["per_question"], tag="casual")
    normal = [r for r in casual if r["gold_kind"] == "normal"]
    rest = [r for r in casual if r["gold_kind"] != "normal"]
    n, c, p, i = correctness_counts(casual)
    refused = sum(r["abstained"] for r in normal)
    rest_ok = sum(r["correctness"] == "correct" for r in rest)
    print(f"- The casual group is the {len(casual)} dev questions tagged `casual` (q104 to q123), in `{dev_label}`.")
    print(f"- Fact questions (normal gold, n={n}): correct {c}, partial {p}, incorrect {i}; "
          f"refused {refused} of {n}")  # fmt: skip
    print(f"- The other {len(rest)} casual questions are scored by rule (clarify, no advice, calendar-only, must-abstain): "
          f"{rest_ok} of {len(rest)} correct")  # fmt: skip
    print(f"- All {len(casual)} together: {c + rest_ok} of {len(casual)} pass")
    bn, bc, _, _ = correctness_counts(b0["per_question"])
    print(f"- Baseline of the casual round (`casual-b0`, run before q123 was added, {len(b0['per_question'])} questions): "
          f"{bc} of {bn} fact questions correct ({pct(bc / bn)})")  # fmt: skip
    print("- \"Wrongly abstained\" in the dev tables is the runner's term: abstained questions among the answerable set "
          "(fact questions plus the no-advice question), so its denominator is one larger than the fact-question count.")  # fmt: skip


def table_routes(dev_label: str) -> None:
    print("\n### (f) Cost and latency by route (whole request to the assistant, no judge)\n")
    print("| Route | requests (dev + test) | median cost | median latency (ms) |")
    print("|---|---|---|---|")
    recs = load(dev_label)["per_question"] + load("final-run")["per_question"]
    for route in sorted({r["route"] or "none" for r in recs}):
        sub = [r for r in recs if (r["route"] or "none") == route]
        costs = [r["answer_cost"] or 0 for r in sub]
        print(f"| {route} | {len(sub)} | ${median(costs):.5f} | {median(r['latency_ms'] for r in sub):.0f} |")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dev-label", default="final-config-dev")
    args = p.parse_args()
    table_final()
    table_dev(args.dev_label)
    table_compare(args.dev_label)
    table_casual(args.dev_label)
    table_routes(args.dev_label)


if __name__ == "__main__":
    main()
