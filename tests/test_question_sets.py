"""Step 4a-1: merged calendar questions, question-set selection, comparing runs on common ids."""

import importlib.util
import json
from pathlib import Path

import pytest

from cta.eval import answer_compare as ac
from cta.eval import compare
from cta.eval.questions import load_questions, question_ids_record, select_questions
from tests.test_calendar_candidates import mcc

spec = importlib.util.spec_from_file_location(
    "merge_calendar_questions",
    Path(__file__).resolve().parents[1] / "scripts" / "merge_calendar_questions.py",
)
merge_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(merge_module)
merge = merge_module.merge

ROOT = Path(__file__).resolve().parents[1]
KEPT = ["q61", "q62", "q63", "q64", "q65", "q66", "q67", "q68", "q69", "q71", "q72", "q73", "q74",
        "q75"]  # fmt: skip
DEV = ["q61", "q63", "q64", "q65", "q67", "q68", "q71", "q75"]
TEST = ["q62", "q66", "q69", "q72", "q73", "q74"]


# ---- the real file ----


def calendar_rows():
    # q88 and later are the dev questions of the chain layout round (docs/chain-layout-plan.md)
    return [
        q for q in load_questions() if "calendar" in q.get("tags", []) and int(q["id"][1:]) <= 87
    ]


def test_the_14_approved_questions_are_merged_with_the_owner_split():
    rows = {q["id"]: q for q in calendar_rows()}
    assert sorted(rows) == KEPT and "q70" not in {q["id"] for q in load_questions()}
    assert sorted(i for i, q in rows.items() if q["split"] == "dev") == DEV
    assert sorted(i for i, q in rows.items() if q["split"] == "test") == TEST
    assert all(q["department"] is None for q in rows.values())


def test_every_gold_row_is_a_real_verified_calendar_event_and_is_in_its_heading():
    events = {
        e["id"]: e for e in json.loads((ROOT / "data/calendar/calendar_events.json").read_text())
    }
    for q in calendar_rows():
        for g in q["gold_sources"]:
            assert (
                g["source"] == "data/calendar/calendar_events.json" and events[g["id"]]["verified"]
            )
            assert g["heading"] == f"{events[g['id']]['term']}: {events[g['id']]['event']}"
            assert f"[{g['id']}]" in q["gold_answer"]


def test_special_gold_rules_of_the_new_questions():
    by_id = {q["id"]: q for q in calendar_rows()}
    assert by_id["q72"]["gold_answer"] == "ABSTAIN" and by_id["q72"]["gold_sources"] == []
    assert by_id["q72"]["type"] == "unanswerable"
    assert by_id["q74"]["gold_answer"].startswith("CLARIFY OR ALL BRANCHES:")
    assert by_id["q74"]["type"] == "ambiguous" and len(by_id["q74"]["gold_sources"]) == 6
    assert {g["id"] for g in by_id["q75"]["gold_sources"]} == {
        "fall-2026-046", "fall-2026-045", "fall-2026-047"}  # fmt: skip
    assert by_id["q69"]["question"] == "When is spring break this spring?"
    assert by_id["q75"]["question"] == "What days are off for Thanksgiving break?"
    assert "Assumed term: Fall 2026 (from today's date, 2026-10-11)" in by_id["q75"]["gold_answer"]


def test_the_old_baseline_questions_are_all_still_dev_and_unchanged_in_number():
    baseline = json.loads((ROOT / "eval/results/baseline-dev-60.json").read_text())
    ids = {r["id"] for r in baseline["per_question"]}
    dev = {q["id"] for q in load_questions() if q["split"] == "dev"}
    assert (
        len(ids) == 40 and ids <= dev and len(dev - ids) == 51
    )  # 8 calendar + 7 chain + 8 (q88-q95) + 8 tester round (q96-q103) + 19 casual (q104-q122)


# ---- selecting questions, recording the set ----

ROWS = [
    {"id": "a", "split": "dev", "tags": ["calendar"]},
    {"id": "b", "split": "dev"},
    {"id": "c", "split": "test", "tags": ["calendar"]},
]


def test_select_by_split_ids_and_tag():
    assert [q["id"] for q in select_questions(ROWS, "dev")] == ["a", "b"]
    assert [q["id"] for q in select_questions(ROWS, "dev", ids=["b"])] == ["b"]
    assert [q["id"] for q in select_questions(ROWS, "dev", tag="calendar")] == ["a"]
    assert [q["id"] for q in select_questions(ROWS, "test", tag="calendar")] == ["c"]


def test_an_id_outside_the_split_is_an_error_not_a_smaller_run():
    with pytest.raises(ValueError, match="not in the dev split: c, zz"):
        select_questions(ROWS, "dev", ids=["a", "c", "zz"])


def test_the_run_config_records_sorted_ids_and_an_order_free_hash():
    one = question_ids_record([{"id": "b"}, {"id": "a"}])
    two = question_ids_record([{"id": "a"}, {"id": "b"}])
    assert one == two and one["question_ids"] == ["a", "b"] and len(one["question_ids_hash"]) == 12
    assert question_ids_record([{"id": "a"}])["question_ids_hash"] != one["question_ids_hash"]


# ---- comparing runs on different question sets ----


def retrieval_run(label, ranks):
    rows = [{"id": i, "type": "lookup", "first_rank": r} for i, r in ranks.items()]
    zero = {"n": len(rows), **{m: 0.0 for m in compare.METRICS}}
    return {"label": label, "metrics": zero, "by_type": {}, "per_question": rows}


def test_retrieval_comparison_on_the_same_questions_says_so():
    old, new = retrieval_run("o", {"q1": 1, "q2": 3}), retrieval_run("n", {"q1": 1, "q2": 1})
    text = compare.report(old, new)
    assert "Same 2 scored questions in both runs." in text and "Improved (1): q2 (3->1)" in text


def test_retrieval_comparison_on_different_sets_uses_the_common_ids_only():
    old = retrieval_run("o", {"q1": 1, "q2": 3, "q9": 1})
    new = retrieval_run("n", {"q1": 2, "q2": 1, "q70": 1})
    text = compare.report(old, new)
    assert "scored different questions (3 before, 3 after)" in text
    assert "Only the 2 common ids" in text and "only in the old run: ['q9']" in text
    assert "only in the new run: ['q70']" in text
    assert "rule is not applied" in text and "KEEP" not in text and "REJECT" not in text
    # MRR on q1, q2: before (1 + 1/3) / 2, after (1/2 + 1) / 2
    assert "mrr" in text and "0.667" in text and "0.750" in text


def answer_run(label, ids, correctness="correct"):
    rows = [
        {"id": i, "type": "lookup", "gold_kind": "normal", "abstained": False, "citations": [1],
         "invalid_citations": [], "judge_status": "ok", "correctness": correctness,
         "faithfulness": "yes", "latency_ms": 1, "chat_ms": 1, "answer_cost": 0.0,
         "judge_cost": 0.0,
         "cache_hit": True, "label": None, "tags": []}
        for i in ids
    ]  # fmt: skip
    rows.append(dict(rows[0]) | {"id": "qa", "gold_kind": "abstain", "abstained": True,
                                 "faithfulness": None, "citations": []})  # fmt: skip
    return {"label": label, "per_question": rows, "answers": {}, "failure_labels": {}}


def test_answer_comparison_restricts_every_run_to_the_common_ids():
    runs = [answer_run("a", ["q1", "q2"]), answer_run("b", ["q1", "q2", "q3"], "partial")]
    assert ac.common_question_ids(runs) == ["q1", "q2", "qa"]
    small = ac.restrict(runs[1], ["q1", "q2"])
    assert [r["id"] for r in small["per_question"]] == ["q1", "q2"]
    assert (
        small["answers"]["correctness"]["n"] == 2
        and small["answers"]["correctness"]["partial"] == 1.0
    )


def test_answer_report_names_the_common_set_when_sizes_differ():
    off = [answer_run(f"off{i}", ["q1", "q2"]) for i in range(3)]
    on = [answer_run(f"on{i}", ["q1", "q2", "q3"]) for i in range(3)]
    text = ac.report(off, on, None, on[0])
    assert "different question sets (sizes [3, 4])" in text and "only the 3 common ids" in text
    assert "| q3 |" not in text and "| q1 |" in text


# ---- the merge script ----


def test_merge_appends_only_and_refuses_duplicates(tmp_path):
    path = tmp_path / "questions.jsonl"
    old = '{"id":"q01","note":"x"}\n'
    path.write_text(old)
    assert merge(path, [{"id": "q02", "a": 1}]) == ["q02"]
    assert path.read_text() == old + '{"id":"q02","a":1}\n'
    with pytest.raises(ValueError, match="already in"):
        merge(path, [{"id": "q02"}])
    assert path.read_text() == old + '{"id":"q02","a":1}\n'


def test_kept_rows_match_the_file():
    events = json.loads(mcc.CALENDAR.read_text(encoding="utf-8"))
    built = {r["id"]: r for r in mcc.kept_rows(events, None)}
    assert sorted(built) == KEPT
    for q in calendar_rows():
        for key in ("question", "gold_sources", "type", "split", "tags"):
            if q["id"] == "q33" and key == "gold_sources":
                continue  # refined by the owner after the 4a run (step 4a-2); see docs/decisions.md
            assert q[key] == built[q["id"]][key]
