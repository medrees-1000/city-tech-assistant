# ruff: noqa: E501
"""Step 4b report helpers (no network, no database)."""

from cta.eval import chain_report as cr


def q(qid, split="dev", tags=(), typ="multi_chunk", sources=()):
    return {"id": qid, "split": split, "tags": list(tags), "type": typ, "question": "?",
            "gold_sources": [{"id": s} for s in sources]}  # fmt: skip


def test_the_question_sets_follow_the_plan():
    rows = [q("q22", tags=["chain"]), q("q83", tags=["chain"], typ="unanswerable"), q("q87"), q("q99", split="test", tags=["chain"]),
            q("q21", typ="lookup"), q("q82", tags=["chain"], typ="unanswerable")]  # fmt: skip
    sets = cr.question_sets(rows)
    assert sets["CH"] == ["q22"] and sets["AB"] == ["q83"]
    assert sets["CTRL"] == ["q87", "q21", "q82"] and "q99" not in sum(sets.values(), [])


def test_chain_coverage_needs_every_gold_source_among_the_received_ones():
    assert cr.coverage(["a", "b", "c"], ["a", "c"]) and not cr.coverage(["a"], ["a", "b"])
    questions = {
        "q1": q("q1", sources=["catalog:A", "catalog:B"]),
        "q2": q("q2", sources=["catalog:A"]),
        "q3": q("q3", sources=["catalog:A", "page/x#1", "catalog:C"]),
    }
    sources = {"q1": ["catalog:A", "catalog:B"], "q2": [], "q3": ["catalog:A"]}
    assert cr.gold_catalog(questions["q3"]) == ["catalog:A", "catalog:C"]
    assert (
        cr.m3(sources, questions, ["q1", "q2", "q3"]) == 0.5
    )  # q2 has one gold source: not eligible
    assert cr.m3(sources, questions, ["q2"]) is None


def test_answered_by_chain_counts_the_chain_answer_and_the_no_record_abstain_but_not_a_fall_through():
    assert cr.answered_by_chain({"route": "chain"})
    assert cr.answered_by_chain({"route": "abstain", "router": {"chain": {"no_record": True}}})
    assert not cr.answered_by_chain(
        {"route": "chain_fallthrough", "router": {"chain": {"fallthrough": True}}}
    )
    assert not cr.answered_by_chain({"route": "abstain", "router": {"term_status": "unsupported"}})
    assert cr.prerequisite_intent(
        {"router": {"intent": "prerequisite"}}
    ) and not cr.prerequisite_intent({"route": "chain"})


def test_a_chain_abstain_is_not_a_calendar_misroute():
    run = {"per_question": [
        {"id": "q83", "route": "abstain", "router": {"intent": "prerequisite"}},
        {"id": "q13", "route": "calendar_fallthrough", "router": {"intent": "calendar"}},
        {"id": "q34", "route": "abstain", "router": {"intent": "calendar"}},
        {"id": "q12", "route": "calendar", "router": {"intent": "calendar"}},
    ]}  # fmt: skip
    intents = {"q83": "other", "q13": "other", "q34": "calendar", "q12": "calendar"}
    assert cr.calendar_misroutes(run, intents) == ["q13"]


def test_the_verdict_needs_every_rule():
    assert (
        cr.verdict({"R1": True, "R2": True}) == "KEEP"
        and cr.verdict({"R1": True, "R2": False}) == "REJECT"
    )
