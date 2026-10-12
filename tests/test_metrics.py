import pytest

from cta.eval import run_retrieval as rr
from cta.eval.metrics import average, question_metrics, scorable_gold


def chunk(source_id, merged=()):
    return {"source_id": source_id, "merged_section_ids": list(merged)}


def ranked(*ids):
    return [chunk(i) for i in ids] + [chunk(f"filler{n}") for n in range(10 - len(ids))]


def test_hit_at_rank_1():
    m = question_metrics(ranked("g"), ["g"])
    assert (m["first_rank"], m["mrr"], m["hit@1"], m["recall@1"], m["precision@1"]) == (
        1,
        1,
        1,
        1,
        1,
    )


def test_hit_at_rank_4():
    m = question_metrics(ranked("x", "y", "z", "g"), ["g"])
    assert m["first_rank"] == 4 and m["mrr"] == 0.25
    assert (m["hit@3"], m["hit@5"], m["recall@3"], m["recall@5"]) == (0, 1, 0, 1)
    assert m["precision@5"] == pytest.approx(0.2)


def test_miss():
    m = question_metrics(ranked("x", "y"), ["g"])
    assert m["first_rank"] is None and m["mrr"] == 0 and m["hit@10"] == 0 and m["recall@10"] == 0


def test_two_gold_only_one_found():
    m = question_metrics(ranked("a", "x"), ["a", "b"])
    assert m["recall@10"] == 0.5 and m["recall@1"] == 0.5 and m["hit@10"] == 1


def test_match_through_merged_section_ids():
    chunks = [chunk("parent", merged=["table-section"])] + ranked()[:9]
    m = question_metrics(chunks, ["table-section"])
    assert m["first_rank"] == 1 and m["recall@1"] == 1


def test_calendar_id_is_ignored():
    q = {"gold_sources": [{"id": "fall-2026-044"}, {"id": "page/a/b#1"}, {"id": "winter-2027-023"}]}
    assert scorable_gold(q) == ["page/a/b#1"]
    assert scorable_gold({"gold_sources": [{"id": "spring-2027-043"}]}) == []


def test_no_scorable_gold_is_excluded():
    assert question_metrics(ranked("x"), []) is None
    questions = [
        {"id": "q1", "type": "lookup", "department": None, "gold_sources": [{"id": "g"}]},
        {"id": "q2", "type": "unanswerable", "department": None, "gold_sources": []},
        {"id": "q3", "type": "time_sensitive", "department": None,
         "gold_sources": [{"id": "spring-2027-043"}]},
    ]  # fmt: skip
    scored, excluded = rr.score(questions, {q["id"]: ranked("g") for q in questions})
    assert [r["id"] for r in scored] == ["q1"] and excluded == ["q2", "q3"]


def test_precision_for_a_single_gold_source_is_at_most_one_over_k():
    m = question_metrics(ranked("g"), ["g"])
    assert m["precision@3"] == pytest.approx(1 / 3) and m["precision@10"] == pytest.approx(0.1)
    # the same chunk listed twice would still count once per chunk, never above hits / k
    assert m["precision@5"] <= 1 / 5 + 1e-9


def test_mrr_is_averaged_over_questions():
    qs = [
        question_metrics(ranked("g"), ["g"]),  # 1
        question_metrics(ranked("x", "g"), ["g"]),  # 1/2
        question_metrics(ranked("x"), ["g"]),  # 0
        question_metrics(ranked("x", "y", "g"), ["g"]),  # 1/3
    ]
    assert average(qs)["mrr"] == pytest.approx((1 + 0.5 + 0 + 1 / 3) / 4)
    assert average(qs)["n"] == 4 and average(qs)["hit@1"] == 0.25


def test_mrr_ignores_a_first_hit_below_rank_10():
    chunks = [chunk(f"x{n}") for n in range(10)] + [chunk("g")]
    m = question_metrics(chunks, ["g"])
    assert m["mrr"] == 0 and m["first_rank"] == 11 and m["hit@10"] == 0


def test_test_split_is_refused_without_final(capsys):
    assert "refused" in rr.check_split("test", False)
    assert rr.check_split("test", True) is None and rr.check_split("dev", False) is None
    assert rr.main(["x", "--split", "test", "--label", "never-written"]) == 2
    assert "only for the final baseline run" in capsys.readouterr().out
    assert not (rr.RESULTS / "never-written.json").exists()
