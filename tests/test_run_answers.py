"""run_answers tests: fake answers and a fake judge, no network."""

import json

import pytest

from cta.answer import Answer
from cta.eval import run_answers as ra
from cta.settings import load_models

CFG = load_models(env={})


def chunk(source_id, merged=(), sim=0.7):
    return {"id": source_id, "source_id": source_id, "merged_section_ids": list(merged),
            "similarity": sim, "kind": "section", "source": "https://x", "heading_path": "H",
            "terms": [], "last_updated": None, "text": "body"}  # fmt: skip


def top(*ids):
    return [chunk(i) for i in ids] + [chunk(f"f{n}") for n in range(10 - len(ids))]


class FakeSearch:
    cache_hit = False
    cost = 0.0


def ans(text="The deadline is Nov 6 [1].", abstained=False, cost=0.0002, sources=None, **kw):
    a = Answer(
        text,
        abstained,
        "r" if abstained else None,
        sources or top("g")[:5],
        citations=kw.get("citations", [1]),
        invalid_citations=kw.get("invalid", []),
    )
    a.search, a.chat_cost, a.latency_ms, a.chat_ms = FakeSearch(), cost, 1200, 900
    return a


def question(qid="q1", gold="Nov 6", sources=("g",), qtype="lookup"):
    return {"id": qid, "question": "When?", "gold_answer": gold, "type": qtype, "department": None,
            "gold_sources": [{"id": s} for s in sources]}  # fmt: skip


def judge_reply(correctness="correct", faithfulness="yes"):
    return json.dumps({"correctness": correctness, "correctness_reason": "r1",
                       "faithfulness": faithfulness, "faithfulness_reason": "r2"})  # fmt: skip


def fake_judge(*replies, cost=0.01):
    calls = []
    queue = list(replies)

    def call(messages):
        calls.append(messages)
        return queue.pop(0), cost

    call.calls = calls
    return call


# ---- special gold rules ----


def test_gold_kinds():
    assert ra.gold_kind(question(gold="ABSTAIN", sources=())) == "abstain"
    assert ra.gold_kind(question(gold="CLARIFY: it depends")) == "clarify"
    assert ra.gold_kind(question(gold="NO ADVICE: state the rules")) == "no_advice"
    assert ra.gold_kind(question(sources=("fall-2026-044", "winter-2027-023"))) == "calendar_only"
    assert ra.gold_kind(question(sources=("fall-2026-044", "page/a/b#1"))) == "normal"
    assert ra.gold_kind(question(sources=())) == "normal"


def test_abstain_gold_needs_no_judge():
    judge = fake_judge()
    q = question(gold="ABSTAIN", sources=())
    ok = ra.evaluate_question(q, ans("ABSTAIN: nothing found", abstained=True), top(), judge)
    bad = ra.evaluate_question(q, ans("It is open."), top(), judge)
    assert ok["correctness"] == "correct" and ok["label"] is None
    assert bad["correctness"] == "incorrect" and bad["label"] == "abstention error"
    assert judge.calls == []


def test_clarify_gold_is_not_supported_yet_without_a_judge():
    judge = fake_judge()
    r = ra.evaluate_question(question(gold="CLARIFY: which degree?"), ans(), top("g"), judge)
    assert r["label"] == "not supported yet" and r["correctness"] is None and judge.calls == []


def test_no_advice_judge_only_checks_advice():
    judge = fake_judge(json.dumps({"gives_advice": "yes", "reason": "says you should drop"}))
    r = ra.evaluate_question(question(gold="NO ADVICE: rules"), ans(), top("g"), judge)
    assert r["correctness"] == "incorrect" and r["faithfulness"] is None
    assert "Gold answer" not in judge.calls[0][1]["content"]
    judge = fake_judge(json.dumps({"gives_advice": "no", "reason": "rules only"}))
    assert (
        ra.evaluate_question(question(gold="NO ADVICE: r"), ans(), top("g"), judge)["label"] is None
    )


def test_calendar_only_is_judged_and_labelled_not_supported():
    judge = fake_judge(judge_reply("incorrect", "no"))
    q = question(sources=("winter-2027-023",))
    r = ra.evaluate_question(q, ans(), top("x"), judge)
    assert r["gold_kind"] == "calendar_only" and r["correctness"] == "incorrect"
    assert r["label"] == "not supported yet" and len(judge.calls) == 1


def test_judge_sees_question_gold_answer_and_exact_sources_only():
    judge = fake_judge(judge_reply())
    ra.evaluate_question(question(gold="GOLD TEXT"), ans("MODEL ANSWER"), top("g"), judge)
    text = judge.calls[0][1]["content"]
    assert "GOLD TEXT" in text and "MODEL ANSWER" in text and "[1] id: g" in text
    assert "gpt" not in text.lower() and "temperature" not in text


# ---- failure labels (earliest failing stage) ----


@pytest.mark.parametrize(
    ("top10", "answer", "expected"),
    [
        (top("x"), ans(), "retrieval miss"),  # gold g nowhere in the top 10
        (top("x", "x2", "x3", "x4", "x5", "g"), ans(), "ranking miss"),  # rank 6
        (top("g"), ans("Wrong date [1]"), "generation error"),  # in the top 5
        (top("g"), ans("ABSTAIN: missing", abstained=True), "abstention error"),
    ],
)
def test_failure_labels(top10, answer, expected):
    judge = fake_judge(judge_reply("incorrect", "yes"))
    r = ra.evaluate_question(question(), answer, top10, judge)
    assert r["label"] == expected


def test_label_through_merged_section_id():
    judge = fake_judge(judge_reply("partial"))
    top10 = [chunk("parent", merged=["g"])] + top()[1:]
    assert ra.evaluate_question(question(), ans(), top10, judge)["label"] == "generation error"


def test_correct_answer_has_no_label():
    r = ra.evaluate_question(question(), ans(), top("g"), fake_judge(judge_reply()))
    assert r["label"] is None and r["judge_cost"] == 0.01 and r["first_gold_rank"] == 1


# ---- judge parse failure ----


def test_bad_json_is_retried_once_then_recorded_as_failed():
    judge = fake_judge("not json", "{also bad")
    r = ra.evaluate_question(question(), ans(), top("g"), judge)
    assert r["judge_status"] == "judge failed" and r["label"] == "judge failed"
    assert len(judge.calls) == 2 and r["judge_cost"] == pytest.approx(0.02)


def test_bad_json_then_good_json_succeeds():
    judge = fake_judge("oops", judge_reply("partial"))
    r = ra.evaluate_question(question(), ans(), top("g"), judge)
    assert r["correctness"] == "partial" and r["judge_status"] == "ok" and len(judge.calls) == 2


def test_invalid_value_counts_as_parse_failure():
    judge = fake_judge(judge_reply("great", "yes"), judge_reply("correct", "maybe"))
    assert (
        ra.evaluate_question(question(), ans(), top("g"), judge)["judge_status"] == "judge failed"
    )


def test_judge_api_error_does_not_crash():
    def call(messages):
        raise ra.ApiError("boom")

    r = ra.evaluate_question(question(), ans(), top("g"), call)
    assert r["judge_status"] == "judge failed"


# ---- aggregation ----


def records():
    j = fake_judge(
        judge_reply("correct", "yes"),
        judge_reply("partial", "partly"),
        judge_reply("incorrect", "no"),
    )
    refuse = ans("ABSTAIN: no", abstained=True, citations=[])
    gold_abstain = question("q4", "ABSTAIN", ())
    return [
        ra.evaluate_question(question("q1"), ans(), top("g"), j),
        ra.evaluate_question(question("q2"), ans(citations=[1, 9], invalid=[9]), top("g"), j),
        ra.evaluate_question(question("q3"), refuse, top("g"), j),
        ra.evaluate_question(gold_abstain, refuse, top(), j),
        ra.evaluate_question(question("q5", "ABSTAIN", ()), ans("It is open."), top(), j),
        ra.evaluate_question(question("q6", "CLARIFY: x"), ans(), top("g"), j),
    ]


def test_aggregate():
    agg = ra.aggregate(records())
    assert agg["correctness"]["n"] == 3 and agg["correctness"]["correct"] == pytest.approx(1 / 3)
    assert agg["faithfulness"]["partly"] == pytest.approx(1 / 3)
    assert agg["abstention_accuracy"] == {"n": 2, "share": 0.5}
    assert agg["wrongly_abstained"]["n"] == 3
    assert agg["wrongly_abstained"]["share"] == pytest.approx(1 / 3)
    assert agg["citation_rate"]["n"] == 4 and agg["citation_rate"]["invalid_citations"] == 1
    assert agg["citation_rate"]["share"] == 1.0  # [1,9] still has a valid citation
    assert agg["cost"]["n"] == 6 and agg["cost"]["judge_usd"] == pytest.approx(0.03)
    assert agg["latency_ms"]["total_median"] == 1200 and agg["latency_ms"]["query_cache_hits"] == 0


def test_label_counts_and_percentile():
    assert ra.label_counts(records()) == {
        "abstention error": 2, "generation error": 1, "not supported yet": 1}  # fmt: skip
    assert ra.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10
    assert ra.percentile([], 95) is None


def test_judge_failed_is_counted():
    judge = fake_judge("x", "y")
    r = ra.evaluate_question(question(), ans(), top("g"), judge)
    assert ra.aggregate([r])["judge_failed"] == 1


# ---- judge check selection ----


def test_judge_check_rule_is_fixed_and_mixed():
    grades = [("correct", "yes")] * 6 + [
        ("partial", "yes"), ("incorrect", "partly"), ("correct", "no"),
        ("partial", "yes"), ("correct", "yes"),
    ]  # fmt: skip
    recs = [
        {"id": f"q{n:02d}", "judge_status": "ok", "correctness": c, "faithfulness": f}
        for n, (c, f) in enumerate(grades, 1)
    ]
    chosen = ra.pick_judge_check(recs)
    assert len(chosen) == 8 and chosen == ra.pick_judge_check(recs)
    assert {"q08", "q09"} <= set(chosen)  # the faithfulness partly / no ones
    assert "q07" in chosen and "q10" in chosen  # partial ones fill up to 4 non-correct picks


# ---- guards ----


def test_test_split_refused_without_final(capsys):
    assert ra.main(["x", "--split", "test", "--label", "never-written", "--dry-run"]) == 2
    assert "only for the final baseline run" in capsys.readouterr().out


def test_run_stops_when_the_estimate_is_above_the_cap(monkeypatch, capsys):
    from contextlib import nullcontext

    monkeypatch.setattr(ra, "connect", lambda: nullcontext(None))
    monkeypatch.setattr(ra, "estimate_run", lambda *a, **k: (5.0, ["q01 ..."]))
    monkeypatch.setattr(ra, "run", lambda *a, **k: pytest.fail("must not run"))
    assert ra.main(["x", "--split", "dev", "--label", "cap-test", "--yes"]) == 1
    assert "above eval.max_cost_usd" in capsys.readouterr().out


def test_dry_run_and_missing_yes_do_not_run(monkeypatch, capsys):
    from contextlib import nullcontext

    monkeypatch.setattr(ra, "connect", lambda: nullcontext(None))
    monkeypatch.setattr(ra, "estimate_run", lambda *a, **k: (0.01, []))
    monkeypatch.setattr(ra, "run", lambda *a, **k: pytest.fail("must not run"))
    assert ra.main(["x", "--split", "dev", "--label", "dry-test", "--dry-run", "--yes"]) == 0
    assert ra.main(["x", "--split", "dev", "--label", "dry-test"]) == 0
    out = capsys.readouterr().out
    assert "dry run" in out and "add --yes" in out
