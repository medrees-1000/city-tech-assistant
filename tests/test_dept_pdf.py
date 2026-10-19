from pathlib import Path

import pytest

from cta.parse.dept_pdf import (
    PTable,
    flow,
    key_of,
    kind,
    parse_card,
    parse_maps,
    program_title,
    read_stream,
    repair_broken,
    requirement_groups,
    split_parts,
)
from cta.parse.pdf_docs import PLine, Repairs

DENT = Path(__file__).parent / "fixtures" / "pdfs" / "DENT-NYT-2026-09-10-19-16-25.pdf"


def L(
    text, top, page=1, size=7.2, bold=False, x0=30.0, x1=200.0, col="L", first=20.0, margin=300.0
):
    plain = text.replace("**", "")
    marked = f"**{plain}**" if bold else text
    return PLine(
        marked, plain, page, top, x0, x1, size, bold, 842.0, first, margin, col
    )


def blocks(*lines):
    return flow(list(lines), Repairs())


def test_kind_by_size_and_bold():
    assert kind(L("Dept", 0, size=14.4, bold=True)) == "dept"
    assert kind(L("Chair", 0, size=12.2, bold=True)) == "h12"
    assert kind(L("Prog - BS - Bachelor", 0, size=10.1, bold=True)) == "title"
    assert kind(L("General", 0, size=9.4, bold=True)) == "h9"
    assert kind(L("Learning Outcomes", 0, size=8.3)) == "h8"
    assert kind(L("text", 0)) == "body"
    assert kind(PTable(1, "L", 0, [["a", "b"]], False)) == "table"


def test_split_parts_overview_programs_and_courses():
    items = [
        L("Dental Hygiene Department", 60, size=14.4, bold=True),
        L("Description", 80, size=12.2, bold=True),
        L("About us.", 100),
        L("Programs", 120, page=2, size=12.2, bold=True),
        L("Dental - AAS - Associate", 60, page=3, size=10.1, bold=True),
        L("in Applied Science", 72, page=3, size=10.1, bold=True),
        L("General", 90, page=3, size=9.4, bold=True),
        L("Second - BS - Bachelor of Science", 60, page=4, size=10.1, bold=True),
        L("Courses", 60, page=5, size=12.2, bold=True),
        L("DEN 1100 - Principles (4 cr)", 80, page=5, size=10.1, bold=True),
    ]
    parts = split_parts(items)
    assert parts.dept_title == "Dental Hygiene Department"
    assert [i.plain for i in parts.overview] == [
        "Dental Hygiene Department",
        "Description",
        "About us.",
    ]
    assert [program_title(t) for t, _ in parts.programs] == [
        "Dental - AAS - Associate in Applied Science",
        "Second - BS - Bachelor of Science",
    ]
    assert [i.plain for i in parts.courses] == ["DEN 1100 - Principles (4 cr)"]


def test_split_parts_needs_programs_and_courses_headings():
    with pytest.raises(ValueError):
        split_parts([L("Dept", 0, size=14.4, bold=True)])


def test_wrapped_line_continues_and_early_end_starts_a_new_paragraph():
    wrapped = blocks(
        L("This line runs right up to the margin of the column and", 100, x1=299.0),
        L("continues here.", 110.8, x1=90.0, first=40.0),
    )
    assert wrapped == [
        ("p", 0, "This line runs right up to the margin of the column and continues here.")
    ]
    hard = blocks(L("A short paragraph.", 100, x1=120.0), L("Next paragraph", 110.8, first=20.0))
    assert [b[2] for b in hard] == ["A short paragraph.", "Next paragraph"]


def test_bullets_nest_by_indentation():
    out = blocks(
        L("• first item", 100, x0=59.5),
        L("• second item", 112, x0=59.5),
        L("◦ nested item", 124, x0=112.0),
        L("• third item", 136, x0=59.5),
    )
    assert out == [("list", 0, "- first item\n- second item\n  - nested item\n- third item")]


def test_indentation_is_measured_from_the_column_edge():
    left = L("• Left item", 700, x0=59.5, col="L")
    right = L("• Right item", 56, page=2, x0=336.1, col="R")
    assert blocks(left, right) == [("list", 0, "- Left item\n- Right item")]


def test_wrapped_list_item_joins_the_item():
    out = blocks(
        L("• An item that wraps", 100, x0=59.5, x1=290.0),
        L("onto a second line.", 110.8, x0=70.0),
    )
    assert out == [("list", 0, "- An item that wraps onto a second line.")]


def test_paragraph_continues_into_the_next_column_when_it_starts_lowercase():
    out = blocks(
        L("The sentence is cut by the column and", 700, x1=299.0),
        L("continues in the next column.", 56, page=2, x0=306.6, col="R"),
    )
    assert out == [("p", 0, "The sentence is cut by the column and continues in the next column.")]


def test_table_is_a_block_of_its_own():
    table = PTable(1, "L", 90, [["ITEM", "COST"], ["Book", "$5"], ["Pen", "$1"]], False)
    out = flow([L("Intro text.", 80, x1=100.0), table, L("After.", 200, x1=100.0)], Repairs())
    assert [b[0] for b in out] == ["p", "table", "p"]
    assert "Book" in out[1][2] and "$5" in out[1][2]


def test_requirement_groups_start_at_a_bold_line_followed_by_type():
    items = [
        L("Simple Requirements", 60, size=8.3),
        L("Admission Requirements", 90, bold=True),
        L("Type", 100, bold=True),
        L("Prerequisite", 110),
        L("Transfer students need a 2.5.", 125),
        L("General Education", 160, bold=True),
        L("Type", 170, bold=True),
        L("Completion Requirement", 180),
        L("Complete ALL of the following Courses:", 195, bold=True),
        L("• ENG 1101 - English Composition I", 210, x0=72.1),
    ]
    notes, groups = requirement_groups(items, Repairs())
    assert notes == [("h", 3, "Simple Requirements")]
    assert [(g.title, g.type_label) for g in groups] == [
        ("Admission Requirements", "Prerequisite"),
        ("General Education", "Completion Requirement"),
    ]
    assert groups[0].blocks == [("p", 0, "Transfer students need a 2.5.")]
    assert groups[1].blocks[-1] == ("list", 0, "- ENG 1101 - English Composition I")


def card_lines(*specs):
    return [L(t, 100 + 10.8 * i, bold=t.startswith("**")) for i, t in enumerate(specs)]


def test_key_of_needs_a_bold_key_at_the_start():
    assert key_of(L("Notes", 0, bold=True)) == "Notes"
    assert key_of(L("Notes in plain text", 0)) is None


def bold_key(text, top):
    """A key line: bold key, plain value (as in the PDFs)."""
    key, _, value = text.partition("|")
    ln = L(key + (" " + value if value else ""), top)
    ln.text = f"**{key}**" + (f" {value}" if value else "")
    return ln


def test_parse_card_options_two_notes_and_fields():
    lines = [
        L("• ENG 1101 - English Composition I", 100),
        L("OR", 111),
        L("• ENG 1101CO - English Composition I (with", 122),
        L("corequisite support)", 133),
        bold_key("Notes|013081 - CUNY proficiency in", 144),
        L("English, 032849 - ENG 1101 Corequisite", 155),
        bold_key("Notes|fulfills English Composition", 166),
        bold_key("Minimum Grade|-", 177),
        bold_key("Actual Credits|3", 188),
        bold_key("Progress Credits|3 - 5", 199),
        bold_key("Criticality|No", 210),
    ]
    flags: list[str] = []
    card = parse_card(lines, flags, "test")
    assert card.options == [
        "ENG 1101 - English Composition I",
        "ENG 1101CO - English Composition I (with corequisite support)",
    ]
    assert card.rule_notes == "013081 - CUNY proficiency in English, 032849 - ENG 1101 Corequisite"
    assert card.notes == "fulfills English Composition"
    assert card.fields["Progress Credits"] == "3 - 5" and card.fields["Criticality"] == "No"
    assert flags == []


def test_card_with_the_wrong_number_of_notes_is_flagged():
    flags: list[str] = []
    parse_card([L("• CST 1100 - Intro", 100), bold_key("Notes|x", 111)], flags, "bad")
    assert flags == ["bad: 1 Notes entries (expected 2)"]


def test_parse_maps_header_semesters_cards_and_zero_totals():
    items = [
        L("Degree Map Name", 0, bold=True),
        L("Dental Hygiene", 10),
        L("Total Degree Map Credits", 20, bold=True),
        L("66 - 67", 30),
        L("Degree Map Effective Catalog Year", 40, bold=True),
        L("2027 -", 50),
        L("Degree Map Narrative", 60, size=8.3, bold=True),
        L("A recommended plan.", 70),
        L("Year Semester Actual Credits Progress Credits", 80, bold=True),
        L("Year 1 Fall 11 11", 90),
        L("Requirement Select", 100, bold=True),
        L("• BIO 2311 - Anatomy", 110),
        bold_key("Notes|013475 - Prerequisites: BIO", 120),
        bold_key("Notes|-", 130),
        bold_key("Actual Credits|4", 140),
        L("Total General Education Credits Total Major Credits", 160, bold=True),
        L("0 0", 170),
        L("Total Minor Credits Total Elective Credits", 180, bold=True),
        L("0 0", 190),
    ]
    stripped: list[dict] = []
    flags: list[str] = []
    maps = parse_maps(items, stripped, flags, Repairs(), "P")
    assert len(maps) == 1 and flags == []
    m = maps[0]
    assert (m.name, m.total_credits, m.effective_year, m.narrative) == (
        "Dental Hygiene",
        "66 - 67",
        "2027 -",
        "A recommended plan.",
    )
    assert [s.printed for s in m.semesters] == ["Year 1 Fall 11 11"]
    card = m.semesters[0].cards[0]
    assert (
        card.options == ["BIO 2311 - Anatomy"] and card.rule_notes == "013475 - Prerequisites: BIO"
    )
    assert [(s["type"], s["zero"]) for s in stripped] == [("total_credits", True)] * 2


def test_repair_broken_counts_every_occurrence_and_only_known_words():
    repairs: list[dict] = []
    out = repair_broken("O⯑ers and O⯑ers; the O⯑ce; X⯑y", repairs, "here")
    assert out == "Offers and Offers; the Office; X⯑y"
    assert [(r["printed"], r["repaired"], r["count"]) for r in repairs] == [
        ("O⯑ers", "Offers", 2),
        ("O⯑ce", "Office", 1),
    ]


@pytest.fixture(scope="module")
def dent():
    return read_stream(DENT)


def test_dent_stream_footers_and_tables(dent):
    assert [f["text"] for f in dent.footers] == [f"{n} / 16" for n in range(1, 17)]
    tables = [i for i in dent.items if isinstance(i, PTable)]
    assert tables and all(len(t.rows) >= 3 for t in tables)


def test_dent_page_one_is_full_width_and_columns_are_read_left_then_right(dent):
    lines = [i for i in dent.items if isinstance(i, PLine)]
    assert {ln.col for ln in lines if ln.page == 1} == {"F"}
    page4 = [ln.col for ln in lines if ln.page == 4]
    assert page4 == ["L"] * page4.count("L") + ["R"] * page4.count("R")


def test_dent_has_the_broken_glyph_and_no_ligature_characters(dent):
    text = " ".join(i.plain for i in dent.items if isinstance(i, PLine))
    assert "⯑" in text
    assert "ﬁ" not in text and "ﬂ" not in text
