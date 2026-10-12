"""Step 4a report helpers: gold intent, misroutes, classifier accuracy, summaries, cost split."""

from datetime import date

import pytest

from cta.eval import router_report as rr
from cta.graph.build import load_events

TODAY = date(2026, 10, 11)


def rec(qid, route="calendar", intent="calendar", correctness="correct", label=None, **kw):
    base = {
        "id": qid, "route": route, "correctness": correctness, "label": label, "answer_cost": 0.001,
        "judge_cost": 0.002, "rerank_cost": 0.0002, "latency_ms": 1000, "returned_rows": [],
        "router": {"intent": intent, "classify": {"cost": 0.0001, "ms": 800},
                   "select": {"cost": 0.0002, "ms": 900}, "render_ms": 0.1},
    }  # fmt: skip
    return base | kw


def q(kind_gold, question="Q?", sources=()):
    return {"id": "x", "question": question, "gold_answer": kind_gold, "type": "lookup",
            "gold_sources": [{"id": s} for s in sources]}  # fmt: skip


def test_gold_intent_from_the_gold_not_from_the_classifier():
    events = load_events()
    assert rr.gold_intent(q("Friday", sources=["fall-2026-040"]), events, TODAY) == "calendar"
    assert (
        rr.gold_intent(q("ABSTAIN", "Last day to drop in Summer 2027?"), events, TODAY)
        == "calendar"
    )
    assert (
        rr.gold_intent(q("ABSTAIN", "Open seats in CST 1101 this fall?"), events, TODAY) == "other"
    )
    assert (
        rr.gold_intent(q("text", sources=["page/x#1", "fall-2026-044"]), events, TODAY) == "other"
    )


def test_misroutes_both_ways_and_classifier_accuracy():
    run = {"per_question": [
        rec("a", "calendar", "calendar"), rec("b", "other", "other"),
        rec("c", "calendar", "calendar"),  # an other question sent to the calendar
        rec("d", "other", "other"),  # a calendar question sent away
        rec("e", "calendar_fallthrough", "calendar"), rec("f", "abstain", "calendar"),
        {"id": "g", "route": None, "router": None},  # a router-off record is ignored
    ]}  # fmt: skip
    intents = {
        "a": "calendar",
        "b": "other",
        "c": "other",
        "d": "calendar",
        "e": "other",
        "f": "calendar",
    }
    got = rr.misroutes(run, intents)
    assert got == {"other_to_calendar": ["c", "e"], "calendar_sent_away": ["d"]}
    assert rr.classifier_accuracy(run, intents) == (3, 6)
    assert rr.fell_through(run) == ["e"]


def test_calendar_summary_counts_grades_wrong_dates_and_labels():
    run = {"per_question": [
        rec("a"), rec("b", correctness="partial", label="calendar missed"),
        rec("c", correctness="incorrect", label="calendar wrong row"),
        rec("d", correctness="incorrect", label="calendar missed"),
    ]}  # fmt: skip
    s = rr.calendar_summary(run, ["a", "b", "c", "d"])
    assert (s["correct"], s["partial"], s["incorrect"], s["wrong_dates"]) == (1, 1, 2, 1)
    assert s["labels"] == {"calendar missed": 2, "calendar wrong row": 1}


def test_cost_is_split_into_classify_select_rerank_answer_and_judge():
    run = {"per_question": [rec("a"), rec("b", router=None, rerank_cost=0.0)]}
    c = rr.component_cost(run)
    assert c["classify"] == pytest.approx(0.00005) and c["select"] == pytest.approx(0.0001)
    assert c["rerank"] == pytest.approx(0.0001) and c["judge"] == pytest.approx(0.002)
    assert c["answer"] == pytest.approx((0.001 - 0.0001 - 0.0002 - 0.0002 + 0.001) / 2)
    assert c["total_usd"] == pytest.approx(0.006)


def test_latency_by_route_uses_the_router_numbers():
    run = {"per_question": [rec("a"), rec("b", "other")]}
    out = rr.component_latency(run)
    assert out["calendar"]["classify"][0] == 800 and out["calendar"]["select"][0] == 900
    assert (
        "select" not in out["other"] or out["other"]["select"] is not None
    )  # "other" has the stub select
    assert out["calendar"]["n"] == 1 and out["other"]["n"] == 1
