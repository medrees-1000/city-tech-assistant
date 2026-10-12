"""Step 4a-2: the acceptable-extra field, scoring v1 and v2, same-date collisions, re-scoring."""

import pytest

from cta.eval import calendar_gold as cg
from cta.eval import run_answers as ra
from cta.eval.questions import GoldData, check_all, load_questions, row_problems
from cta.graph.state import RoutedAnswer
from cta.index.search import Search


def ev(rid, date_start, event="Something.", term="Fall 2026", **kw):
    return {"id": rid, "term": term, "event": event, "date_start": date_start, "date_end": None,
            "verified": True} | kw  # fmt: skip


def question(gold=("a",), extra=None, qid="q1"):
    q = {"id": qid, "question": "When?", "gold_answer": "d", "type": "time_sensitive",
         "department": None, "split": "dev", "note": "",
         "gold_sources": [{"id": i, "source": "data/calendar/calendar_events.json",
                           "heading": "Fall 2026: Something."} for i in gold]}  # fmt: skip
    return q | ({"calendar_acceptable_extra": extra} if extra is not None else {})


def answer(rows=(), route="calendar"):
    ans = RoutedAnswer("t", False, None, [], search=Search([], False, 0, 0, 0.0))
    ans.row_ids, ans.route = list(rows), route
    return ans


# ---- the loader field ----


def test_the_field_is_accepted_and_checked_in_shape():
    assert row_problems(question(("a",), ["b"])) == []
    assert "not a list" in row_problems(question(("a",), "b"))[0]
    assert "not a list" in row_problems(question(("a",), [""]))[0]
    assert "also gold: a" in row_problems(question(("a", "c"), ["a"]))[0]


def test_extras_must_be_verified_calendar_events_on_a_calendar_only_question():
    data = GoldData({}, {}, {"a": ev("a", "2026-09-03"), "b": ev("b", "2026-09-03"),
                             "u": ev("u", "2026-09-03", verified=False)})  # fmt: skip
    good = check_all([question(("a",), ["b"])], data)["q1"]
    assert good == []
    assert any(
        "not a verified calendar event" in p
        for p in check_all([question(("a",), ["u"])], data)["q1"]
    )
    assert any(
        "not a verified calendar event" in p
        for p in check_all([question(("a",), ["zz"])], data)["q1"]
    )
    section = question(("page/x#1",), ["b"]) | {"type": "lookup"}
    assert any("needs a calendar-only question" in p for p in check_all([section], data)["q1"])


def test_the_real_file_loads_with_the_optional_field_unused_until_the_owner_decides():
    rows = load_questions()
    assert all(row_problems(r) == [] for r in rows)


# ---- scoring v1 and v2 ----


@pytest.mark.parametrize(
    ("returned", "route", "v1", "v2"),
    [
        (["a", "b"], "calendar", "correct", "correct"),
        (["b", "a"], "calendar", "correct", "correct"),
        (["a"], "calendar", "partial", "partial"),
        (["a", "b", "e"], "calendar", "correct", "correct"),  # e is an acceptable extra in v2 only
        (["a", "x"], "calendar", "incorrect", "incorrect"),
        (["e"], "calendar", "incorrect", "incorrect"),  # an extra alone covers nothing required
        ([], "calendar_fallthrough", "incorrect", "incorrect"),
        ([], "abstain", "incorrect", "incorrect"),
    ],
)
def test_scoring_v1_exact_and_v2_with_extras(returned, route, v1, v2):
    q = question(("a", "b"), ["e"])
    assert ra.calendar_result(q, answer(returned, route), 1)[0]["correctness"] == (
        v1 if "e" not in returned else "incorrect"
    )
    assert ra.calendar_result(q, answer(returned, route), 2)[0]["correctness"] == v2


def test_v2_an_extra_with_every_required_row_is_correct_and_v1_calls_it_a_wrong_row():
    q = question(("a",), ["e"])
    assert ra.calendar_result(q, answer(["a", "e"]), 2)[1:2] == (None,)
    verdict, label, _ = ra.calendar_result(q, answer(["a", "e"]), 1)
    assert verdict["correctness"] == "incorrect" and label == "calendar wrong row"


def test_v2_partial_needs_nothing_outside_required_and_extras():
    q = question(("a", "b"), ["e"])
    assert ra.calendar_result(q, answer(["a", "e"]), 2)[0]["correctness"] == "partial"
    verdict, label, _ = ra.calendar_result(q, answer(["a", "x"]), 2)
    assert (verdict["correctness"], label) == ("incorrect", "calendar wrong row")


def test_every_run_records_both_versions_and_the_chosen_one_decides():
    a, e = "fall-2026-001", "fall-2026-002"
    q = question((a,), [e])
    ans = answer([a, e])
    v1 = ra.evaluate_question(q, ans, [], None, 1)
    v2 = ra.evaluate_question(q, ans, [], None, 2)
    assert v1["correctness"] == "incorrect" and v2["correctness"] == "correct"
    for rec in (v1, v2):
        assert rec["calendar_v1"]["correctness"] == "incorrect"
        assert rec["calendar_v2"]["correctness"] == "correct"
    judged = ra.evaluate_question(q, ans, [], lambda m: ('{"x":1}', 0.0), 0)
    assert "calendar_v1" not in judged  # scoring off: the old judge path


# ---- same-date collisions and re-scoring ----


def test_collisions_exclude_gold_undated_and_web_address_rows():
    rows = [ev("a", "2026-09-03"), ev("b", "2026-09-03"), ev("c", "2026-09-04"),
            ev("d", "2026-09-03", event="For more info :- www.x.edu/a"),
            ev("e", None), ev("f", "2026-09-03", term="Winter 2027")]  # fmt: skip
    assert [(r["id"], g) for r, g in cg.collisions(rows, ["a"])] == [("b", "a"), ("f", "a")]
    assert cg.collisions(rows, ["c"]) == []


def test_proposals_default_to_no_and_the_prefilled_rows_are_the_owners():
    assert cg.proposal("q63", "winter-2027-005")[0] == "yes"
    assert cg.proposal("q63", "winter-2027-006")[0] == "no" and cg.proposal("q12", "x")[0] == "no"
    q33 = next(q for q in load_questions() if q["id"] == "q33")
    after = cg.with_prefilled(q33)
    assert [g["id"] for g in after["gold_sources"]] == ["spring-2027-007"]
    assert after["calendar_acceptable_extra"] == ["spring-2027-006"]
    assert len(q33["gold_sources"]) == 2 and "calendar_acceptable_extra" not in q33  # a copy


def test_rescoring_a_stored_run_uses_returned_rows_and_route_without_a_model():
    a, e = "fall-2026-001", "fall-2026-002"
    run = {"per_question": [
        {"id": "q1", "returned_rows": [a, e], "route": "calendar"},
        {"id": "q2", "returned_rows": [], "route": "abstain"},
        {"id": "q3", "returned_rows": ["z"], "route": "other"},  # not a calendar-only question
    ]}  # fmt: skip
    qs = {"q1": question((a,), [e], "q1"), "q2": question((a,), None, "q2")}
    assert cg.rescore(run, qs, 1) == {
        "q1": ("incorrect", "calendar wrong row"),
        "q2": ("incorrect", "calendar abstained"),
    }
    assert cg.rescore(run, qs, 2)["q1"] == ("correct", None)
