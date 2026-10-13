"""run_answers tests: fake answers and a fake judge, no network."""

import json

import pytest

from cta.answer import Answer
from cta.eval import run_answers as ra
from cta.settings import load_models

CFG = load_models(
    env={"CTA_RERANK": "off", "CTA_ROUTER_MODE": "off"}
)  # the reranker has its own tests


def chunk(source_id, merged=(), sim=0.7):
    return {"id": source_id, "source_id": source_id, "merged_section_ids": list(merged),
            "similarity": sim, "kind": "section", "source": "https://x", "heading_path": "H",
            "terms": [], "last_updated": None, "text": "body"}  # fmt: skip


def top(*ids):
    return [chunk(i) for i in ids] + [chunk(f"f{n}") for n in range(10 - len(ids))]


class FakeSearch:
    cache_hit = False
    cost = 0.0
    total_cost = 0.0


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


# ---- rubric v2, new label rule, re-judge helpers ----


def test_label_rule_v2_any_missing_gold_is_a_retrieval_miss():
    q = question(sources=("g1", "g2"))
    only_one = top("g1")  # g2 nowhere in the top 10
    judge = fake_judge(judge_reply("partial"))
    r = ra.evaluate_question(q, ans(), only_one, judge)
    assert r["label"] == "retrieval miss" and "g2" in r["label_reason"]


def test_label_rule_v2_any_missing_from_top5_is_a_ranking_miss():
    q = question(sources=("g1", "g2"))
    ranked = top("g1", "x1", "x2", "x3", "x4", "g2")  # g2 at rank 6
    r = ra.evaluate_question(q, ans(), ranked, fake_judge(judge_reply("partial")))
    assert r["label"] == "ranking miss" and "g2" in r["label_reason"]


def test_label_rule_v2_all_gold_in_top5_is_a_generation_error():
    q = question(sources=("g1", "g2"))
    r = ra.evaluate_question(q, ans(), top("g1", "g2"), fake_judge(judge_reply("partial")))
    assert r["label"] == "generation error"


def test_rubric_is_versioned_and_in_the_prompt():
    from cta.eval import rubric

    assert rubric.RUBRIC_VERSION == 3
    assert "NOT required" in rubric.JUDGE_INSTRUCTIONS
    assert "even if it is likely\n  true" in rubric.JUDGE_INSTRUCTIONS
    # v3: faithfulness is judged against the shown sources only, and absence statements are checked
    assert "Never use outside knowledge" in rubric.JUDGE_INSTRUCTIONS
    assert "is indeed absent from the\n  numbered sources" in rubric.JUDGE_INSTRUCTIONS
    assert "when X is in fact in the numbered sources" in rubric.JUDGE_INSTRUCTIONS
    msgs = ra.judge_messages("normal", question(), ans())
    assert msgs[0]["content"] == rubric.JUDGE_INSTRUCTIONS


@pytest.mark.integration
def test_rubric_version_is_stored_in_the_run_config(conn):
    run_id = ra.start_run(conn, "t", "dev", CFG, {"rejudge_of": "x"})
    config = conn.execute("SELECT config FROM eval_runs WHERE id = %s", (run_id,)).fetchone()[0]
    assert config["rubric_version"] == 3 and config["rejudge_of"] == "x"


def test_verdict_changes_lists_only_changed_questions():
    old = [
        {"id": "q1", "correctness": "partial", "faithfulness": "yes"},
        {"id": "q2", "correctness": "correct", "faithfulness": "yes"},
    ]
    new = [
        {"id": "q1", "correctness": "correct", "faithfulness": "yes",
         "correctness_reason": "asked part given", "faithfulness_reason": "ok"},
        {"id": "q2", "correctness": "correct", "faithfulness": "yes",
         "correctness_reason": "r", "faithfulness_reason": "r"},
    ]  # fmt: skip
    changes = ra.verdict_changes(old, new)
    assert len(changes) == 1 and changes[0].startswith("q1: correctness partial -> correct")
    assert "asked part given" in changes[0]


def test_rejudge_never_calls_the_api():
    with pytest.raises(ra.ApiError):
        ra.no_api()


def test_chained_prerequisite_questions_are_not_supported_yet():
    q = question("q22", sources=("catalog:MAT 2675",), qtype="multi_chunk")
    q["tags"] = ["chain"]
    top10 = top("catalog:MAT 2675")
    r = ra.evaluate_question(
        q, ans("Needs MAT 1575 and MAT 2580 [1]."), top10, fake_judge(judge_reply("partial"))
    )
    assert r["label"] == "not supported yet (chained prerequisite)"
    other = question("q21", sources=("catalog:EET 3672",))
    r = ra.evaluate_question(
        other, ans(), top("catalog:EET 3672"), fake_judge(judge_reply("partial"))
    )
    assert r["label"] == "generation error"


# ---- the 60-question set and the chain row ----

EXPECTED_KIND = {  # how each of q31-q60 is meant to be handled
    **dict.fromkeys(["q31", "q32", "q33", "q36", "q37", "q38"], "calendar_only"),
    **dict.fromkeys(["q34", "q35", "q44", "q45", "q46"], "abstain"),
    **dict.fromkeys(["q47", "q48"], "no_advice"),
    **dict.fromkeys(["q49", "q50"], "clarify"),
    **dict.fromkeys(
        ["q39", "q40", "q41", "q42", "q43", "q51", "q52", "q53", "q54", "q55", "q56", "q57",
         "q58", "q59", "q60"], "normal"),
}  # fmt: skip


def real_questions():
    from cta.eval.questions import load_questions

    return {q["id"]: q for q in load_questions()}


def test_new_questions_are_classified_as_intended():
    from cta.eval.metrics import scorable_gold

    qs = real_questions()
    assert sorted(EXPECTED_KIND) == [f"q{n}" for n in range(31, 61)] and len(qs) >= 60
    for qid, kind in EXPECTED_KIND.items():
        assert ra.gold_kind(qs[qid]) == kind, qid
    # retrieval-scored: a section or course gold source (calendar ids never count)
    unscored = {qid for qid in EXPECTED_KIND if not scorable_gold(qs[qid])}
    assert unscored == {"q31", "q32", "q33", "q34", "q35", "q36", "q37", "q38", "q44", "q45", "q46"}
    # the 14 calendar questions of step 4a-1 are never retrieval-scored, so the 30 scored dev
    # questions (and the baseline-dev-60 retrieval numbers) did not change when they were added
    new_calendar = [q for q in qs if "calendar" in qs[q].get("tags", []) and int(q[1:]) <= 87]
    assert len(new_calendar) == 14 and not any(scorable_gold(qs[q]) for q in new_calendar)
    kinds = {q: ra.gold_kind(qs[q]) for q in new_calendar}
    assert {q: k for q, k in kinds.items() if k != "calendar_only"} == {
        "q72": "abstain",
        "q74": "clarify",
    }


def test_chain_tags_are_exactly_the_chain_questions():
    qs = real_questions()
    tagged = sorted(q for q, row in qs.items() if "chain" in row.get("tags", []))
    # the five of Phase 3 step 0, then q76 to q86 of step 4b-1 (q87 is the non-chain control)
    assert tagged == ["q20", "q22", "q39", "q40", "q41"] + [f"q{n}" for n in range(76, 87)] + [
        "q93", "q94"]  # fmt: skip


def test_chain_row_is_separate_and_all_row_is_unchanged():
    chain_q = question("qa", sources=("g",))
    chain_q["tags"] = ["chain"]
    plain_q = question("qb", sources=("g",))
    retrieved = {"qa": top("x"), "qb": top("g")}  # the chain question misses, the other hits
    scored, _ = ra.score([chain_q, plain_q], retrieved)
    assert [r["tags"] for r in scored] == [["chain"], []]
    overall, chain = ra.average(scored), ra.chain_retrieval(scored)
    assert overall["n"] == 2 and overall["hit@1"] == 0.5  # 'all' counts both
    assert chain["n"] == 1 and chain["hit@1"] == 0.0  # the chain row only the tagged one
    assert ra.chain_retrieval([r for r in scored if not r["tags"]]) is None


def test_aggregate_adds_a_chain_block_without_changing_the_rest():
    j = fake_judge(judge_reply("correct"), judge_reply("partial"))
    q1, q2 = question("q1"), question("q2")
    q2["tags"] = ["chain"]
    recs = [
        ra.evaluate_question(q1, ans(), top("g"), j),
        ra.evaluate_question(q2, ans(), top("g"), j),
    ]
    agg = ra.aggregate(recs)
    assert agg["correctness"]["n"] == 2 and agg["chain"]["correctness"]["n"] == 1
    assert agg["chain"]["correctness"]["partial"] == 1.0
    plain = ra.aggregate([recs[0]])
    assert plain["chain"] is None
    assert {k: v for k, v in agg.items() if k != "chain"}["correctness"] != plain["correctness"]


def test_print_report_shows_the_chain_row():
    j = fake_judge(judge_reply("partial"))
    q = question("q2")
    q["tags"] = ["chain"]
    recs = [ra.evaluate_question(q, ans(), top("g"), j)]
    scored, excluded = ra.score([q], {"q2": top("g")})
    lines: list[str] = []
    ra.print_report(recs, ra.aggregate(recs), ra.average(scored), excluded, lines.append,
                    ra.chain_retrieval(scored))  # fmt: skip
    text = "\n".join(lines)
    assert "chain (tagged)" in text and "chain-tagged questions" in text
