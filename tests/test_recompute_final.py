"""The headline arithmetic of scripts/recompute_final.py (harness-only and with owner grades)."""

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "recompute_final", Path(__file__).resolve().parent.parent / "scripts" / "recompute_final.py"
)
recompute = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recompute)


def rec(i, kind, correctness):
    return {"id": i, "gold_kind": kind, "correctness": correctness}


RECORDS = [
    rec("a", "normal", "correct"), rec("b", "normal", "partial"), rec("c", "normal", "correct"),
    rec("d", "abstain", "correct"), rec("e", "clarify", None), rec("f", "clarify", None),
]  # fmt: skip


def test_harness_only_counts_the_normal_gold_questions():
    assert recompute.correctness_counts(RECORDS) == (3, 2, 1, 0)


def test_owner_grades_are_added_only_for_ungraded_questions():
    owner = {"e": "correct", "f": "partial", "a": "incorrect"}  # a is graded: owner grade ignored
    assert recompute.correctness_counts(RECORDS, owner) == (5, 3, 2, 0)


def test_the_stored_final_run_gives_10_3_0_and_11_4_0():
    import json

    root = Path(__file__).resolve().parent.parent / "eval" / "results"
    recs = json.loads((root / "final-run.json").read_text())["per_question"]
    owner = json.loads((root / "final-run-owner-grades.json").read_text())["grades"]
    grades = {k: v["correctness"] for k, v in owner.items()}
    assert recompute.correctness_counts(recs) == (13, 10, 3, 0)
    assert recompute.correctness_counts(recs, grades) == (15, 11, 4, 0)
