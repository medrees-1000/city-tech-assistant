import json
from pathlib import Path

import pytest

from cta.eval.questions import (
    CALENDAR,
    GoldData,
    analyze_prerequisite,
    answer_problems,
    check_all,
    course_codes_in,
    duplicate_ids,
    eval_findings,
    gold_problem,
    load_gold_data,
    load_questions,
    prerequisite_tree,
    question_problems,
    render_tree,
    row_problems,
    tree_courses,
    tree_without_records,
)
from cta.eval.review import render

SECTION = {
    "id": "page/registrar/faqs#3", "source": "https://x/faqs.aspx", "heading_path": "FAQs > Grades",
    "heading": "Grades", "doc_type": "faq",
}  # fmt: skip


def course(code, prereq, dept="DENT-NYT"):
    return {"code": code, "title": f"T {code}", "credits": 3, "department": dept,
            "description": f"About {code}.", "prerequisite_text": prereq}  # fmt: skip


def event(**over):
    base = {
        "id": "fall-2026-044", "term": "Fall 2026", "event": "SAP deadline",
        "date_start": "2026-11-13", "date_end": None, "weekday_raw": "Friday",
        "applies_to": None, "verified": True, "pdf_last_updated": "2026-09-15", "notes": None,
    }  # fmt: skip
    return {**base, **over}


def data():
    d = GoldData()
    d.sections = {SECTION["id"]: SECTION}
    d.courses = {
        "DEN 2400": [
            course("DEN 2400", "Prerequisites: DEN 2300 & DEN 2315. Corequisites: DEN 2413.")
        ],
        "DEN 2300": [course("DEN 2300", "Prerequisites: DEN 1200 (C or higher).")],
        "DEN 2315": [course("DEN 2315", None)],
    }
    d.events = {"fall-2026-044": event(), "x-1": event(id="x-1", verified=False)}
    return d


def good(**over):
    return {
        "id": "q01", "question": "When?", "gold_answer": "TODO", "type": "lookup", "split": "dev",
        "department": None, "note": "", "gold_sources": [
            {"id": SECTION["id"], "source": SECTION["source"], "heading": "FAQs > Grades"}],
        **over,
    }  # fmt: skip


def test_a_good_row_has_no_problems():
    assert row_problems(good()) == [] and question_problems(good(), data()) == []


def test_every_required_field_is_needed():
    for f in (
        "id",
        "question",
        "gold_answer",
        "gold_sources",
        "type",
        "department",
        "split",
        "note",
    ):
        row = good()
        del row[f]
        assert f"missing field {f}" in row_problems(row)


def test_tags_are_optional_and_unknown_fields_are_rejected():
    assert row_problems(good(tags=["chain"])) == [] and row_problems(good(tags=[])) == []
    assert any("tags" in p for p in row_problems(good(tags="chain")))
    assert any("tags" in p for p in row_problems(good(tags=["chain", ""])))
    assert any("tags" in p for p in row_problems(good(tags=[1])))
    assert "unknown field difficulty" in row_problems(good(difficulty="hard"))


def test_type_split_and_department_are_checked():
    assert any("type" in p for p in row_problems(good(type="essay")))
    for t in ("lookup", "multi_chunk", "time_sensitive", "ambiguous", "unanswerable"):
        assert row_problems(good(type=t)) == []
    assert any("split" in p for p in row_problems(good(split="train")))
    assert any("department" in p for p in row_problems(good(department="BIO-NYT")))
    for dept in ("CST-NYT", "MATH-NYT", "EET-NYT", "DENT-NYT", None):
        assert row_problems(good(department=dept)) == []


def test_empty_text_and_malformed_gold_sources_are_problems():
    assert "question is empty" in row_problems(good(question=" "))
    assert "gold_sources is not a list" in row_problems(good(gold_sources="x"))
    assert any("lacks" in p for p in row_problems(good(gold_sources=[{"id": "a"}])))


def test_duplicate_ids_are_found_across_rows():
    rows = [good(id=q, gold_answer="A") for q in ("q01", "q02", "q01")]
    assert duplicate_ids(rows) == {"q01"}
    results = check_all(rows, data())
    assert "id is not unique" in results["q01"] and results["q02"] == []


def test_section_gold_source_must_exist_with_the_same_source_and_heading():
    d = data()
    ok = {"id": SECTION["id"], "source": SECTION["source"], "heading": "FAQs > Grades"}
    assert gold_problem(ok, d) is None
    assert "not a section in the index" in gold_problem({**ok, "id": "page/registrar/faqs#9"}, d)
    assert "source is" in gold_problem({**ok, "source": "https://other"}, d)
    assert "heading path is" in gold_problem({**ok, "heading": "FAQs > Other"}, d)


def test_a_heading_with_link_markup_does_not_match_its_visible_text():
    d = data()
    stored = "Degrees > [CIS/AAS](https://c/p)"
    d.sections["page/a/b#1"] = {**SECTION, "id": "page/a/b#1", "heading_path": stored}
    src = {"id": "page/a/b#1", "source": SECTION["source"], "heading": "Degrees > CIS/AAS"}
    assert "heading path is" in gold_problem(src, d)  # the index is expected to be clean


def test_catalog_gold_source_must_match_a_course_code():
    d = data()
    ok = {"id": "catalog:DEN 2400", "source": "catalog_course", "heading": "DEN 2400"}
    assert gold_problem(ok, d) is None
    assert "no course record" in gold_problem({**ok, "id": "catalog:DEN 9999"}, d)
    assert "catalog_course" in gold_problem({**ok, "source": "x"}, d)


def test_calendar_gold_source_must_be_a_verified_event_of_the_headings_term():
    d = data()
    ok = {"id": "fall-2026-044", "source": CALENDAR, "heading": "Fall 2026: SAP appeal deadline"}
    assert gold_problem(ok, d) is None
    assert gold_problem({**ok, "id": "TODO"}, d) == "unresolved (TODO)"
    assert "no calendar event" in gold_problem({**ok, "id": "fall-2026-999"}, d)
    assert "not verified" in gold_problem({**ok, "id": "x-1"}, d)
    assert "the heading says" in gold_problem({**ok, "heading": "Spring 2027: x"}, d)
    assert "not a section id" in gold_problem({"id": "zzz", "source": "x", "heading": "y"}, d)


def test_a_missing_gold_source_is_a_problem_for_answerable_types_only():
    missing = good(gold_sources=[{"id": "page/registrar/faqs#9", "source": "s", "heading": "h"}])
    assert any("not a section" in p for p in question_problems(missing, data()))
    assert "no gold sources for a lookup question" in question_problems(
        good(gold_sources=[]), data()
    )
    for t in ("ambiguous", "unanswerable"):
        assert question_problems(good(type=t, gold_sources=[]), data()) == []


def test_a_deliberately_broken_row_reports_each_problem():
    row = good(
        type="essay",
        split="train",
        department="BIO",
        gold_sources=[{"id": "TODO", "source": "s", "heading": "h"}],
    )
    del row["note"]
    problems = question_problems(row, data())
    assert len(problems) == 5
    assert "unresolved (TODO)" in problems and "missing field note" in problems


def test_course_codes_in_text_include_codes_written_without_a_space():
    assert course_codes_in("Prerequisites: DEN 2300, DEN 2311 & DEN 2315. PRE: MAT1475") == [
        "DEN 2300", "DEN 2311", "DEN 2315", "MAT 1475",
    ]  # fmt: skip
    assert course_codes_in(None) == [] and course_codes_in("CUNY proficiency in English") == []


def kinds(text):
    return [(i["kind"], i.get("code") or i.get("text")) for i in analyze_prerequisite(text)]


def test_prerequisite_text_is_split_into_prerequisites_corequisites_and_stops():
    full = "Prerequisites: DEN 2300, DEN 2311, DEN 2315 & DEN 2318. Corequisites: DEN 2413."
    assert kinds(full) == [
        ("prerequisite", "DEN 2300"), ("prerequisite", "DEN 2311"), ("prerequisite", "DEN 2315"),
        ("prerequisite", "DEN 2318"), ("corequisite", "DEN 2413"),
    ]  # fmt: skip
    mixed = (
        "Prerequisite: DEN 2300 all with a grade of C; Corequisite: DEN 2400; "
        "Pre- or corequisite: BIO 3524."
    )
    assert kinds(mixed) == [
        ("prerequisite", "DEN 2300"), ("corequisite", "DEN 2400"),
        ("pre- or corequisite", "BIO 3524"),
    ]  # fmt: skip
    assert kinds("Pre/corequisite: MAT 1190 or MAT 1190CO or higher") == [
        ("pre- or corequisite", "MAT 1190"), ("pre- or corequisite", "MAT 1190CO"),
    ]  # fmt: skip
    assert kinds("PRE: MAT1475") == [("prerequisite", "MAT 1475")]
    assert kinds("Prerequisites of MAT 1575 AND MAT 2580") == [
        ("prerequisite", "MAT 1575"), ("prerequisite", "MAT 2580"),
    ]  # fmt: skip
    assert kinds(None) == [] and kinds("") == []


def test_exclusion_equivalence_and_placement_text_are_not_prerequisites():
    assert kinds("PREREQUISITE OF MAT 1475, MUST NOT HAVE PASSED MAT 2675") == [
        ("prerequisite", "MAT 1475"), ("exclusion", "MAT 2675"),
    ]  # fmt: skip
    assert kinds("PRE: MAT 1375 OR Meet the Math Placement for MAT 1475") == [
        ("prerequisite", "MAT 1375"), ("placement", "Meet the Math Placement for MAT 1475"),
    ]  # fmt: skip
    proficiency = "CUNY proficiency in reading, writing and mathematics; Corequisite of DEN 1100."
    assert kinds(proficiency) == [
        ("placement", "CUNY proficiency in reading, writing and mathematics"),
        ("corequisite", "DEN 1100"),
    ]  # fmt: skip
    assert kinds("MAT 1275CO is equivalent to MAT 1275 for grade replacement purposes") == [
        ("equivalence", "MAT 1275CO"), ("equivalence", "MAT 1275"),
    ]  # fmt: skip
    assert kinds("DENTAL HYGIENE STUDENTS ONLY") == [("placement", "DENTAL HYGIENE STUDENTS ONLY")]
    assert kinds("Algebra 1 Regents score of 75 or higher OR Geometry Regents score of 70") == [
        ("placement", "Algebra 1 Regents score of 75 or higher OR Geometry Regents score of 70")
    ]  # fmt: skip


def chain_data():
    d = data()
    d.courses["DEN 2315"] = [course("DEN 2315", "Prerequisites: DEN 1200 & BIO 3302.")]
    d.courses["DEN 2300"] = [course("DEN 2300", "Prerequisites: DEN 1200. Corequisites: DEN 2413.")]
    d.courses["DEN 1200"] = [
        course("DEN 1200", "CUNY proficiency in English; MUST NOT HAVE PASSED DEN 9000")
    ]
    return d


def test_the_tree_follows_prerequisites_only_and_marks_the_rest():
    tree = prerequisite_tree("DEN 2400", chain_data())
    assert [(i["kind"], i["code"]) for i in tree["items"]] == [
        ("prerequisite", "DEN 2300"), ("prerequisite", "DEN 2315"), ("corequisite", "DEN 2413"),
    ]  # fmt: skip
    den2300 = tree["items"][0]["node"]
    assert [i["kind"] for i in den2300["items"]] == ["prerequisite", "corequisite"]
    den1200 = den2300["items"][0]["node"]
    assert [(i["kind"], i.get("code") or i["text"]) for i in den1200["items"]] == [
        ("placement", "CUNY proficiency in English"), ("exclusion", "DEN 9000"),
    ]  # fmt: skip
    den2315 = tree["items"][1]["node"]
    assert den2315["items"][0] == {"kind": "prerequisite", "code": "DEN 1200", "node": None,
                                   "expanded_elsewhere": True}  # fmt: skip
    assert den2315["items"][1]["node"]["record"] is False  # BIO 3302 has no record


def test_tree_lists_courses_with_and_without_records_and_renders_the_marks():
    tree = prerequisite_tree("DEN 2400", chain_data())
    assert tree_courses(tree) == ["DEN 2400", "DEN 2300", "DEN 1200", "DEN 2315"]
    assert tree_without_records(tree) == ["BIO 3302"]
    text = "\n".join(render_tree(tree))
    assert "- DEN 2400 (T DEN 2400): Prerequisites: DEN 2300 & DEN 2315." in text
    assert "  - corequisite, not followed: DEN 2413" in text
    assert "- prerequisite BIO 3302: **no record**" in text
    assert "placement or proficiency text, walk stops: CUNY proficiency in English" in text
    assert "exclusion, not a prerequisite: DEN 9000" in text
    assert "prerequisite DEN 1200: shown elsewhere in this tree" in text


def test_a_cycle_through_prerequisites_does_not_loop():
    d = GoldData()
    d.courses = {
        "AAA 100": [course("AAA 100", "PRE: BBB 200")],
        "BBB 200": [course("BBB 200", "PRE: AAA 100")],
    }
    tree = prerequisite_tree("AAA 100", d)
    assert tree["items"][0]["node"]["items"][0]["expanded_elsewhere"] is True


def test_load_questions_reads_lines_and_names_the_bad_line(tmp_path):
    path = tmp_path / "q.jsonl"
    path.write_text(
        json.dumps(good()) + "\n\n" + json.dumps(good(id="q02")) + "\n", encoding="utf-8"
    )
    assert [r["id"] for r in load_questions(path)] == ["q01", "q02"]
    path.write_text(json.dumps(good()) + "\n{broken\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        load_questions(path)


def test_review_marks_empty_and_unresolved_questions_and_shows_gold_text(tmp_path):
    d = data()
    d.processed = tmp_path
    (tmp_path / "pages" / "registrar").mkdir(parents=True)
    sections = [{"markdown": "first"}, {"markdown": "second"}, {"markdown": "Grades text"}]
    (tmp_path / "pages" / "registrar" / "faqs.json").write_text(json.dumps({"sections": sections}))
    cal = {"id": "fall-2026-044", "source": CALENDAR, "heading": "Fall 2026: SAP appeal deadline"}
    rows = [
        good(),
        good(id="q02", gold_sources=[]),
        good(id="q03", gold_sources=[{**cal, "id": "TODO"}]),
        good(
            id="q04",
            gold_sources=[
                cal,
                {"id": "catalog:DEN 2400", "source": "catalog_course", "heading": "DEN 2400"},
            ],
        ),
    ]
    text = render(rows, d)
    assert "## q01\n" in text and "Grades text" in text
    assert "## q02 — **NO GOLD SOURCES**" in text
    assert "## q03 — **UNRESOLVED**" in text and "UNRESOLVED: unresolved (TODO)" in text
    assert "- weekday as printed: Friday" in text and "- date: 2026-11-13" in text
    assert "Prerequisite text: Prerequisites: DEN 2300 & DEN 2315" in text


def test_review_shows_the_tree_for_q20_and_q22_only(tmp_path):
    src = [{"id": "catalog:DEN 2400", "source": "catalog_course", "heading": "DEN 2400"}]
    text = render(
        [good(id="q20", gold_sources=src), good(id="q21", gold_sources=src)], chain_data()
    )
    assert text.count("Prerequisite tree below DEN 2400") == 1
    assert "Courses in the tree with records: DEN 2400, DEN 2300, DEN 1200, DEN 2315." in text
    assert "Named but with no record: BIO 3302." in text


def test_a_placeholder_gold_answer_fails_except_for_the_exempt_abstain_questions():
    for placeholder in ("TODO", "FILL_FROM_CALENDAR"):
        assert answer_problems(good(gold_answer=placeholder)) == [
            f"gold_answer is still {placeholder}"
        ]
    assert answer_problems(good(gold_answer="Monday, January 25, 2027")) == []
    for qid in ("q25", "q26", "q27", "q28", "q29"):
        assert answer_problems(good(id=qid, gold_answer="TODO")) == []
    assert answer_problems(good(id="q30", gold_answer="TODO")) != []
    assert answer_problems(good(id="q24", gold_answer="TODO")) != []


def test_check_all_and_the_findings_include_the_placeholder_check():
    rows = [good(id="q01", gold_answer="TODO"), good(id="q02", gold_answer="A real answer.")]
    results = check_all(rows, data())
    assert results["q01"] == ["gold_answer is still TODO"] and results["q02"] == []
    findings = eval_findings(rows, data())
    assert [(f.check, f.severity, f.course) for f in findings] == [("eval_question", "fail", "q01")]


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not (ROOT / "eval" / "questions.jsonl").exists(), reason="no questions file")
def test_the_real_file_has_102_well_formed_rows_with_unique_ids():
    rows = load_questions()
    assert [r["id"] for r in rows if answer_problems(r)] == []  # no TODO or FILL_FROM_CALENDAR
    # q01 to q60, the 14 calendar questions of step 4a-1 (q70 dropped), the 12 chain ones of 4b-1
    expected = [f"q{n:02d}" for n in range(1, 70)] + [
        f"q{n}" for n in range(71, 104)
    ]  # q96 to q103: tester round
    assert [r["id"] for r in rows] == expected
    splits = [r["split"] for r in rows]
    assert splits.count("dev") == 71 and splits.count("test") == 31
    assert all(row_problems(r) == [] for r in rows) and duplicate_ids(rows) == set()


@pytest.mark.skipif(
    not (ROOT / "data" / "processed" / "pages").exists(), reason="no processed data"
)
def test_every_real_gold_source_resolves():
    results = check_all(load_questions(), load_gold_data())
    assert {q: p for q, p in results.items() if p} == {}
