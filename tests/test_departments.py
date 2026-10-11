import json
from pathlib import Path

import pytest

from cta.parse.departments import (
    boilerplate_sentences,
    build_all,
    codes_in_tree,
    compare_chair,
    compare_contact,
    credit_flags,
    credit_totals,
    dedupe_maps,
    file_date,
    fix_table,
    fix_tables,
    is_label,
    legacy_lines,
    load_root_contact,
    map_blocks,
    map_labels,
    parse_rule_notes,
    resolve_notes,
    semester_label,
    slugify,
    strip_boilerplate,
    strip_inactive,
    tracks_text,
)
from cta.parse.dept_pdf import Card, DegreeMap, Group, ProgramTree, Semester
from cta.parse.pdf_docs import PLine
from cta.validate.departments import (
    check_characters,
    check_completeness,
    check_map_labels,
    check_no_empty_sections,
    check_no_markers,
    check_no_rule_dumps,
    check_pdf_contact_not_indexed,
    check_required_parts,
    check_rule_ids_on_sections,
    check_table_format,
    check_term_not_invented,
    run_department_checks,
)

FIXTURES = Path(__file__).parent / "fixtures" / "pdfs"
RULES = json.loads((FIXTURES / "dent_rules.json").read_text(encoding="utf-8"))


def line(text, top=100.0, page=1):
    return PLine(text, text.replace("**", ""), page, top, top + 7, 30, 200, 7.2, False)


def card(*options, rule_notes="", notes="-"):
    return Card(list(options), rule_notes, notes, {}, 1)


def dmap(name, cards, total="60", year="2027 -", narrative="n"):
    return DegreeMap(name, total, year, narrative, [Semester("Year 1 Fall 3 3", list(cards))], 1)


def tree(groups=(), maps=(), general=()):
    return ProgramTree("T - AAS - Title", list(general), [], list(groups), list(maps), [], [])


def group(*blocks, title="G"):
    return Group(title, "Completion Requirement", list(blocks), 1)


# ---- names and dates ---------------------------------------------------------------------------


def test_file_date_from_the_file_name():
    assert file_date("CST-NYT-2026-09-10-19-16-13.pdf") == "2026-09-10T19:16:13"
    assert file_date("chair.pdf") is None


def test_slugify_uses_the_first_two_title_parts():
    assert slugify("Dental Hygiene - AAS - Associate in Applied Science") == "dental-hygiene-aas"
    assert slugify("Plain") == "plain"


# ---- chair comparison --------------------------------------------------------------------------

PDF_CHAIR = {
    "name": "Prof. Jane Roe",
    "office": "Namm N-720",
    "phone": "718-260-5000",
    "email": None,
}
WEB_CHAIR = {"name": "Jane Roe", "room": "N-720", "phone": "(718) 260-5000", "email": "j@x.edu"}


def test_chair_web_wins_and_every_field_is_a_row():
    chair, rows = compare_chair(PDF_CHAIR, WEB_CHAIR)
    assert chair["email"] == "j@x.edu" and chair["source"].startswith("chairperson.aspx")
    results = {r["field"]: r["result"] for r in rows}
    assert results == {
        "name": "match",
        "office": "match",
        "phone": "match",
        "email": "not printed in the PDF",
    }


def test_chair_mismatch_is_marked_and_the_web_value_is_used():
    chair, rows = compare_chair({**PDF_CHAIR, "phone": "718-260-9999"}, WEB_CHAIR)
    assert chair["phone"] == "(718) 260-5000"
    assert [r["result"] for r in rows if r["field"] == "phone"] == ["MISMATCH (web wins)"]


def test_chair_without_a_web_record_uses_the_pdf():
    chair, rows = compare_chair(PDF_CHAIR, None)
    assert chair["name"] == "Prof. Jane Roe" and rows == []


# ---- rule notes --------------------------------------------------------------------------------


def test_parse_rule_notes_splits_ids_and_keeps_text_without_an_id():
    assert parse_rule_notes("-") == []
    assert parse_rule_notes(
        "013081 - CUNY proficiency in English, 032849 - ENG 1101 Corequisite"
    ) == [
        {"id": "013081", "printed": "CUNY proficiency in English"},
        {"id": "032849", "printed": "ENG 1101 Corequisite"},
    ]
    assert parse_rule_notes("Just text")[0] == {"id": None, "printed": "Just text"}


def test_resolve_notes_status_match_differs_unresolved_and_flags():
    texts = {"111111": "Prerequisite: BIO 1100", "222222": "Something else", "333333": "PRE_ABC"}
    flags: list[str] = []
    out = resolve_notes(
        "111111 - Prerequisite: BIO 1100, 222222 - Printed words, 444444 - Gone, 333333 - PRE_ABC",
        texts.get,
        flags,
        "W",
    )
    assert [o["status"] for o in out] == ["match", "differs", "unresolved", "match"]
    assert out[3]["shorthand"] is True
    assert any("did not resolve" in f for f in flags) and any("shorthand" in f for f in flags)


def test_resolve_notes_flags_a_truncated_rule():
    flags: list[str] = []
    out = resolve_notes("555555 - Prerequisite: CST", lambda _: "Prerequisite: CST", flags, "W")
    assert out[0]["truncated"] is True and any("truncated" in f for f in flags)


def test_courses_titled_with_co_in_a_word_are_not_truncated():
    flags: list[str] = []
    out = resolve_notes("666666 - COURSES: see list", lambda _: "COURSES: see list", flags, "W")
    assert "truncated" not in out[0]


# ---- stripping ---------------------------------------------------------------------------------

SENT = "Students must complete all of the courses listed in this group before graduating."


def test_boilerplate_needs_two_departments_and_eight_words():
    a = tree([group(("p", 0, SENT + " Short one."))])
    b = tree([group(("p", 0, SENT))])
    only_one = boilerplate_sentences({"A": [a, b]})
    assert only_one == set()  # two programs, one department
    both = boilerplate_sentences({"A": [a], "B": [b]})
    assert both == {" ".join(SENT.lower().split())} or len(both) == 1


def test_strip_boilerplate_removes_the_sentence_and_records_it():
    generic = boilerplate_sentences(
        {"A": [tree([group(("p", 0, SENT))])], "B": [tree([group(("p", 0, SENT))])]}
    )
    stripped: list[dict] = []
    out = strip_boilerplate(
        [
            ("p", 0, SENT + " Keep this specific sentence about labs."),
            ("p", 0, SENT),
            ("p", 0, "**" + SENT + "**"),
        ],
        generic,
        "W",
        stripped,
    )
    assert out[0][2] == "Keep this specific sentence about labs."
    assert len(out) == 2 and out[1][2].startswith("**")  # a fully bold directive is kept
    assert [s["type"] for s in stripped] == ["rule_dump_text", "rule_dump_text"]


def test_strip_inactive_removes_the_bullet_and_its_wrapped_lines():
    items = [
        line("• ACTIVE 1000 - Active course"),
        line("• OLD 1000 - A course whose title", 110),
        line("wraps (Inactive)", 120),
        line("• NEXT 2000 - Next", 130),
    ]
    stripped: list[dict] = []
    out = strip_inactive(items, stripped, "W")
    assert [i.plain for i in out] == ["• ACTIVE 1000 - Active course", "• NEXT 2000 - Next"]
    assert stripped[0]["type"] == "inactive_course"
    assert stripped[0]["text"] == "• OLD 1000 - A course whose title wraps (Inactive)"


# ---- degree maps -------------------------------------------------------------------------------


def test_identical_maps_are_kept_once_and_tracks_are_listed():
    a = dmap("Track A", [card("CST 1000 - X")])
    b = dmap("Track B", [card("CST 1000 - X")])
    c = dmap("Track C", [card("CST 2000 - Y")])
    kept, repeats = dedupe_maps([a, b, c])
    assert [m.name for m in kept] == ["Track A", "Track C"]
    assert [m.name for m in repeats[0]] == ["Track B"]
    assert tracks_text(kept[0], repeats[0]) == (
        "This degree map is printed once per track with identical content. "
        "Applies to: Track A; Track B."
    )
    assert tracks_text(kept[1], repeats[1]) is None


def test_same_name_maps_with_different_content_are_both_kept():
    kept, _ = dedupe_maps([dmap("Same", [card("A 1")]), dmap("Same", [card("B 2")])])
    assert len(kept) == 2


# ---- program facts -----------------------------------------------------------------------------


def test_credit_totals_and_the_disagreement_flag():
    t = tree(
        [
            group(
                ("p", 0, "**Earn at least 120 credits**"),
                ("p", 0, "Complete 60 credits in the major"),
            )
        ],
        [dmap("Plan", [], total="100 - 110")],
    )
    totals = credit_totals(t)
    assert totals["degree_maps"] == [{"name": "Plan", "total_credits": "100 - 110"}]
    assert totals["overall_requirement_lines"] == [
        "Earn at least 120 credits",
        "Complete 60 credits in the major",
    ]
    assert len(credit_flags(t)) == 1 and "credit totals disagree" in credit_flags(t)[0]
    ok = tree([group(("p", 0, "Earn at least 60 credits"))], [dmap("Plan", [], total="60 - 62")])
    assert credit_flags(ok) == []


def test_codes_in_tree_come_from_list_bullets_and_map_cards():
    t = tree(
        [
            group(
                ("list", 0, "- CST 1100 - Intro\n- **OR** MAT 1275 - Algebra"),
                ("p", 0, "ENG 9999 - not a bullet"),
            )
        ],
        [dmap("Plan", [card("BIO 2311 - Anatomy", "BIO 2312 - More")])],
    )
    assert codes_in_tree(t) == {
        "CST 1100": {"requirements"},
        "MAT 1275": {"requirements"},
        "BIO 2311": {"degree map"},
        "BIO 2312": {"degree map"},
    }


def test_legacy_lines_list_every_line_that_mentions_mst_or_dpt():
    t = tree(
        [group(("list", 0, "- MST 1100 - Old\n- CST 1100 - New"))],
        [dmap("Plan", [card("DPT 2200 - Old too")])],
    )
    found = legacy_lines(t)
    assert [f["text"] for f in found] == ["- MST 1100 - Old", "DPT 2200 - Old too"]


# ---- the DENT fixture, end to end -------------------------------------------------------------


@pytest.fixture(scope="module")
def dent_build(tmp_path_factory):
    processed = tmp_path_factory.mktemp("processed")
    chair_dir = processed / "pages" / "DENT-NYT"
    chair_dir.mkdir(parents=True)
    (chair_dir / "chairperson.json").write_text(
        json.dumps(
            {
                "chair": {
                    "name": "Test Chair",
                    "room": "N-100",
                    "phone": "(718) 555-0100",
                    "email": "chair@example.edu",
                    "role": "Chair",
                }
            }
        ),
        encoding="utf-8",
    )
    contacts = processed / "contacts"
    contacts.mkdir()
    (contacts / "DENT-NYT.json").write_text(
        json.dumps(
            {
                "panels": [
                    {
                        "heading": "CONTACT US",
                        "markdown": "285 Jay Street\nAcademic Building 701 (A-701)\n"
                        "Brooklyn, NY 11201\n\nEmail: office@example.edu\n\nPhone: 718-260-5070",
                    }
                ],
                "source_pages": ["https://www.citytech.cuny.edu/dental/"],
            }
        ),
        encoding="utf-8",
    )
    from cta.parse import departments

    old = dict(departments.DEPARTMENTS)
    departments.DEPARTMENTS.clear()
    departments.DEPARTMENTS["DENT-NYT"] = "DENT-NYT-2026-09-10-19-16-25.pdf"
    try:
        records, parsed, generic = build_all(FIXTURES, processed, RULES.get)
    finally:
        departments.DEPARTMENTS.clear()
        departments.DEPARTMENTS.update(old)
    return records["DENT-NYT"], parsed["DENT-NYT"], generic


def test_dent_records_have_the_requested_shape(dent_build):
    records, _, _ = dent_build
    assert records[0]["doc_type"] == "department" and records[1]["doc_type"] == "program"
    for r in records:
        assert r["department"] == "DENT-NYT" and r["scope"] == "department"
        assert r["source_file"].endswith("DENT-NYT-2026-09-10-19-16-25.pdf")
        assert r["file_date"] == "2026-09-10T19:16:25"
        assert r["term"] is None and r["term_label_web"] == "2026 Fall Term"
        for s in r["sections"]:
            assert {"heading", "level", "parents", "markdown"} <= set(s)


def test_dent_broken_glyphs_are_repaired_and_recorded(dent_build):
    records, _, _ = dent_build
    text = json.dumps(records, ensure_ascii=False)
    assert "⯑" not in json.dumps(
        [{k: v for k, v in r.items() if k != "repairs"} for r in records], ensure_ascii=False
    )
    repairs = [x for r in records for x in r["repairs"] if x["kind"] == "broken_glyph"]
    assert {x["repaired"] for x in repairs} <= {"Offers", "Office"} and repairs
    assert "Offers" in text or "Office" in text


def test_dent_chair_uses_the_web_page(dent_build):
    overview = dent_build[0][0]
    assert (
        overview["chair"]["name"] == "Test Chair"
        and overview["chair"]["email"] == "chair@example.edu"
    )
    assert overview["chair_comparison"]


def test_dent_passes_all_checks_including_character_completeness(dent_build):
    records, parsed, generic = dent_build
    assert run_department_checks(records, parsed, generic) == []


# ---- the checks catch what they are for ---------------------------------------------------------


def mutate(records, fn):
    out = json.loads(json.dumps(records))
    fn(out)
    return out


def names(findings):
    return {f.check for f in findings}


def test_check_replacement_character_and_unrepaired_glyph(dent_build):
    records = dent_build[0]
    bad = mutate(records, lambda r: r[0]["sections"][0].update(markdown="x � y ⯑ z ﬁ"))
    assert names(check_characters(bad[0])) == {"replacement_chars", "broken_glyph", "ligatures"}


def test_check_advisory_inactive_total_and_stray_markers(dent_build):
    records = dent_build[0]
    for text, check in [
        ("The Advisory Commission met", "advisory_commission"),
        ("BIO 1 - Old (Inactive)", "inactive"),
        ("Total Major Credits 0", "total_lines"),
    ]:
        bad = mutate(records, lambda r, t=text: r[0]["sections"][0].update(markdown=t))
        assert check in names(check_no_markers(bad[0]))
    bad = mutate(records, lambda r: r[1].update(title="Accelerator Science and Technology - X"))
    assert "stray_program" in names(check_no_markers(bad[1]))


def test_check_rule_dump_text_left_in_a_record(dent_build):
    records = dent_build[0]
    generic = {"students must complete all of the courses"}
    bad = mutate(
        records,
        lambda r: r[1]["sections"][0].update(markdown="Students must complete all of the courses."),
    )
    assert names(check_no_rule_dumps(bad[1], generic)) == {"rule_dump"}
    assert check_no_rule_dumps(records[1], generic) == []


def test_check_required_parts_each_part_is_required(dent_build):
    records = dent_build[0]
    assert check_required_parts(records) == [] or names(check_required_parts(records)) <= {
        "credit_totals"
    }
    no_overview = [r for r in records if r["doc_type"] != "department"]
    assert "overview" in names(check_required_parts(no_overview))
    no_programs = [r for r in records if r["doc_type"] == "department"]
    assert {"programs", "requirements", "degree_map"} <= names(check_required_parts(no_programs))
    no_maps = mutate(records, lambda r: [p["program"].update(degree_maps=[]) for p in r[1:]])
    assert "degree_map" in names(check_required_parts(no_maps))
    dup = mutate(records, lambda r: r.append(json.loads(json.dumps(r[1]))))
    assert "program_slug" in names(check_required_parts(dup))


def test_check_term_must_not_be_invented(dent_build):
    records = dent_build[0]
    bad = mutate(records, lambda r: r[0].update(term="Fall 2026"))
    assert names(check_term_not_invented(bad)) == {"term"}
    assert check_term_not_invented(records) == []


def test_check_completeness_finds_a_dropped_and_an_invented_character(dent_build):
    records, parsed, _ = dent_build
    chars = parsed.stream.body_chars
    assert check_completeness(records, chars) == []
    assert names(check_completeness(records, [*chars, "Q"])) == {"chars_missing"}
    bad = mutate(
        records,
        lambda r: r[0]["sections"][0].update(markdown=r[0]["sections"][0]["markdown"] + " Q"),
    )
    assert names(check_completeness(bad, chars)) == {"chars_extra"}


def test_catalog_rewrite_keeps_the_programs_field(tmp_path):
    from cta.crawl.catalog import write_records

    rec = {"code": "CST 1100", "department": "CST", "course_group_id": "1", "programs": []}
    write_records([dict(rec)], tmp_path)
    path = next(tmp_path.rglob("*.json"))
    stored = json.loads(path.read_text(encoding="utf-8"))
    stored["programs"] = ["CST-NYT/some-program"]
    path.write_text(json.dumps(stored), encoding="utf-8")
    write_records([dict(rec)], tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))["programs"] == ["CST-NYT/some-program"]


# ---- step 6: headings, tables, rule IDs, contacts ------------------------------------------------


def test_semester_label_shows_one_number_when_equal_and_labels_both_when_they_differ():
    assert semester_label("Year 1 Fall 11 11") == "Year 1 Fall (11 credits)"
    assert semester_label("Year 2 Fall 15 - 18 15 - 18") == "Year 2 Fall (15 - 18 credits)"
    assert semester_label("Year 1 Spring 16 18") == (
        "Year 1 Spring (16 actual credits, 18 progress credits)"
    )
    assert semester_label("Year 4 Fall Semester 4 15 - 16 15 - 17") == (
        "Year 4 Fall Semester 4 (15 - 16 actual credits, 15 - 17 progress credits)"
    )
    assert semester_label("- Fall Semester 1 9 - 11 16 - 22") == (
        "- Fall Semester 1 (9 - 11 actual credits, 16 - 22 progress credits)"
    )
    assert semester_label("no numbers here") == "no numbers here"


def test_maps_with_the_same_name_are_labelled_by_pdf_page_and_others_are_not():
    a, b, c = dmap("Same", []), dmap("Same", []), dmap("Other", [])
    a.page, b.page, c.page = 40, 46, 50
    assert map_labels([a, b, c]) == ["Same (PDF page 40)", "Same (PDF page 46)", "Other"]


TABLE = (
    "| Requirement | Rule notes | Notes | Credits | Clinical |\n| --- | --- | --- | --- | --- |\n"
    "| A | text | - | 3 | No |\n| B | - | No | 4 | - |"
)


def test_fix_table_drops_only_columns_that_are_dash_or_no_in_every_row():
    md, done = fix_table(TABLE)
    assert done["dropped"] == ["Notes", "Clinical"]
    assert (
        md == "| Requirement | Rule notes | Credits |\n| --- | --- | --- |\n"
        "| A | text | 3 |\n| B | - | 4 |"
    )
    kept, none = fix_table(TABLE.replace("| - | 3 | No |", "| x | 3 | No |"))
    assert none["dropped"] == ["Clinical"] and "Notes" in kept.split("\n")[0]


def test_fix_table_never_drops_the_first_column_or_changes_a_table_with_nothing_to_fix():
    md = "| Item | Cost |\n| --- | --- |\n| - | $5 |\n| No | $6 |"
    assert fix_table(md) == (md, {"promoted": None, "dropped": []})


def test_fix_table_promotes_the_first_row_when_the_header_is_empty_and_the_row_is_a_header():
    md = "|  |  |\n| --- | --- |\n| ITEM | COST |\n| Book | $5 |"
    out, done = fix_table(md)
    assert out == "| ITEM | COST |\n| --- | --- |\n| Book | $5 |" and done["promoted"] == [
        "ITEM",
        "COST",
    ]
    not_header = "|  |  |\n| --- | --- |\n| Book | $5 |\n| Pen | $1 |"
    assert fix_table(not_header)[0] == not_header


def test_fix_tables_records_where_each_repair_happened():
    header_table = "|  |  |\n| --- | --- |\n| ITEM | COST |\n| a | b |"
    blocks = [
        ("h", 1, "P"),
        ("h", 2, "General"),
        ("table", 0, header_table),
        ("h", 2, "Maps"),
        ("h", 3, "Map"),
        ("table", 0, TABLE),
    ]
    out, repairs = fix_tables(blocks)
    assert [(r["kind"], r["where"]) for r in repairs] == [
        ("table_header_promoted", "P / General"),
        ("dropped_columns", "P / Maps / Map"),
    ]
    assert repairs[1]["columns"] == ["Notes", "Clinical"] and out[2][2].startswith(
        "| ITEM | COST |"
    )


def test_map_blocks_move_rule_ids_to_the_section_and_keep_only_the_text_in_the_cell():
    first = card("BIO 1 - X", rule_notes="013475 - old text, 013081 - other")
    m = dmap("Plan", [first, card("ENG 1 - Y")], total="10")
    m.semesters[0].printed = "Year 1 Fall 11 11"
    rules = {
        (0, 0, 0): [
            {"id": "013475", "printed": "old", "resolved": "Prerequisites: BIO 1"},
            {"id": "013081", "printed": "other", "resolved": None},
        ],
        (0, 0, 1): [],
    }
    blocks, ids = map_blocks([m], rules, {}, ["Plan"])
    assert ids == {("Degree map: Plan", "Year 1 Fall (11 credits)"): ["013475", "013081"]}
    table = next(b[2] for b in blocks if b[0] == "table")
    assert "| BIO 1 - X | Prerequisites: BIO 1; other |" in table and "013475" not in table
    assert "| ENG 1 - Y | - |" in table


ROOT_PANEL = {
    "panels": [
        {
            "heading": "CONTACT US",
            "markdown": "1 St\nNamm Hall 914 (N-914)\n\nEmail: a@x.edu\n\nPhone: 718-260-5170",
        }
    ],
    "source_pages": ["https://x/"],
}


def test_root_contact_is_read_from_the_contacts_file(tmp_path):
    (tmp_path / "contacts").mkdir()
    (tmp_path / "contacts" / "CST-NYT.json").write_text(json.dumps(ROOT_PANEL), encoding="utf-8")
    root = load_root_contact(tmp_path, "CST-NYT")
    assert (root["room"], root["phone"], root["email"]) == ("N-914", "718-260-5170", "a@x.edu")
    assert load_root_contact(tmp_path, "NOPE") is None


def test_pdf_contact_block_is_compared_with_the_root_page_block():
    root = {
        "room": "N-914",
        "phone": "718-260-5170",
        "email": "a@x.edu",
        "source_page": "https://x/",
    }
    pdf = {"office": "Namm Building, room N-914", "phone": "718-260-5170", "email": None}
    same = compare_contact(pdf, root)
    assert same["matches"] and [r["result"] for r in same["rows"]] == [
        "match",
        "match",
        "not printed in the PDF",
    ]
    other = compare_contact({**pdf, "phone": "718-000-0000"}, root)
    assert not other["matches"] and other["rows"][1]["result"] == "MISMATCH"
    assert compare_contact(pdf, None) is None


def test_dent_headings_tables_rule_ids_and_contact(dent_build):
    records, _, _ = dent_build
    overview, program = records
    headings = [s["heading"] for s in program["sections"]]
    assert "Year 1 Fall (11 credits)" in headings and "Year 1 Spring (10 - 11 credits)" in headings
    fall = next(s for s in program["sections"] if s["heading"] == "Year 1 Fall (11 credits)")
    assert fall["rule_ids"] == ["013475", "034625", "013081"] and fall["generated"] is True
    assert "013475" not in fall["markdown"] and "Rule notes" in fall["markdown"]
    assert "Criticality" not in fall["markdown"] and "Actual Credits" in fall["markdown"]
    repairs = {
        (r["kind"], r["where"].split(" / ")[-1])
        for r in program["repairs"]
        if r["kind"] != "ligature"
    }
    assert ("table_header_promoted", "Additional Costs") in repairs
    dropped = next(r for r in program["repairs"] if r["kind"] == "dropped_columns")
    assert "Criticality" in dropped["columns"] and "Rule notes" not in dropped["columns"]
    costs = next(s for s in program["sections"] if s["heading"] == "Additional Costs")
    assert "| ITEM | COST |" in costs["markdown"] and "|  |  |" not in costs["markdown"]
    chair = next(s for s in overview["sections"] if s["heading"] == "Chair")
    assert chair["embed"] is False and overview["chair_pdf"]["embed"] is False
    assert overview["contact_pdf_vs_root"]["matches"] is True
    assert any("source mismatch, not a data error" in f for f in overview["flags"])


def test_checks_catch_table_and_rule_id_and_label_and_contact_problems(dent_build):
    records = dent_build[0]
    program = records[1]

    def sem(r):
        return next(s for s in r[1]["sections"] if s["heading"] == "Year 1 Fall (11 credits)")

    bad = mutate(
        records,
        lambda r: sem(r).update(markdown=sem(r)["markdown"] + "\n| X | 013475 y | 1 | 2 | 3 |"),
    )
    assert "rule_id_in_cell" in names(check_table_format(bad[1]))
    bad = mutate(records, lambda r: sem(r).update(markdown=TABLE))
    assert {"table_constant_column"} <= names(check_table_format(bad[1]))
    bad = mutate(records, lambda r: sem(r).update(markdown="|  |  |\n| --- | --- |\n| a | b |"))
    assert "table_header" in names(check_table_format(bad[1]))
    bad = mutate(records, lambda r: sem(r).update(heading="Year 1 Fall 11 11"))
    assert "semester_heading" in names(check_table_format(bad[1]))
    assert check_table_format(program) == []
    bad = mutate(records, lambda r: sem(r).update(rule_ids=[]))
    assert "rule_ids" in names(check_rule_ids_on_sections(bad[1]))
    assert check_rule_ids_on_sections(program) == []
    bad = mutate(
        records,
        lambda r: r[1]["program"]["degree_maps"].append(dict(r[1]["program"]["degree_maps"][0])),
    )
    assert "map_label" in names(check_map_labels(bad[1]))
    overview = records[0]
    assert check_pdf_contact_not_indexed(overview) == []
    chair = lambda r: next(s for s in r[0]["sections"] if s["heading"] == "Chair")  # noqa: E731
    bad = mutate(records, lambda r: chair(r).pop("embed"))
    assert "pdf_contact_indexed" in names(check_pdf_contact_not_indexed(bad[0]))
    bad = mutate(records, lambda r: r[0]["chair_pdf"].update(embed=True))
    assert "pdf_contact_indexed" in names(check_pdf_contact_not_indexed(bad[0]))


# ---- step 7: labels left empty by a stripped rule dump ---------------------------------------


def test_is_label_needs_a_short_title_case_plain_paragraph_without_final_punctuation():
    assert is_label(("p", 0, "Writing Intensive"))
    assert is_label(("p", 0, "Life and Physical Sciences"))
    assert not is_label(("p", 0, "**Fulfill ALL of the following requirements:**"))
    assert not is_label(("p", 0, "or higher Chemistry course"))
    assert not is_label(("p", 0, "No selection provided"))
    assert not is_label(("p", 0, "Complete the following courses."))
    assert not is_label(("list", 0, "- Writing Intensive"))
    assert not is_label(("p", 0, "One Two Three Four Five Six Seven"))


def generic_set():
    return boilerplate_sentences(
        {"A": [tree([group(("p", 0, SENT))])], "B": [tree([group(("p", 0, SENT))])]}
    )


def test_a_label_whose_text_was_all_stripped_is_removed_and_recorded():
    stripped: list[dict] = []
    blocks = [("p", 0, "Intro text for the group."), ("p", 0, "Writing Intensive"), ("p", 0, SENT)]
    out = strip_boilerplate(blocks, generic_set(), "W", stripped)
    assert out == [("p", 0, "Intro text for the group.")]
    assert [(s["type"], s["text"]) for s in stripped] == [
        ("rule_dump_text", SENT),
        ("empty_label", "Writing Intensive"),
    ]
    assert "generic rule text" in stripped[1]["reason"]


def test_a_label_is_kept_when_a_directive_or_other_content_follows_the_stripped_text():
    directive = ("p", 0, "**Fulfill ALL of the following requirements:**")
    for after in (
        directive,
        ("list", 0, "- ENG 1101 - English Composition I"),
        ("p", 0, "Keep me."),
    ):
        stripped: list[dict] = []
        blocks = [("p", 0, "Required Common Core"), ("p", 0, SENT), after]
        out = strip_boilerplate(blocks, generic_set(), "W", stripped)
        assert out[0] == ("p", 0, "Required Common Core") and out[-1] == after
        assert [s["type"] for s in stripped] == ["rule_dump_text"]


def test_a_label_directly_followed_by_a_kept_block_is_never_touched():
    stripped: list[dict] = []
    blocks = [("p", 0, "Flexible Common Core"), directive_block := ("p", 0, "**Complete ALL:**")]
    assert strip_boilerplate(blocks, generic_set(), "W", stripped) == blocks and stripped == []
    assert directive_block


def test_two_labels_in_a_row_after_a_dump_remove_only_the_empty_one():
    stripped: list[dict] = []
    blocks = [
        ("p", 0, "College Option"),
        ("p", 0, SENT),
        ("p", 0, "Writing Intensive"),
        ("p", 0, SENT),
    ]
    out = strip_boilerplate(blocks, generic_set(), "W", stripped)
    assert out == []
    assert [s["text"] for s in stripped if s["type"] == "empty_label"] == [
        "College Option",
        "Writing Intensive",
    ]


WI_SENTENCES = (
    "Students at New York City College of Technology must complete two courses designated writing "
    "intensive (WI) for the associate level, one from general education requirements and one from "
    "the major.",
    "Transfer students and those who have earned a prior degree may have part or all of this "
    "requirement waived; please consult the Degree Requirements page for additional information.",
)


def test_dent_general_education_no_longer_ends_in_the_writing_intensive_label(dent_build):
    from cta.parse.departments import build_program, norm

    _, parsed, _ = dent_build  # one department only, so give the generic text the other PDFs share
    generic = {norm(x) for x in WI_SENTENCES}
    program = build_program(parsed, parsed.trees[0], generic, RULES.get)
    general = next(x for x in program["sections"] if x["heading"] == "General Education")
    assert "Writing Intensive" not in general["markdown"]
    assert general["markdown"].endswith("noted in the degree map below.")
    labels = [x for x in program["stripped"] if x["type"] == "empty_label"]
    assert [x["text"] for x in labels] == ["Writing Intensive"]
    assert check_no_empty_sections(program) == []


def test_check_empty_sections_flags_a_blank_section_and_a_trailing_bare_label(dent_build):
    records = dent_build[0]
    assert check_no_empty_sections(records[1]) == []
    blank = mutate(records, lambda r: r[1]["sections"][0].update(markdown="  "))
    assert names(check_no_empty_sections(blank[1])) == {"empty_section"}
    label = mutate(
        records, lambda r: r[1]["sections"][0].update(markdown="Some text.\n\nWriting Intensive")
    )
    assert names(check_no_empty_sections(label[1])) == {"empty_label"}


def test_check_empty_sections_leaves_lists_fragments_and_printed_statements_alone():
    def record(markdown):
        section = {"heading": "H", "level": 2, "parents": [], "markdown": markdown}
        return {"department": "D", "doc_type": "program", "title": "T", "sections": [section]}

    for markdown in (
        "Complete ALL:\n\n- Electrical Engineering Technical Elective",
        "- CHEM 1000 - Principles\n\nor higher Chemistry course",
        "Choose one.\n\nNo selection provided",
        "A single short section",
    ):
        assert check_no_empty_sections(record(markdown)) == []


# ---- step 8: the Simple Requirements wrapper ---------------------------------------------------


def wrapper_sections(markdown="**(No Requirement Levels)**"):
    top = {"level": 1, "heading": "Program"}
    req = {"level": 2, "heading": "Requirements"}
    simple = {"level": 3, "heading": "Simple Requirements"}
    return [
        {"heading": "Requirements", "level": 2, "parents": [top], "markdown": "Intro"},
        {"heading": "Simple Requirements", "level": 3, "parents": [top, req], "markdown": markdown},
        {"heading": "Admission", "level": 4, "parents": [top, req, simple], "markdown": "Text"},
    ]


def test_the_wrapper_is_dropped_when_its_only_content_is_no_requirement_levels():
    from cta.parse.departments import drop_wrapper_sections

    out, dropped = drop_wrapper_sections(wrapper_sections(), "P")
    assert [s["heading"] for s in out] == ["Requirements", "Admission"]
    assert [p["heading"] for p in out[1]["parents"]] == [
        "Program",
        "Requirements",
        "Simple Requirements",
    ]
    assert dropped == [
        {"type": "wrapper_section", "text": "(No Requirement Levels)",
         "heading": "Simple Requirements", "where": "P"}
    ]  # fmt: skip


def test_the_wrapper_is_kept_when_it_has_other_content():
    from cta.parse.departments import drop_wrapper_sections

    sections = wrapper_sections("**(No Requirement Levels)**\n\nExtra sentence.")
    out, dropped = drop_wrapper_sections(sections, "P")
    assert out == sections and dropped == []


def test_a_wrapper_without_children_keeps_its_heading_text_in_the_stripped_entry():
    from cta.parse.departments import drop_wrapper_sections

    out, dropped = drop_wrapper_sections(wrapper_sections()[:2], "P")
    assert [s["heading"] for s in out] == ["Requirements"]
    assert dropped[0]["text"] == "Simple Requirements (No Requirement Levels)"


def test_dent_program_has_no_simple_requirements_section_but_children_keep_the_path(dent_build):
    program = dent_build[0][1]
    assert not any(s["heading"] == "Simple Requirements" for s in program["sections"])
    admission = next(s for s in program["sections"] if s["heading"] == "Admission Requirements")
    assert [p["heading"] for p in admission["parents"]][-2:] == [
        "Requirements",
        "Simple Requirements",
    ]
    assert [s["type"] for s in program["stripped"]].count("wrapper_section") == 1
    assert run_department_checks(*dent_build) == []
