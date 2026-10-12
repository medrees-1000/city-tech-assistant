"""scripts/make_calendar_candidates.py: gold text from rows, year resolution, TBA, determinism."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "make_calendar_candidates", ROOT / "scripts" / "make_calendar_candidates.py"
)
mcc = importlib.util.module_from_spec(spec)
sys.modules["make_calendar_candidates"] = mcc
spec.loader.exec_module(mcc)


def row(rid="fall-2026-040", **kw):
    base = {
        "id": rid, "term": "Fall 2026", "event": "Last day to withdraw.",
        "date_start": "2026-11-06",
        "date_end": None, "date_raw": "November 06", "weekday_raw": "Friday", "applies_to": None,
        "bold": False, "source_pdf": "data/pdfs/fall_2026.pdf", "source_page": 1,
        "pdf_last_updated": "2026-09-15", "verified": True,
    }  # fmt: skip
    return base | kw


# ---- dates in words, year resolution ----


def test_single_date_in_words():
    assert mcc.date_in_words(row()) == "Friday, November 6, 2026"


def test_winter_december_row_is_2026_and_january_row_is_2027():
    dec = row("winter-2027-001", term="Winter 2027", date_start="2026-12-28", weekday_raw="Monday")
    jan = row("winter-2027-004", term="Winter 2027", date_start="2027-01-04", weekday_raw="Monday")
    assert mcc.date_in_words(dec) == "Monday, December 28, 2026"
    assert mcc.date_in_words(jan) == "Monday, January 4, 2027"


def test_ranges_inside_a_month_across_months_and_across_years():
    inside = row(date_start="2026-12-15", date_end="2026-12-21", weekday_raw="Tuesday-Monday")
    months = row(date_start="2027-05-28", date_end="2027-06-02", weekday_raw="Friday-Wednesday")
    years = row(date_start="2026-12-30", date_end="2027-01-02", weekday_raw="Wednesday-Saturday")
    assert mcc.date_in_words(inside) == "December 15-21, 2026 (Tuesday-Monday)"
    assert mcc.date_in_words(months) == "May 28 - June 2, 2027 (Friday-Wednesday)"
    assert mcc.date_in_words(years) == "December 30, 2026 - January 2, 2027 (Wednesday-Saturday)"


def test_tba_row_has_no_date():
    tba = row("spring-2027-055", term="Spring 2027", date_start=None, weekday_raw="TBA")
    assert mcc.date_in_words(tba) == "TBA (not announced)"


# ---- gold text ----


def test_gold_is_built_from_the_row_fields():
    gold = mcc.gold_answer({"kind": "rows"}, [row()], None)
    assert gold == (
        "Friday, November 6, 2026: Last day to withdraw. [fall-2026-040] "
        "(Fall 2026 calendar, fall_2026.pdf, last updated 2026-09-15; the calendar can change)"
    )


def test_assumed_term_is_named_in_the_gold():
    gold = mcc.gold_answer({"assumed": "Fall 2026"}, [row()], None)
    assert gold.startswith("Assumed term: Fall 2026 (from today's date, 2026-10-11). Friday")


def test_several_rows_from_two_calendars_list_each_provenance_once():
    other = row("spring-2027-040", term="Spring 2027", source_pdf="data/pdfs/spring_2027.pdf",
                pdf_last_updated="2026-07-27")  # fmt: skip
    gold = mcc.gold_answer({}, [row(), row("fall-2026-041"), other], None)
    assert gold.count("Fall 2026 calendar, fall_2026.pdf") == 1
    assert "Spring 2027 calendar, spring_2027.pdf, last updated 2026-07-27" in gold
    assert gold.count("[") == 3


def test_tba_gold_says_not_announced_and_names_the_registrar():
    tba = row(
        "spring-2027-055", term="Spring 2027", event="87th Commencement Ceremony",
        date_start=None, weekday_raw="TBA", source_pdf="data/pdfs/spring_2027.pdf",
    )  # fmt: skip
    gold = mcc.gold_answer({"kind": "tba"}, [tba], "registrar@x.edu, 718-000-0000")
    assert gold.startswith("Not announced yet: the Spring 2027 calendar lists the date of")
    assert "[spring-2027-055]" in gold and gold.endswith(
        "Contact the Registrar: registrar@x.edu, 718-000-0000."
    )
    assert "Registrar contact: TODO" in mcc.gold_answer({"kind": "tba"}, [tba], None)


def test_abstain_gold_is_the_word_abstain():
    assert mcc.gold_answer({"kind": "abstain"}, [], "c") == "ABSTAIN"


# ---- data checks ----


def test_weekday_check_compares_the_first_name_of_a_range():
    ok = row(date_start="2026-11-06", weekday_raw="Friday")
    bad = row("x", date_start="2026-11-06", weekday_raw="Monday")
    rng = row("y", date_start="2026-12-15", date_end="2026-12-21", weekday_raw="Tuesday-Monday")
    assert mcc.weekday_problems([ok, rng]) == []
    assert mcc.weekday_problems([bad])[0].startswith("x: printed Monday")


def test_repeated_events_and_weekend_deadlines():
    a = row("a", event="College Closed")
    b = row("b", event="College Closed", term="Winter 2027")
    sunday = row("c", event="Last day to drop.", date_start="2027-01-03", weekday_raw="Sunday")
    assert mcc.repeated_events([a, b, sunday]) == ['a, b: "College Closed" on 2026-11-06']
    assert mcc.weekend_deadlines([a, sunday])[0].startswith("c: Sunday")


# ---- the real file ----


@pytest.fixture(scope="module")
def events():
    return json.loads(mcc.CALENDAR.read_text(encoding="utf-8"))


def test_every_candidate_row_exists_and_ids_run_from_q61(events):
    items = mcc.build(events, "contact")
    assert [c["id"] for c in items][:2] == ["q61", "q62"]
    assert len({c["id"] for c in items}) == len(items) >= 14
    assert all("calendar" in c["tags"] for c in items)
    assert all(len(c["rows"]) == len(c["spec"]["ids"]) for c in items)


def test_the_real_tba_and_winter_year_cases(events):
    gold = {c["spec"]["category"]: c["gold"] for c in mcc.build(events, "contact")}
    assert "Not announced yet" in gold["TBA row"]
    assert "December 28, 2026" in gold["simple date, Winter 2027 (December: year 2026)"]
    assert "January 4, 2027" in gold["simple date, Winter 2027 (January: year 2027)"]


def test_output_is_deterministic(events):
    first = mcc.render(events, "contact", ["q1 (dev): x"])
    assert first == mcc.render(events, "contact", ["q1 (dev): x"])
    assert "## Checklist: owner decisions" in first and "| q61 | yes | yes | keep | dev |" in first


def test_the_script_does_not_touch_the_questions_file():
    assert "questions.jsonl" in mcc.QUESTIONS.name
    source = (ROOT / "scripts" / "make_calendar_candidates.py").read_text()
    assert "QUESTIONS.write" not in source and "open(QUESTIONS" not in source
