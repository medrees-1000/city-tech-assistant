import copy
import json
from datetime import date
from pathlib import Path

import pytest

from cta.parse.calendar import build_events, extract_pdf
from cta.parse.calendar_build import (
    build_all,
    load_terms,
    refuses_overwrite,
    render_verification,
    run_checks,
)
from cta.validate.calendar import (
    UnverifiedCalendarError,
    calendar_status,
    check_against_pdf,
    check_dates_in_window,
    check_duplicates,
    check_no_calendar_terms,
    check_required_fields,
    check_term_markers,
    check_term_matches_pdf,
    check_verified,
    check_weekdays,
    load_events_for_indexing,
)

FIXTURES = Path(__file__).parent / "fixtures" / "calendar"
WINDOW = {"Winter 2027": (date(2026, 12, 20), date(2027, 2, 10))}


def ev(**over):
    base = {
        "id": "winter-2027-001", "term": "Winter 2027", "event": "Classes begin",
        "date_start": "2027-01-04", "date_end": None, "date_raw": "January 04",
        "weekday_raw": "Monday", "applies_to": None, "bold": False, "source_pdf": "w.pdf",
        "source_page": 1, "pdf_last_updated": "2026-07-27", "verified": False, "notes": None,
    }  # fmt: skip
    return {**base, **over}


def checks_of(findings):
    return sorted(f.check for f in findings)


# ---- rules on synthetic rows --------------------------------------------------------------


def test_clean_row_has_no_findings():
    assert check_required_fields([ev()]) == []
    assert check_dates_in_window([ev()], WINDOW) == []
    assert check_weekdays([ev()]) == [] and check_duplicates([ev()]) == []


@pytest.mark.parametrize(
    "field", ["term", "event", "source_pdf", "source_page", "pdf_last_updated"]
)
def test_every_row_needs_term_event_source_page_and_last_updated(field):
    found = check_required_fields([ev(**{field: None})])
    assert [f.check for f in found] == ["required_fields"] and field in found[0].message


def test_row_needs_a_date_or_an_explicit_tba():
    assert checks_of(check_required_fields([ev(date_start=None)])) == ["required_fields"]
    assert checks_of(check_required_fields([ev(date_start="soon")])) == ["required_fields"]
    tba = ev(date_raw="TBA", weekday_raw="TBA", date_start=None, date_end=None)
    assert check_required_fields([tba]) == []
    assert check_required_fields([ev(date_raw="TBA", date_end="2027-01-05")]) != []


def test_source_page_must_be_a_positive_page_number_and_verified_a_bool():
    assert checks_of(check_required_fields([ev(source_page=0)])) == ["required_fields"]
    assert checks_of(check_required_fields([ev(verified="no")])) == ["required_fields"]
    assert check_required_fields([ev(verified=True)]) == []  # the owner will set this


def test_ids_must_be_unique():
    assert checks_of(check_required_fields([ev(), ev(event="other")])) == ["ids"]


def test_dates_outside_the_term_window_fail_with_the_date_shown():
    late = ev(date_start="2027-03-01")
    early = ev(date_start="2026-11-01")
    found = check_dates_in_window([late, early], WINDOW)
    assert checks_of(found) == ["date_window", "date_window"]
    assert "2027-03-01" in found[0].message
    wrong_year = ev(date_start="2026-01-04")  # the classic year slip
    assert checks_of(check_dates_in_window([wrong_year], WINDOW)) == ["date_window"]


def test_window_edges_are_inclusive_and_ranges_are_checked_at_both_ends():
    assert (
        check_dates_in_window([ev(date_start="2026-12-20"), ev(date_start="2027-02-10")], WINDOW)
        == []
    )
    assert checks_of(
        check_dates_in_window([ev(date_start="2027-02-09", date_end="2027-02-12")], WINDOW)
    ) == ["date_window"]
    assert checks_of(
        check_dates_in_window([ev(date_start="2027-01-05", date_end="2027-01-04")], WINDOW)
    ) == ["date_range"]
    tba = ev(date_start=None)
    assert check_dates_in_window([tba], WINDOW) == []


def test_weekday_mismatch_is_listed_and_names_both_days():
    found = check_weekdays([ev(weekday_raw="Tuesday")])
    assert checks_of(found) == ["weekday"]
    assert "printed Tuesday, date is Monday" in found[0].message
    assert check_weekdays([ev(date_raw="TBA", weekday_raw="TBA", date_start=None)]) == []


def test_duplicate_rows_are_found_but_the_same_event_on_another_date_is_fine():
    assert checks_of(check_duplicates([ev(id="a"), ev(id="b")])) == ["duplicates"]
    other_day = ev(id="b", date_raw="January 05", weekday_raw="Tuesday", date_start="2027-01-05")
    assert check_duplicates([ev(id="a"), other_day]) == []


def test_term_markers_start_and_end_exist_once_and_in_order():
    start = ev(id="1", event="Start of Winter 2027 session.", date_start="2027-01-04")
    end = ev(id="2", event="End of Winter 2027 Session", date_start="2027-01-25")
    assert check_term_markers([start, end], "Winter 2027") == []
    assert len(check_term_markers([start], "Winter 2027")) == 1
    assert len(check_term_markers([start, end, end], "Winter 2027")) == 1
    swapped = ev(id="2", event="End of Winter 2027 Session", date_start="2027-01-01")
    assert len(check_term_markers([start, swapped], "Winter 2027")) == 1


def test_terms_without_a_calendar_produce_no_rows_and_abstain():
    rows = [ev()]
    assert calendar_status(rows, "Winter 2027") == "available"
    assert calendar_status(rows, "Summer 2027") == "abstain"
    assert calendar_status(rows, "Fall 2027") == "abstain"
    assert check_no_calendar_terms(rows, ["Summer 2027", "Fall 2027"]) == []
    leaked = [ev(term="Fall 2027")]
    assert checks_of(check_no_calendar_terms(leaked, ["Fall 2027"])) == [
        "no_calendar",
        "no_calendar",
    ]


# ---- the real Winter 2027 PDF: the checks pass, and fail when the table is damaged ---------


@pytest.fixture(scope="module")
def real():
    ex = extract_pdf(FIXTURES / "winter_2027.pdf")
    events, unparsed = build_events(ex, "winter_2027.pdf")
    return ex, events, unparsed


def test_real_winter_table_matches_the_pdf(real):
    ex, events, _ = real
    assert check_against_pdf(events, ex) == []
    assert check_term_matches_pdf(ex, "Winter 2027") == []
    assert check_term_markers(events, "Winter 2027") == []
    assert check_dates_in_window(events, WINDOW) == []
    assert check_required_fields(events) == [] and check_duplicates(events) == []


def test_an_event_dropped_from_the_table_is_found(real):
    ex, events, _ = real
    found = check_against_pdf(events[:5] + events[6:], ex)
    assert "pdf_missing" in checks_of(found)


def test_an_event_that_is_not_in_the_pdf_is_found(real):
    ex, events, _ = real
    extra = events + [{**events[0], "id": "winter-2027-027", "event": "Made up holiday"}]
    assert "pdf_extra" in checks_of(check_against_pdf(extra, ex))


def test_changed_event_text_is_found(real):
    ex, events, _ = real
    changed = copy.deepcopy(events)
    changed[3]["event"] = changed[3]["event"].replace("Winter", "Spring")
    found = checks_of(check_against_pdf(changed, ex))
    assert "event_lines" in found and "pdf_missing" in found and "pdf_extra" in found


def test_a_duplicated_event_is_found_by_the_pdf_check_too(real):
    ex, events, _ = real
    doubled = events[:4] + [events[3]] + events[4:]
    assert "pdf_extra" in checks_of(check_against_pdf(doubled, ex))


def test_a_date_moved_by_a_day_fails_the_weekday_check(real):
    _, events, _ = real
    moved = copy.deepcopy(events)
    moved[0]["date_start"] = "2026-12-29"  # the PDF prints Monday
    assert checks_of(check_weekdays(moved)) == ["weekday"]


def test_wrong_term_for_a_pdf_is_found(real):
    ex, _, _ = real
    assert checks_of(check_term_matches_pdf(ex, "Spring 2027")) == ["term"]


# ---- build and the verification document, from the real Winter PDF -------------------------


CONFIG = {
    "terms": [
        {
            "term": "Winter 2027",
            "pdf": "winter_2027.pdf",
            "window": [date(2026, 12, 20), date(2027, 2, 10)],
        }
    ],
    "no_calendar_terms": ["Summer 2027", "Fall 2027"],
}


def test_build_all_and_every_check_pass_on_the_fixture():
    events, extractions, unparsed = build_all(CONFIG, FIXTURES)
    assert len(events) == 26 and [e["verified"] for e in events] == [False] * 26
    assert run_checks(events, extractions, unparsed, CONFIG) == []


def test_verification_document_has_one_row_per_event_with_the_agreed_columns():
    events, extractions, _ = build_all(CONFIG, FIXTURES)
    doc = render_verification(events, extractions)
    assert (
        "| # | Printed date | Printed day | Event text | Parsed date | Weekday check | OK |" in doc
    )
    rows = [line for line in doc.splitlines() if line.startswith("| ") and line.endswith("| [ ] |")]
    assert len(rows) == 26
    assert rows[0].startswith(
        "| 1 | December 28 | Monday | Last day to file ePermit request for the Winter Session |"
    )
    assert "| 2026-12-28 | ok | [ ] |" in rows[0]
    assert any("**College Closed**" in r for r in rows)  # bold in the PDF
    assert "Weekday mismatches: none." in doc and "Rows made from two printed lines" in doc
    assert "last updated 2026-07-27" in doc


def test_title_that_does_not_match_the_config_stops_the_build():
    wrong = {**CONFIG, "terms": [{**CONFIG["terms"][0], "term": "Fall 2026"}]}
    with pytest.raises(SystemExit):
        build_all(wrong, FIXTURES)


def test_config_file_lists_the_three_terms_and_two_terms_without_a_calendar():
    config = load_terms()
    assert [t["term"] for t in config["terms"]] == ["Fall 2026", "Winter 2027", "Spring 2027"]
    assert config["no_calendar_terms"] == ["Summer 2027", "Fall 2027"]
    windows = {t["term"]: t["window"] for t in config["terms"]}
    assert windows["Winter 2027"] == [date(2026, 12, 20), date(2027, 2, 10)]
    assert all(low < high for low, high in windows.values())


# ---- all three real PDFs (not committed: skipped when data/pdfs is missing) ----------------

ROOT = Path(__file__).resolve().parents[1]
HAVE_PDFS = all(
    (ROOT / f"data/pdfs/{n}.pdf").exists() for n in ("fall_2026", "winter_2027", "spring_2027")
)


@pytest.mark.skipif(not HAVE_PDFS, reason="data/pdfs is not committed")
def test_all_three_real_calendars_build_with_no_findings():
    config = load_terms()
    events, extractions, unparsed = build_all(config)
    counts = {
        t: sum(e["term"] == t for e in events) for t in ("Fall 2026", "Winter 2027", "Spring 2027")
    }
    assert counts == {"Fall 2026": 55, "Winter 2027": 26, "Spring 2027": 55}
    assert run_checks(events, extractions, unparsed, config) == []
    tba = [e for e in events if e["date_start"] is None]
    assert [(e["term"], e["date_raw"], e["event"]) for e in tba] == [
        ("Spring 2027", "TBA", "87th Commencement Ceremony")
    ]
    assert calendar_status(events, "Fall 2027") == "abstain"


# ---- verification: nothing is indexed until every event is verified -------------------------

EVENTS_FILE = Path(__file__).resolve().parents[1] / "data" / "calendar" / "calendar_events.json"


def verified(**over):
    return ev(verified=True, verified_by="owner", verified_on="2026-10-11", **over)


def write(tmp_path, events):
    path = tmp_path / "calendar_events.json"
    path.write_text(json.dumps(events), encoding="utf-8")
    return path


def test_check_verified_accepts_a_fully_verified_event():
    assert check_verified([verified()]) == []


def test_check_verified_fails_when_verified_is_false_or_missing():
    found = check_verified(
        [ev(id="a"), ev(id="b", verified=None), {**verified(id="c"), "verified": "yes"}]
    )
    assert [(f.check, f.course) for f in found] == [
        ("verified", "a"),
        ("verified", "b"),
        ("verified", "c"),
    ]


def test_verified_event_needs_who_and_when():
    no_by = {**verified(id="a"), "verified_by": ""}
    no_on = {k: v for k, v in verified(id="b").items() if k != "verified_on"}
    bad_on = {**verified(id="c"), "verified_on": "yesterday"}
    found = check_verified([no_by, no_on, bad_on])
    assert [f.course for f in found] == ["a", "b", "c"]


def test_loading_for_indexing_returns_the_events_when_all_are_verified(tmp_path):
    events = [verified(id="a"), verified(id="b")]
    assert load_events_for_indexing(write(tmp_path, events)) == events


def test_loading_for_indexing_fails_if_any_event_is_not_verified(tmp_path):
    path = write(
        tmp_path, [verified(id="a"), ev(id="winter-2027-007", verified=False), verified(id="c")]
    )
    with pytest.raises(UnverifiedCalendarError) as err:
        load_events_for_indexing(path)
    assert "winter-2027-007" in str(err.value) and "1 calendar problems" in str(err.value)


def test_rebuilding_never_overwrites_verified_rows_unless_forced(tmp_path):
    path = write(tmp_path, [verified(id="a")])
    assert refuses_overwrite(path, force=False) is True
    assert refuses_overwrite(path, force=True) is False
    assert refuses_overwrite(write(tmp_path, [ev(id="a")]), force=False) is False  # nothing to lose
    assert refuses_overwrite(tmp_path / "missing.json", force=False) is False


def test_the_committed_calendar_file_is_fully_verified_and_loads_for_indexing():
    events = load_events_for_indexing(EVENTS_FILE)
    assert len(events) == 136
    assert {e["verified_by"] for e in events} == {"owner"}
    assert {e["verified_on"] for e in events} == {"2026-10-11"}
    assert all(e["verified"] is True for e in events)


def test_the_spring_sap_deadline_carries_the_cross_source_conflict_note():
    events = json.loads(EVENTS_FILE.read_text(encoding="utf-8"))
    row = next(e for e in events if e["id"] == "spring-2027-043")
    assert row["event"].startswith(
        "Deadline to submit Satisfactory Academic Progress (SAP) Appeals"
    )
    assert (row["date_raw"], row["weekday_raw"], row["date_start"]) == (
        "March 31",
        "Wednesday",
        "2027-03-31",
    )
    assert row["notes"] == (
        "Financial Aid SAP page lists Tuesday, March 30, 2027. "
        "The calendar PDF is the source for dates."
    )
    other_notes = [e["id"] for e in events if e["notes"] and "joined" not in e["notes"]]
    assert other_notes == ["spring-2027-043"]  # no other note was added
    fall = next(e for e in events if e["id"] == "fall-2026-044")
    assert (
        fall["notes"] is None and fall["date_start"] == "2026-11-13"
    )  # Fall agrees with the SAP page


@pytest.mark.skipif(not HAVE_PDFS, reason="data/pdfs is not committed")
def test_verifying_changed_nothing_but_the_verification_fields_and_one_note():
    config = load_terms()
    rebuilt, _, _ = build_all(config)
    saved = json.loads(EVENTS_FILE.read_text(encoding="utf-8"))
    assert [e["id"] for e in saved] == [e["id"] for e in rebuilt]
    skip = {"verified", "verified_by", "verified_on", "notes"}
    for old, new in zip(rebuilt, saved, strict=True):
        assert {k: v for k, v in old.items() if k not in skip} == {
            k: v for k, v in new.items() if k not in skip
        }
        if new["id"] != "spring-2027-043":
            assert old["notes"] == new["notes"]
