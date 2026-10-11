import json
from pathlib import Path

import pytest

from cta.parse.departments import (
    boilerplate_sentences,
    build_all,
    codes_in_tree,
    compare_chair,
    credit_flags,
    credit_totals,
    dedupe_maps,
    file_date,
    legacy_lines,
    parse_rule_notes,
    resolve_notes,
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
    check_no_markers,
    check_no_rule_dumps,
    check_required_parts,
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
