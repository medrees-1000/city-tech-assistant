import copy
import json
from collections import Counter
from pathlib import Path

import pytest

from cta.parse.pdf_docs import (
    DOCUMENTS,
    FlowConfig,
    PLine,
    Repairs,
    continues,
    flow_blocks,
    join_lines,
    merge_bold_runs,
    parse_dropping_withdrawing,
    parse_refund_calendar,
    pdf_date,
    printed_update,
    strip_bullet,
    table_markdown,
    trim_empty_edges,
)
from cta.settings import load_sources
from cta.validate.pdfs import (
    check_dates_and_terms,
    check_every_character_placed,
    check_every_line_placed,
    check_no_replacement_characters,
    check_tables_complete,
    markdown_text,
    run_pdf_checks,
)

FIX = Path(__file__).parent / "fixtures" / "pdfs"
REFUND = FIX / "Award_Year_2026_2027_Financial_Aid_Payment_Refund _Calendar.pdf"
DROP = FIX / "Fall_2026_Dropping_and_Withdrawing_from_Classes.pdf"
ROOT = Path(__file__).resolve().parents[1]
PDFS = ROOT / "data" / "pdfs"
HAVE_ALL = all((PDFS / name).exists() for _, name, _ in DOCUMENTS)


def line(text, top, page=1, size=12.0, bold=False, x0=72.0, x1=300.0, first=30.0, margin=540.0):
    plain = text.replace("**", "")
    return PLine(text, plain, page, top, top + size, x0, x1, size, bold, 792.0, first, margin)


def flow(lines, **cfg):
    items = [("line", ln) for ln in lines]
    return flow_blocks(items, FlowConfig(**cfg), Repairs())


# ---- small pure helpers -----------------------------------------------------------------


def test_pdf_date_parses_metadata_dates_and_does_not_invent_a_zone():
    assert pdf_date("D:20260727092220-04'00'") == "2026-07-27T09:22:20-04:00"
    assert pdf_date("D:20260828122519Z") == "2026-08-28T12:25:19+00:00"
    assert pdf_date("D:20260116153141") == "2026-01-16T15:31:41"
    assert pdf_date(None) is None and pdf_date("garbage") is None


def test_printed_update_dates():
    assert printed_update("Updated 06/08/2026") == ("Updated 06/08/2026", "2026-06-08")
    assert printed_update("Last updated: 9/15/26")[1] == "2026-09-15"
    assert printed_update("Award year 2026-2027") == (None, None)


def test_trim_empty_edges_drops_artifact_rows_and_columns_but_keeps_inner_blanks():
    rows = [["", "", ""], ["a", "b", ""], ["", "c", ""], ["", "", ""]]
    assert trim_empty_edges(rows) == [["a", "b"], ["", "c"]]
    assert trim_empty_edges([["", ""]]) == []


def test_table_markdown_has_a_blank_header_and_escapes_pipes():
    md = table_markdown([["a|b", "c"], ["", "d"]])
    assert md.splitlines() == ["|  |  |", "| --- | --- |", "| a\\|b | c |", "|  | d |"]


def test_join_lines_joins_a_hyphenated_line_without_a_space_and_records_it():
    repairs = Repairs()
    text = join_lines(
        ["a three-", "quarter-time student", "next"],
        ["a three-", "quarter-time student", "next"],
        repairs,
    )
    assert text == "a three-quarter-time student next"
    assert [r["kind"] for r in repairs.items] == ["hyphen_join"]


def test_bold_runs_across_lines_are_merged_and_bullets_stripped():
    assert merge_bold_runs("**three-** **quarter-time**") == "**three- quarter-time**"
    assert merge_bold_runs("**a** **b**") == "**a b**"
    assert strip_bullet("• Will not appear") == "Will not appear"
    assert strip_bullet(" text") == "text"


def test_continues_rules():
    prev = line("a line that runs almost to the right margin of the page", 100, x1=530.0)
    assert continues(prev, line("lowercase start", 115, first=40.0))
    assert continues(prev, line("2027 return).", 115, first=30.0))
    assert continues(prev, line("Registration by appointment", 115, first=60.0))  # does not fit
    short = line("A short line.", 100, x1=300.0)
    assert not continues(
        short, line("Next paragraph starts here", 115, first=30.0)
    )  # fits: hard break
    assert not continues(
        prev, line("Example:", 115, bold=True, first=20.0)
    )  # a label starts a paragraph


# ---- the flow reader on synthetic lines ---------------------------------------------------


def test_bold_lines_without_final_punctuation_and_with_space_above_are_headings():
    blocks, _ = flow([
        line("**Title**", 100, bold=True), line("Intro text.", 130, x1=200),
        line("**Dropping Classes**", 170, bold=True), line("Body text.", 185, x1=200),
        line("**Attendance is required.**", 230, bold=True),
        line("**Example:**", 245, bold=True), line("Text after the label.", 260, x1=200),
    ])  # fmt: skip
    assert [(k, lv) for k, lv, _ in blocks if k == "h"] == [("h", 1), ("h", 2)]
    assert [t for k, _, t in blocks if k == "p"] == [
        "Intro text.", "Body text.", "**Attendance is required.**", "**Example:**",
        "Text after the label.",
    ]  # fmt: skip


def test_a_bold_label_ending_in_a_colon_is_a_heading_only_with_space_above():
    blocks, _ = flow(
        [line("Some text here.", 100, x1=200), line("**Book Dates:**", 160, bold=True)]
    )
    assert blocks[-1] == ("h", 1, "Book Dates:")
    blocks, _ = flow([line("Some text here.", 100, x1=200), line("**Example:**", 115, bold=True)])
    assert blocks[-1][0] == "p"


def test_two_bold_lines_close_together_are_one_heading():
    title = line("**Fall 2026**", 100, size=14.3, bold=True)
    second = line("**Important Information About Dropping**", 118, bold=True)
    blocks, _ = flow([title, second])
    assert blocks == [("h", 1, "Fall 2026 Important Information About Dropping")]


def test_bullets_become_a_list_and_indented_lines_continue_an_item():
    blocks, _ = flow([
        line("The course:", 100, x1=200),
        line("• Will not appear", 115, x0=90.0, x1=250),
        line("• Will not be included in the calculation", 130, x0=90.0, x1=500),
        line("purposes.", 145, x0=108.0, x1=150),
        line("After the list.", 175, x1=200),
    ])  # fmt: skip
    assert blocks[1] == (
        "list",
        0,
        "- Will not appear\n- Will not be included in the calculation purposes.",
    )
    assert blocks[2] == ("p", 0, "After the list.")


def test_a_list_continues_across_a_page_break_and_a_sentence_does_not_without_a_lowercase_start():
    blocks, _ = flow([
        line("• first item.", 700, page=1, x0=90.0), line("• second item.", 100, page=2, x0=90.0),
        line("A paragraph ending", 140, page=2, x1=200),
        line("New paragraph on page 3.", 100, page=3),
    ])  # fmt: skip
    assert blocks[0] == ("list", 0, "- first item.\n- second item.")
    assert [t for k, _, t in blocks if k == "p"] == [
        "A paragraph ending",
        "New paragraph on page 3.",
    ]


def test_a_paragraph_continues_across_pages_only_with_a_lowercase_start():
    blocks, _ = flow(
        [
            line("The sentence is cut", 700, page=1, x1=530),
            line("by the page end.", 100, page=2, x1=300),
        ]
    )
    assert blocks == [("p", 0, "The sentence is cut by the page end.")]


def test_excluded_lines_are_listed_with_their_reason():
    def exclude(ln):
        return "page number" if ln.plain.isdigit() else None

    blocks, excluded = flow([line("Text.", 100), line("2", 750)], exclude=exclude)
    assert excluded == [{"page": 1, "text": "2", "reason": "page number"}] and len(blocks) == 1


# ---- the refund calendar (real PDF) ------------------------------------------------------


@pytest.fixture(scope="module")
def refund():
    return parse_refund_calendar(REFUND)


def test_refund_calendar_record_fields(refund):
    r = refund
    assert r["title"] == "AWARD YEAR 2026-2027 STUDENT FINANCIAL AID REFUND DATES"
    assert (r["doc_type"], r["scope"], r["aid_year"], r["term"]) == (
        "aid",
        "city_tech",
        "2026-2027",
        None,
    )
    assert (r["pdf_last_updated"], r["pdf_last_updated_raw"]) == (
        "2026-06-08",
        "Updated 06/08/2026",
    )
    assert r["file_modified"] == "2026-07-27T09:22:20-04:00" and r["page_count"] == 2
    assert r["index"] is True and r["status"] == "collected" and r["text_source"] == "text layer"
    assert r["source_file"].endswith("Refund _Calendar.pdf")


def test_refund_calendar_sections(refund):
    assert [(s["level"], s["heading"]) for s in refund["sections"]] == [
        (2, "Attendance"),
        (2, "Financial Aid (Federal Pell, SEOG, Direct Loans) Refund Dates"),
        (2, "Summer 2026, Fall 2026, and Spring 2027 Refund Schedule"),
        (2, "Fall Book Advance Refund Dates (25% of Federal Pell Grant):"),
        (2, "Fall Refund Date: 10/05/2026"),
        (2, "Spring Book Advance Refund Dates (25% of Federal Pell Grant):"),
        (2, "Spring Refund Date: 3/05/2027"),
    ]
    assert refund["sections"][0]["parents"] == [{"level": 1, "heading": refund["title"]}]


def test_refund_dates_are_exactly_as_printed(refund):
    schedule = refund["sections"][2]["markdown"].splitlines()
    first_row = "| 7/24/2026 | 10/02/2026 | 12/04/2026 | 2/22/2027 | 4/30/2027 |"
    assert schedule[:3] == ["|  |  |  |  |  |", "| --- | --- | --- | --- | --- |", first_row]
    assert (
        schedule[-1] == "|  | 11/27/2026 | 2/16/2027 | 4/23/2027 |  |"
    )  # the short last row keeps its blanks
    assert len(schedule) == 12
    assert refund["sections"][3]["markdown"].splitlines()[2:] == [
        "| 8/21/2026 |",
        "| 8/28/2026 |",
        "| 9/04/2026 |",
        "| 9/11/2026 |",
    ]
    assert (
        "will be October 5, 2026. After October 5th, refunds" in refund["sections"][4]["markdown"]
    )
    assert refund["sections"][5]["markdown"].splitlines()[-1] == "| 2/12/2027 |"


def test_refund_ordinals_are_joined_and_the_wn_grade_bold_is_kept(refund):
    attendance = refund["sections"][0]["markdown"]
    assert "through the 21st day each semester" in attendance
    assert attendance.endswith("**Financial Aid will not pay for classes with WN Grades.**")


def test_refund_footer_and_page_number_are_excluded_with_a_reason(refund):
    assert [(e["page"], e["text"]) for e in refund["excluded"]] == [
        (2, "Updated 06/08/2026"),
        (2, "Award year 2026-2027 financial aid payment refund calendar"),
        (2, "2"),
    ]  # fmt: skip
    assert refund["repairs"] == []


# ---- the Dropping and Withdrawing PDF (real) -----------------------------------------------


@pytest.fixture(scope="module")
def dropping():
    return parse_dropping_withdrawing(DROP)


def test_dropping_record_fields(dropping):
    r = dropping
    assert (
        r["title"] == "Fall 2026 Important Information About Dropping and Withdrawing from Classes"
    )
    assert (r["doc_type"], r["scope"], r["term"], r["aid_year"]) == (
        "policy",
        "city_tech",
        "Fall 2026",
        None,
    )
    assert r["pdf_last_updated"] is None and r["pdf_last_updated_raw"] is None  # none is printed
    assert (
        r["file_modified"] == "2026-09-01T09:23:13-04:00"
        and r["file_created"] == "2026-08-28T12:25:19+00:00"
    )
    assert r["index"] is True and r["page_count"] == 3


def test_dropping_sections_are_the_printed_headings_in_order(dropping):
    assert [s["heading"] for s in dropping["sections"]] == [
        "Fall 2026 Important Information About Dropping and Withdrawing from Classes",
        "Dropping Classes",
        "Dropping a Class Before the First Day of the Semester",
        "Dropping a Class On or Before September 3, 2026 (Financial Aid Certification Date)",
        "Dropping a Class After September 3, 2026",
        "Dropping or Withdrawing from All Classes",
        "Withdrawal (W Grade)",
        "Important Notes",
        "Administrative/Academic Withdrawal (WA Grade)",
    ]
    assert {s["level"] for s in dropping["sections"][1:]} == {2}  # the PDF has one heading style


def test_dropping_dates_and_bold_are_as_printed(dropping):
    md = {s["heading"]: s["markdown"] for s in dropping["sections"]}
    after = md["Dropping a Class After September 3, 2026"]
    assert "between **September 4 and September 17, 2026,**" in after
    assert "**WD grade**" in after
    assert "after the 21st day of the semester**" in md["Withdrawal (W Grade)"]
    assert "(after **September 17, 2026,** for Fall 2026)" in md["Withdrawal (W Grade)"]


def test_dropping_hard_line_breaks_stay_separate_paragraphs(dropping):
    after = next(
        s for s in dropping["sections"] if s["heading"].endswith("After September 3, 2026")
    )
    parts = after["markdown"].split("\n\n")
    assert parts[1] == "**Example:**" and parts[3] == "However:"
    notes = next(s for s in dropping["sections"] if s["heading"] == "Important Notes")
    assert len(notes["markdown"].split("\n\n")) == 3


def test_dropping_list_continues_across_the_page_break(dropping):
    after = next(
        s for s in dropping["sections"] if s["heading"].endswith("After September 3, 2026")
    )
    assert after["markdown"].endswith(
        "- Your NYS TAP award may be prorated (reduced) for the semester.\n"
        "- You may use the equivalent of 6 TAP points for that term."
    )  # the first item is at the foot of page 1, the second at the top of page 2


def test_dropping_hyphen_join_and_page_numbers_are_recorded(dropping):
    assert any("three-quarter-time" in s["markdown"] for s in dropping["sections"])
    assert dropping["repairs"] == [
        {"kind": "hyphen_join", "text": "you a three-quarter-time", "count": 1}
    ]
    assert [e["text"] for e in dropping["excluded"]] == ["1", "2", "3"]
    assert {e["reason"] for e in dropping["excluded"]} == {"page number"}


# ---- the checks pass on the real records and fail on damaged ones --------------------------


def test_checks_pass_on_the_real_records(refund, dropping):
    assert run_pdf_checks(refund, REFUND) == []
    assert run_pdf_checks(dropping, DROP) == []


def checks_of(findings):
    return sorted(f.check for f in findings)


def test_a_dropped_sentence_is_found_by_the_character_and_the_line_check(dropping):
    damaged = copy.deepcopy(dropping)
    sec = damaged["sections"][1]
    sec["markdown"] = sec["markdown"].replace(
        "A **drop** occurs when you remove a course from your schedule", "A **drop**"
    )
    assert "chars_missing" in checks_of(check_every_character_placed(damaged, DROP))
    assert "line_not_placed" in checks_of(check_every_line_placed(damaged, DROP))


def test_an_invented_sentence_is_found(dropping):
    damaged = copy.deepcopy(dropping)
    damaged["sections"][1]["markdown"] += "\n\nThis sentence is not in the PDF."
    assert "chars_extra" in checks_of(check_every_character_placed(damaged, DROP))


def test_a_replacement_character_is_found(dropping):
    damaged = copy.deepcopy(dropping)
    damaged["sections"][1]["markdown"] = damaged["sections"][1]["markdown"].replace(
        "drop", "dr�p", 1
    )
    assert checks_of(check_no_replacement_characters(damaged)) == ["replacement_chars"]
    assert check_no_replacement_characters({"source_file": "x", "sections": []}) == []


def test_dates_and_terms_must_match_what_the_pdf_prints(refund, dropping):
    no_aid = {**refund, "aid_year": None}
    assert "aid_year" in checks_of(check_dates_and_terms(no_aid, REFUND))
    no_updated = {**refund, "pdf_last_updated": None}
    assert "pdf_last_updated" in checks_of(check_dates_and_terms(no_updated, REFUND))
    invented = {**dropping, "pdf_last_updated": "2026-08-01"}
    assert "pdf_last_updated" in checks_of(check_dates_and_terms(invented, DROP))
    no_term = {**dropping, "term": None}
    assert "term" in checks_of(check_dates_and_terms(no_term, DROP))
    wrong = {**dropping, "term": "Spring 2027"}
    assert "term" in checks_of(check_dates_and_terms(wrong, DROP))
    assert "dates" in checks_of(
        check_dates_and_terms({**dropping, "file_modified": "yesterday"}, DROP)
    )


def test_a_table_with_a_missing_row_or_cell_or_wrong_width_is_found(refund):
    damaged = copy.deepcopy(refund)
    md = damaged["sections"][2]["markdown"]
    damaged["sections"][2]["markdown"] = md.replace(
        "| 9/25/2026 | 11/20/2026 | 2/05/2027 | 4/16/2027 | 6/25/2027 |\n", ""
    )
    assert "table_cells" in checks_of(check_tables_complete(damaged, REFUND))
    changed = copy.deepcopy(refund)
    changed["sections"][2]["markdown"] = md.replace("10/02/2026", "10/03/2026")
    assert "table_cells" in checks_of(check_tables_complete(changed, REFUND))
    narrow = copy.deepcopy(refund)
    narrow["sections"][2]["markdown"] = md.replace(
        "| 7/24/2026 | 10/02/2026 | 12/04/2026 | 2/22/2027 | 4/30/2027 |", "| 7/24/2026 |"
    )
    assert "table_shape" in checks_of(check_tables_complete(narrow, REFUND))


def test_a_missing_table_is_found_and_a_table_where_none_is_expected_is_found(refund, dropping):
    gone = copy.deepcopy(refund)
    gone["sections"][3]["markdown"] = ""
    assert "tables" in checks_of(check_tables_complete(gone, REFUND))
    assert check_tables_complete(dropping, DROP) == []  # no table expected, none in the PDF


def test_markdown_text_strips_markup():
    md = "**Bold** text\n- item one\n|  |  |\n| --- | --- |\n| a\\|b | c |"
    assert markdown_text(md) == "Bold text\nitem one\n \na|b c"


# ---- the flyer and the CUNYfirst guide (not committed: skipped without data/pdfs) -------------


@pytest.mark.skipif(not HAVE_ALL, reason="data/pdfs is not committed")
def test_flyer_is_read_from_the_text_layer_panel_by_panel():
    from cta.parse.pdf_docs import parse_flyer

    r = parse_flyer(PDFS / "Special_Circumstances_Flyer_2025_2026_2026_2027.pdf")
    assert r["title"] == "SPECIAL CIRCUMSTANCES 2025-2026 & 2026-2027"
    assert (r["doc_type"], r["scope"], r["aid_year"]) == (
        "aid",
        "city_tech",
        "2025-2026 & 2026-2027",
    )
    assert r["pdf_last_updated"] is None and r["file_modified"] is None
    assert r["file_created"] == "2026-01-16T15:31:41"
    assert [s["heading"] for s in r["sections"]] == [
        None,
        "STEP #1 Determine Your Circumstance",
        "STEP #2 Gather Supporting Documents",
        "STEP #3 Contact the Financial Aid Office Professional Judgment / "
        "Special Circumstance Coordinator",
        "Contact",
    ]
    contact = r["sections"][-1]["markdown"].splitlines()
    assert contact == ["Professional Judgment/", "Special Circumstances Coordinator", "Ms. Pena",
                       "718-260-5714", "finaidspecialcircumstances@citytech.cuny.edu"]  # fmt: skip
    assert r["sections"][1]["markdown"].count("\n- ") == 5  # six bullets
    assert r["sections"][2]["markdown"].count("\n- ") == 7
    assert {(x["char"], x["count"]) for x in r["repairs"]} == {("ﬁ", 12), ("ﬂ", 1)}
    assert "text layer" in r["note"] and "not transcribed from an image" in r["note"]
    assert r["text_source"] == "text layer" and r["excluded"] == []


@pytest.mark.skipif(not HAVE_ALL, reason="data/pdfs is not committed")
def test_cunyfirst_guide_keeps_the_written_steps_and_drops_screenshot_callouts():
    from cta.parse.pdf_docs import parse_cunyfirst

    r = parse_cunyfirst(PDFS / "cunyfirst_student_reference.pdf")
    assert (r["doc_type"], r["scope"], r["term"], r["aid_year"]) == ("howto", "cuny", None, None)
    assert r["pdf_last_updated"] is None and r["file_modified"] == "2022-12-28T12:06:31-05:00"
    assert "Hunter and LaGuardia" in r["note"] and "2022-23" in r["note"]
    headings = [s["heading"] for s in r["sections"]]
    assert headings[0] == "STUDENT FINANCIAL AID GUIDE" and len(headings) == 10
    for key in ("TASKS & HOLDS", "SUPPLEMENT FORM", "AWARDS & DISBURSEMENTS",
                "DIRECT LOAN PROCESSING FORM",
                "BALANCE, PENDING FINANCIAL AID & REFUNDS", "FORM 1098-T", "W-2 FORM"):  # fmt: skip
        assert any(key in h for h in headings), key
    assert {e["reason"] for e in r["excluded"]} == {
        "screenshot annotation (7 pt callout text laid over a screenshot)"
    }
    assert len(r["excluded"]) == 22
    text = " ".join(s["markdown"] for s in r["sections"])
    assert (
        "Click here to choose your college" not in text
        and "**STEP# 1:** Login to CUNYfirst" in text
    )
    assert "origination fee" in text and "Never miss an aid refund" in text
    assert run_pdf_checks(r, PDFS / "cunyfirst_student_reference.pdf") == []


@pytest.mark.skipif(not HAVE_ALL, reason="data/pdfs is not committed")
def test_all_four_records_pass_every_check_and_are_indexed():
    from cta.parse.pdf_docs import build_all

    records = build_all(PDFS)
    assert sorted(records) == [
        "cunyfirst-student-reference", "dropping-withdrawing-fall-2026",
        "financial-aid-refund-calendar-2026-2027", "special-circumstances-flyer",
    ]  # fmt: skip
    names = {slug: name for slug, name, _ in DOCUMENTS}
    for slug, record in records.items():
        assert run_pdf_checks(record, PDFS / names[slug]) == []
        assert record["index"] is True and record["status"] == "collected"
        assert json.loads(json.dumps(record)) == record


def test_the_four_pdfs_are_in_the_known_data_list_of_sources_yaml():
    known = load_sources()["known_data"]
    by_file = {Path(k["file"]).name: k for k in known}
    assert set(by_file) == {name for _, name, _ in DOCUMENTS}
    for slug, name, _ in DOCUMENTS:
        assert by_file[name]["record"] == f"data/processed/pdfs/{slug}.json"
    assert by_file["cunyfirst_student_reference.pdf"]["scope"] == "cuny"
    assert Counter(k["doc_type"] for k in known) == {"aid": 2, "policy": 1, "howto": 1}
