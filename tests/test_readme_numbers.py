"""The scripts that reproduce the README numbers: the counting functions of
scripts/readme_numbers.py on small data and on the committed test run, and the headline arithmetic
of scripts/recompute_final.py (harness-only and with owner grades).
"""

import importlib.util
from pathlib import Path

# ---- from test_readme_numbers.py ----
#
# scripts/readme_numbers.py: the counting functions on small data, and the committed test run.

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "scripts" / "readme_numbers.py"
SPEC = importlib.util.spec_from_file_location("readme_numbers", PATH)
numbers = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(numbers)


def rec(i, kind, correctness=None, faith=None, abstained=False, rank=None, tags=()):
    return {"id": i, "gold_kind": kind, "correctness": correctness, "faithfulness": faith,
            "abstained": abstained, "first_gold_rank": rank, "tags": list(tags)}  # fmt: skip


RECORDS = [
    rec("a", "normal", "correct", "yes", rank=1), rec("b", "normal", "partial", "yes", rank=4),
    rec("c", "normal", "correct", "no", rank=None, abstained=True),
    rec("d", "abstain", "correct", abstained=True), rec("e", "abstain", "incorrect"),
    rec("f", "clarify"), rec("g", "no_advice", "correct"),
]  # fmt: skip


def test_correctness_counts_use_normal_gold_and_add_owner_grades_only_when_ungraded():
    assert numbers.correctness_counts(RECORDS) == (3, 2, 1, 0)
    assert numbers.correctness_counts(RECORDS, {"f": "partial", "a": "incorrect"}) == (4, 2, 2, 0)


def test_faithfulness_abstention_and_rank_metrics():
    assert numbers.faithfulness_counts(RECORDS) == (3, 2)
    assert numbers.abstention(RECORDS) == (2, 1, 4, 1)  # 2 abstain-gold, 1 abstained; 1 of 4 wrong
    n, hit5, mrr = numbers.rank_metrics(RECORDS, excluded=["f", "g"])
    assert n == 3 and hit5 == 2 / 3 and mrr == (1 + 0.25 + 0) / 3


def test_filters_by_ids_and_tags():
    tagged = [rec("x", "normal", tags=("casual",)), rec("y", "normal")]
    assert [r["id"] for r in numbers.by_filter(tagged, tag="casual")] == ["x"]
    assert [r["id"] for r in numbers.by_filter(tagged, ids={"y"})] == ["y"]


def test_the_committed_final_run_gives_the_reported_numbers():
    run = numbers.load("final-run")
    owner = {"q50": "correct", "q74": "partial"}
    assert numbers.correctness_counts(run["per_question"]) == (13, 10, 3, 0)
    assert numbers.correctness_counts(run["per_question"], owner) == (15, 11, 4, 0)
    assert numbers.faithfulness_counts(run["per_question"]) == (13, 13)
    assert numbers.abstention(run["per_question"]) == (7, 7, 14, 0)
    assert numbers.rank_metrics(run["per_question"], run["excluded_from_retrieval"])[0] == 14


def test_assistant_cost_does_not_count_the_reranker_twice():
    run = numbers.load("final-run")["per_question"]
    cost = numbers.product_cost(run)
    assert abs(cost - 0.00040) < 0.000005
    # answer_cost already holds the rerank call: adding rerank_cost would give about 0.00058
    assert sum(r["answer_cost"] + r["rerank_cost"] for r in run) / len(run) > 0.00055
    assert cost == sum(r["answer_cost"] for r in run) / len(run)


def test_casual_group_counts():
    dev = numbers.load("final-config-dev")["per_question"]
    casual = numbers.by_filter(dev, tag="casual")
    assert len(casual) == 20
    assert numbers.correctness_counts(casual) == (15, 4, 1, 10)
    normal = [r for r in casual if r["gold_kind"] == "normal"]
    assert sum(r["abstained"] for r in normal) == 10


def test_the_compact_dev_table_has_the_four_rows(capsys):
    numbers.table_dev_compact("final-config-dev")
    rows = [line for line in capsys.readouterr().out.splitlines() if line.startswith("| ")]
    assert len(rows) == 5  # header and four runs
    assert "| Final configuration, all 91 questions | 52 | 34 (65%) | 95% | 0.87 |" in rows


# ---- from test_recompute_final.py ----
#
# The headline arithmetic of scripts/recompute_final.py (harness-only and with owner grades).

RECOMPUTE_SPEC = importlib.util.spec_from_file_location(
    "recompute_final", Path(__file__).resolve().parent.parent / "scripts" / "recompute_final.py"
)
recompute = importlib.util.module_from_spec(RECOMPUTE_SPEC)
RECOMPUTE_SPEC.loader.exec_module(recompute)


def recompute_rec(i, kind, correctness):
    return {"id": i, "gold_kind": kind, "correctness": correctness}


RECOMPUTE_RECORDS = [
    recompute_rec("a", "normal", "correct"), recompute_rec("b", "normal", "partial"),
    recompute_rec("c", "normal", "correct"), recompute_rec("d", "abstain", "correct"),
    recompute_rec("e", "clarify", None), recompute_rec("f", "clarify", None),
]  # fmt: skip


def test_harness_only_counts_the_normal_gold_questions():
    assert recompute.correctness_counts(RECOMPUTE_RECORDS) == (3, 2, 1, 0)


def test_owner_grades_are_added_only_for_ungraded_questions():
    owner = {"e": "correct", "f": "partial", "a": "incorrect"}  # a is graded: owner grade ignored
    assert recompute.correctness_counts(RECOMPUTE_RECORDS, owner) == (5, 3, 2, 0)


def test_the_stored_final_run_gives_10_3_0_and_11_4_0():
    import json

    root = Path(__file__).resolve().parent.parent / "eval" / "results"
    recs = json.loads((root / "final-run.json").read_text())["per_question"]
    owner = json.loads((root / "final-run-owner-grades.json").read_text())["grades"]
    grades = {k: v["correctness"] for k, v in owner.items()}
    assert recompute.correctness_counts(recs) == (13, 10, 3, 0)
    assert recompute.correctness_counts(recs, grades) == (15, 11, 4, 0)
