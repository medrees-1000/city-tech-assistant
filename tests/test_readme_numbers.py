"""scripts/readme_numbers.py: the counting functions on small data, and the committed test run."""

import importlib.util
from pathlib import Path

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
