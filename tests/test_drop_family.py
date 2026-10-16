"""Casual round, item 2 (T04): the drop-family calendar rule. Phrase sets in
tests/drop_phrases.py (written before the code). No model call."""

import re
from datetime import date

import pytest

from cta.eval.questions import load_questions
from cta.graph import build, drop_family
from tests.drop_phrases import NEGATIVES, POSITIVES
from tests.test_router import Script, make_router


def calendar_rows():
    return build.load_events()


def test_the_sets_have_the_pre_registered_sizes():
    assert (len(POSITIVES), len(NEGATIVES)) == (10, 12)


@pytest.mark.parametrize("question", POSITIVES)
def test_unqualified_drop_and_withdraw_date_questions_apply(question):
    assert drop_family.applies(question)


@pytest.mark.parametrize("question", NEGATIVES)
def test_qualified_or_other_questions_do_not(question):
    assert not drop_family.applies(question)


EXPECTED = {
    "Fall 2026": ["fall-2026-011", "fall-2026-021", "fall-2026-040"],
    "Winter 2027": ["winter-2027-008", "winter-2027-012", "winter-2027-019"],
    "Spring 2027": ["spring-2027-012", "spring-2027-022", "spring-2027-044"],
}


@pytest.mark.parametrize(("term", "ids"), EXPECTED.items())
def test_each_term_matches_exactly_its_three_rows_in_date_order(term, ids):
    pool = [r for r in calendar_rows() if r["term"] == term]
    rows = drop_family.rows_of(pool)
    assert [r["id"] for r in rows] == ids
    assert [r["date_start"] for r in rows] == sorted(r["date_start"] for r in rows)
    assert not any(re.search(r"refund|\badd\b|assigned|period begins", r["event"], re.I)
                   for r in rows)  # fmt: skip


def test_a_term_without_such_rows_gets_nothing():
    other = [{"id": "x-1", "event": "Classes begin", "date_start": "2026-01-01"}]
    assert drop_family.rows_of(other) == []


def test_dev_questions_that_apply_are_only_the_new_cq17():
    dev = [q for q in load_questions() if q["split"] == "dev"]
    assert [q["id"] for q in dev if drop_family.applies(q["question"])] == ["q114"]


TODAY = date(2026, 10, 11)
THREE = "fall-2026-011 fall-2026-021 fall-2026-040".split()


@pytest.mark.parametrize(
    "question",
    [
        "whats the last day to drop a class fall 2026",
        "call me at [PHONE] whats the last day to drop a class fall 2026",
    ],
)
def test_the_router_lists_the_three_rows_without_a_selector_call(monkeypatch, question):
    script = Script("calendar", "Fall 2026", ["fall-2026-040"])  # the selector would pick one row
    router, seen = make_router(script, monkeypatch, calendar_rows())
    ans = router.answer(question, TODAY, log=False)
    assert script.calls == ["classify"] and seen == []
    assert ans.route == "calendar" and ans.row_ids == THREE and not ans.abstained
    assert ans.router["selector_version"] == "drop_family"
    assert (
        ans.text.index("September 3")
        < ans.text.index("September 17")
        < ans.text.index("November 6")
    )


def test_a_qualified_question_still_goes_to_the_selector(monkeypatch):
    script = Script("calendar", "Fall 2026", ["fall-2026-011"])
    router, _ = make_router(script, monkeypatch, calendar_rows())
    ans = router.answer("last day to drop a class fall 2026 without a W", TODAY, log=False)
    assert script.calls == ["classify", "select"] and ans.row_ids == ["fall-2026-011"]


def test_an_assumed_term_is_stated_like_any_calendar_answer(monkeypatch):
    script = Script("calendar", None, [])
    router, _ = make_router(script, monkeypatch, calendar_rows())
    ans = router.answer("last day to drop a class", TODAY, log=False)
    assert ans.row_ids == THREE and "Assuming the current term, Fall 2026" in ans.text
