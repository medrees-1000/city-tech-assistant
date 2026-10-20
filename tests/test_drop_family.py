"""Casual round, item 2 (T04): the drop-family calendar rule. Phrase sets in
tests/drop_phrases.py (written before the code). No model call."""

import re
from datetime import date

import pytest

from cta.eval.questions import load_questions
from cta.graph import build, clarify
from tests.drop_phrases import NEGATIVES, POSITIVES
from tests.helpers import Script, make_router


def calendar_rows():
    return build.load_events()


def test_the_sets_have_the_pre_registered_sizes():
    assert (len(POSITIVES), len(NEGATIVES)) == (10, 12)


@pytest.mark.parametrize("question", POSITIVES)
def test_unqualified_drop_and_withdraw_date_questions_apply(question):
    assert clarify.drop_family_applies(question)


@pytest.mark.parametrize("question", NEGATIVES)
def test_qualified_or_other_questions_do_not(question):
    assert not clarify.drop_family_applies(question)


# Oct 17, 2026 (owner decision): the drop and withdraw deadline rows AND the tuition-refund rows,
# in date order (the same date keeps the row-id order). Winter has no 75% refund row.
EXPECTED = {
    "Fall 2026": "004 008 011 016 019 021 040",
    "Winter 2027": "003 007 008 011 012 019",
    "Spring 2027": "005 009 012 017 020 022 044",
}
EXPECTED = {
    t: [f"{t.lower().replace(' ', '-')}-{n}" for n in ids.split()] for t, ids in EXPECTED.items()
}


@pytest.mark.parametrize(("term", "ids"), EXPECTED.items())
def test_each_term_matches_exactly_its_drop_and_refund_rows_in_date_order(term, ids):
    pool = [r for r in calendar_rows() if r["term"] == term]
    rows = clarify.drop_family_rows(pool)
    assert [r["id"] for r in rows] == ids
    assert [r["date_start"] for r in rows] == sorted(r["date_start"] for r in rows)
    # never an add row, a "grade ... is assigned" explanation row or a period start
    assert not any(re.search(r"\badd\b|assigned|period begins", r["event"], re.I) for r in rows)
    refunds = [r for r in rows if "tuition refund" in r["event"]]
    assert refunds and all(r["event"].lower().startswith("last day to drop") for r in refunds)
    assert {r["id"] for r in rows} <= {e["id"] for e in calendar_rows()}  # only verified rows


def test_a_term_without_such_rows_gets_nothing():
    other = [{"id": "x-1", "event": "Classes begin", "date_start": "2026-01-01"}]
    assert clarify.drop_family_rows(other) == []


def test_dev_questions_that_apply_are_only_the_new_cq17():
    dev = [q for q in load_questions() if q["split"] == "dev"]
    assert [q["id"] for q in dev if clarify.drop_family_applies(q["question"])] == ["q114"]


TODAY = date(2026, 10, 11)
THREE = EXPECTED["Fall 2026"]  # the name is kept; the list is the seven rows since Oct 17, 2026


@pytest.mark.parametrize(
    "question",
    [
        "whats the last day to drop a class fall 2026",
        "call me at [PHONE] whats the last day to drop a class fall 2026",
    ],
)
def test_the_router_lists_the_drop_and_refund_rows_without_a_selector_call(monkeypatch, question):
    script = Script("calendar", "Fall 2026", ["fall-2026-040"])  # the selector would pick one row
    router, seen = make_router(script, monkeypatch, calendar_rows())
    ans = router.answer(question, TODAY, log=False)
    assert script.calls == ["classify"] and seen == []
    assert ans.route == "calendar" and ans.row_ids == THREE and not ans.abstained
    assert ans.router["selector_version"] == "drop_family_v2" == clarify.DROP_FAMILY_VERSION
    assert (
        ans.text.index("August 27")
        < ans.text.index("September 3")
        < ans.text.index("September 10")
        < ans.text.index("September 17")
        < ans.text.index("November 6")
    )
    assert "100% tuition refund" in ans.text and "25% tuition refund" in ans.text


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


def test_refund_rows_are_included_and_every_listed_row_is_in_the_verified_table():
    pool = [r for r in calendar_rows() if r["term"] == "Fall 2026"]
    rows = clarify.drop_family_rows(pool)
    percents = [r["event"] for r in rows if "tuition refund" in r["event"]]
    assert [p.split(" for ")[1][:4] for p in percents] == ["100%", "75% ", "50% ", "25% "]
    assert all(r in pool for r in rows)  # never a row that is not in the table


def test_a_term_with_no_refund_rows_gets_only_the_grade_rows():
    pool = [
        {"id": "t-1", "event": "Last Day to drop without a grade of WD",
         "date_start": "2027-03-02"},
        {"id": "t-2", "event": "Last day to withdraw from a course with a grade of W.",
         "date_start": "2027-04-05"},
        {"id": "t-3", "event": "Classes begin", "date_start": "2027-01-27"},
    ]  # fmt: skip
    assert [r["id"] for r in clarify.drop_family_rows(pool)] == ["t-1", "t-2"]


def test_unrelated_events_and_questions_are_unchanged():
    pool = [
        {"id": "u-1", "event": "Last day to add a course", "date_start": "2026-09-03"},
        {"id": "u-2", "event": "Last day to apply for a refund of the activity fee",
         "date_start": "2026-09-04"},
        {"id": "u-3", "event": "Online registration begins", "date_start": "2026-10-29"},
    ]  # fmt: skip
    assert clarify.drop_family_rows(pool) == []
    assert not clarify.drop_family_applies("when is the last day to add a course")
    # a qualifier: the selector
    assert not clarify.drop_family_applies("when do I get my tuition refund")


def test_the_selector_version_is_bumped_so_stored_records_stay_distinguishable():
    assert clarify.DROP_FAMILY_VERSION == "drop_family_v2"
