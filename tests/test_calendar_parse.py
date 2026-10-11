from datetime import date
from pathlib import Path

import pytest

from cta.parse.calendar import (
    Extraction,
    Line,
    Row,
    applies_to,
    bold_of,
    build_events,
    extract_pdf,
    joined_lines,
    parse_date_text,
    parse_last_updated,
    resolve_dates,
    start_year,
    weekday_check,
)

FIXTURE = Path(__file__).parent / "fixtures" / "calendar" / "winter_2027.pdf"
EDGE = 582.0


def line(text, x1=300.0, first=20.0, bold=False, page=1):
    return Line(text, page, 0.0, x1, first, [bold] * len(text.replace(" ", "")))


def row(date_text, day_text, *events, page=1):
    return Row(page, 0, 10, [line(date_text)], [line(day_text)], [line(t) for t in events])


def extraction(term, rows):
    return Extraction("x.pdf", f"{term.upper()} ACADEMIC CALENDAR*", term, "Last updated: 7/27/26",
                      rows, [], [], [], EDGE)  # fmt: skip


def test_parse_date_text_forms():
    assert parse_date_text("September 03") == {"m1": 9, "d1": 3, "m2": 9, "d2": None, "year": None}
    assert parse_date_text("September 11-13")["d2"] == 13
    assert parse_date_text("January 01, 2027")["year"] == 2027
    assert parse_date_text("December 30 - January 2") == {
        "m1": 12,
        "d1": 30,
        "m2": 1,
        "d2": 2,
        "year": None,
    }
    assert parse_date_text("TBA") == {"tba": True}
    assert parse_date_text("Someday") is None
    assert parse_date_text("Sept 03") is None  # abbreviations are not guessed


def test_resolve_dates_single_range_and_cross_month():
    one = parse_date_text("September 11-13")
    assert resolve_dates(one, 2026) == (date(2026, 9, 11), date(2026, 9, 13))
    assert resolve_dates(parse_date_text("May 03"), 2027) == (date(2027, 5, 3), None)
    cross = parse_date_text("December 30 - January 2")
    assert resolve_dates(cross, 2026) == (date(2026, 12, 30), date(2027, 1, 2))


def test_start_year_winter_starts_in_the_year_before_only_if_the_table_starts_in_december():
    assert start_year("Winter 2027", 12) == 2026 and start_year("Winter 2027", 11) == 2026
    assert start_year("Winter 2027", 1) == 2027
    assert start_year("Fall 2026", 7) == 2026 and start_year("Spring 2027", 1) == 2027


def test_year_rolls_over_when_the_table_goes_from_december_to_january():
    rows = [row("December 28", "Monday", "a"), row("January 01", "Friday", "b"),
            row("February 01", "Monday", "c")]  # fmt: skip
    ex = extraction("Winter 2027", rows)
    events, unparsed = build_events(ex, "x.pdf")
    assert [e["date_start"] for e in events] == ["2026-12-28", "2027-01-01", "2027-02-01"]
    assert unparsed == []


def test_fall_table_crosses_into_january_with_a_printed_year():
    ex = extraction(
        "Fall 2026", [row("December 31", "Thursday", "a"), row("January 01, 2027", "Friday", "b")]
    )
    events, _ = build_events(ex, "x.pdf")
    assert [e["date_start"] for e in events] == ["2026-12-31", "2027-01-01"]
    assert events[1]["notes"] is None  # the printed year agrees with the table position


def test_printed_year_that_disagrees_is_noted_and_the_printed_year_wins():
    ex = extraction(
        "Fall 2026", [row("July 09", "Thursday", "a"), row("January 01, 2028", "Saturday", "b")]
    )
    events, _ = build_events(ex, "x.pdf")
    assert events[1]["date_start"] == "2028-01-01"
    assert "PDF prints year 2028, table position gives 2027" in events[1]["notes"]


def test_weekday_check_ok_and_mismatch_and_ranges():
    assert weekday_check("2026-12-28", None, "Monday") == "ok"
    assert (
        weekday_check("2026-12-28", None, "Tuesday") == "MISMATCH: printed Tuesday, date is Monday"
    )
    assert weekday_check("2026-09-11", "2026-09-13", "Friday-Sunday") == "ok"
    assert weekday_check("2026-12-15", "2026-12-21", "Tuesday-Monday") == "ok"
    assert weekday_check("2026-09-11", "2026-09-13", "Friday-Monday").startswith("MISMATCH")
    assert weekday_check("2026-09-11", "2026-09-13", "Friday").startswith("MISMATCH")
    assert weekday_check(None, None, "TBA") == "n/a"
    assert weekday_check("2026-09-11", None, "Fri").startswith("MISMATCH: unreadable")


def test_a_wrong_weekday_is_reported_and_the_date_is_not_changed():
    ex = extraction("Winter 2027", [row("December 28", "Tuesday", "a")])
    events, _ = build_events(ex, "x.pdf")
    assert events[0]["date_start"] == "2026-12-28"  # not moved to a Tuesday
    assert weekday_check(events[0]["date_start"], None, events[0]["weekday_raw"]).startswith(
        "MISMATCH"
    )


def test_tba_row_keeps_null_dates_and_the_printed_text():
    ex = extraction(
        "Spring 2027",
        [row("May 31", "Monday", "a"), row("TBA", "TBA", "87th Commencement Ceremony")],
    )
    events, unparsed = build_events(ex, "x.pdf")
    tba = events[1]
    assert (tba["date_start"], tba["date_end"], tba["date_raw"], tba["weekday_raw"]) == (
        None,
        None,
        "TBA",
        "TBA",
    )
    assert unparsed == []


def test_one_event_per_printed_line_of_a_cell_with_the_rows_date():
    ex = extraction(
        "Winter 2027",
        [row("January 04", "Monday", "Start of session.", "Classes begin", "Last day")],
    )
    events, _ = build_events(ex, "x.pdf")
    assert [e["event"] for e in events] == ["Start of session.", "Classes begin", "Last day"]
    assert {e["date_start"] for e in events} == {"2027-01-04"}
    assert [e["id"] for e in events] == ["winter-2027-001", "winter-2027-002", "winter-2027-003"]


def test_rows_that_cannot_be_parsed_are_reported_not_dropped():
    two_dates = Row(
        1, 0, 10, [line("January 01"), line("January 03")], [line("Friday")], [line("x")]
    )
    bad_date = row("Someday", "Monday", "y")
    ex = extraction("Winter 2027", [two_dates, bad_date, row("January 04", "Monday", "z")])
    events, unparsed = build_events(ex, "x.pdf")
    assert [e["event"] for e in events] == ["z"]
    assert [u["why"] for u in unparsed] == [
        "2 date, 1 day, 1 event lines",
        "date could not be parsed",
    ]


def test_joined_lines_rules():
    first = line(
        "Deadline for appeals (students dismissed Spring 2026 for potential Summer/Fall",
        x1=578,
        first=40,
    )
    # lowercase or digit start continues the line above
    assert len(joined_lines([first, line("2027 return).", first=22)], EDGE)) == 1
    assert (
        len(
            joined_lines(
                [line("Plan Week: connect", x1=444), line("with an advisor.", first=20)], EDGE
            )
        )
        == 1
    )
    # a first word that would not fit in the space left continues the line above
    full = line("... Veteran student populations.", x1=563)
    assert len(joined_lines([full, line("Registration by appointment only.", first=42)], EDGE)) == 1
    # a capital letter and room on the line above: a new event
    assert len(joined_lines([line("A", x1=300), line("Last day to add", first=15)], EDGE)) == 2
    assert (
        len(joined_lines([line("Return).", x1=450), line("For more info :- www", first=13)], EDGE))
        == 2
    )
    assert len(joined_lines([], EDGE)) == 0


def test_joined_event_has_a_note_and_the_joined_text():
    first = line("Deadline (students dismissed for Summer/Fall", x1=578, first=40)
    cell = [first, line("2027 return).", first=22), line("For more info")]
    ex = extraction("Winter 2027", [Row(1, 0, 10, [line("January 08")], [line("Friday")], cell)])
    events, _ = build_events(ex, "x.pdf")
    assert [e["event"] for e in events] == [
        "Deadline (students dismissed for Summer/Fall 2027 return).",
        "For more info",
    ]
    assert events[0]["notes"] == "printed on 2 lines; joined as wrapped text"
    assert events[1]["notes"] is None


def test_applies_to_only_when_the_text_says_so():
    reg = "Online registration for Fall 2027 begins for all students."
    assert applies_to(reg) == "all students"
    early = (
        "Early online registration for Fall 2027 begins for ASAP, CSTEP, Honors, SEEK, "
        "Seniors & Veteran student populations. Registration by appointment only."
    )
    assert applies_to(early) == "ASAP, CSTEP, Honors, SEEK, Seniors & Veteran student populations"
    appeal = "Deadline (students dismissed Fall 2025 or earlier for potential Fall 2026 return)."
    assert (
        applies_to(appeal)
        == "students dismissed Fall 2025 or earlier for potential Fall 2026 return"
    )
    assert applies_to("Last day to add a course.") is None
    assert applies_to("Faculty to inform students of midterm progress reports") is None


def test_bold_is_true_false_or_null_when_mixed():
    assert bold_of([line("a b", bold=True)]) is True
    assert bold_of([line("a b", bold=False)]) is False
    assert bold_of([line("ab", bold=True), line("cd", bold=False)]) is None
    mixed = Line("ab", 1, 0, 1, 1, [True, False])
    ex = extraction("Winter 2027", [Row(1, 0, 10, [line("January 08")], [line("Friday")], [mixed])])
    event = build_events(ex, "x.pdf")[0][0]
    assert event["bold"] is None and event["notes"] == "line mixes bold and regular text"


def test_parse_last_updated():
    assert parse_last_updated("Last updated: 9/15/26") == "2026-09-15"
    assert parse_last_updated("Last updated: 9 / 15 / 2026") == "2026-09-15"
    assert parse_last_updated("nothing here") is None and parse_last_updated(None) is None


def test_event_fields_are_exactly_the_agreed_ones_and_verified_is_false():
    ex = extraction("Winter 2027", [row("January 04", "Monday", "a")])
    event = build_events(ex, "data/pdfs/winter_2027.pdf")[0][0]
    assert set(event) == {
        "id", "term", "event", "date_start", "date_end", "date_raw", "weekday_raw", "applies_to",
        "bold", "source_pdf", "source_page", "pdf_last_updated", "verified", "notes",
    }  # fmt: skip
    assert event["verified"] is False and event["source_pdf"] == "data/pdfs/winter_2027.pdf"
    assert event["pdf_last_updated"] == "2026-07-27" and event["source_page"] == 1


# ---- the real Winter 2027 PDF -------------------------------------------------------------


@pytest.fixture(scope="module")
def winter():
    ex = extract_pdf(FIXTURE)
    events, unparsed = build_events(ex, "winter_2027.pdf")
    return ex, events, unparsed


def test_real_winter_pdf_term_and_last_updated(winter):
    ex, events, _ = winter
    assert ex.term == "Winter 2027" and ex.last_updated_raw == "Last updated: 7/27/26"
    assert {e["pdf_last_updated"] for e in events} == {"2026-07-27"}
    assert any("subject to change" in t for t in ex.excluded)  # footnotes are not events


def test_real_winter_pdf_has_26_events_and_nothing_unparsed(winter):
    _, events, unparsed = winter
    assert len(events) == 26 and unparsed == []
    assert events[0]["event"] == "Last day to file ePermit request for the Winter Session"
    assert events[0]["date_start"] == "2026-12-28"  # Winter 2027 starts in December 2026
    assert events[-1]["event"] == "Filing period for February 2027 graduation ends"
    assert events[-1]["date_start"] == "2027-02-01"


def test_real_winter_pdf_wrapped_line_and_bold(winter):
    _, events, _ = winter
    wrapped = [e for e in events if e["notes"]]
    assert len(wrapped) == 1 and wrapped[0]["event"].startswith("Deadline for Course and Standa")
    assert wrapped[0]["event"].endswith("Summer/Fall 2027 return).")
    assert wrapped[0]["applies_to"].startswith("students dismissed Spring 2026")
    bold = [e["event"] for e in events if e["bold"]]
    assert len(bold) == 9 and "College Closed" in bold and "Last day to add a course." in bold
    assert next(e for e in events if e["event"] == "Classes begin")["bold"] is False
    assert all(e["bold"] is not None for e in events)


def test_real_winter_pdf_weekdays_all_match(winter):
    _, events, _ = winter
    assert [
        e["event"]
        for e in events
        if weekday_check(e["date_start"], e["date_end"], e["weekday_raw"]) != "ok"
    ] == []


def test_a_winter_table_that_starts_in_january_is_dated_in_the_term_year():
    ex = extraction("Winter 2027", [row("January 04", "Monday", "a")])
    assert build_events(ex, "x.pdf")[0][0]["date_start"] == "2027-01-04"
