import json
from pathlib import Path

import pytest

from cta.eval.questions import (
    CALENDAR,
    GoldData,
    check_all,
    course_codes_in,
    duplicate_ids,
    gold_problem,
    load_gold_data,
    load_questions,
    plain,
    prerequisite_chain,
    question_problems,
    row_problems,
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
    rows = [good(id="q01"), good(id="q02"), good(id="q01")]
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


def test_a_stored_heading_with_link_markup_matches_its_visible_text():
    d = data()
    d.sections["page/a/b#1"] = {
        **SECTION,
        "id": "page/a/b#1",
        "heading_path": "Degrees > [CIS/AAS](https://c/p)",
    }
    src = {"id": "page/a/b#1", "source": SECTION["source"], "heading": "Degrees > CIS/AAS"}
    assert gold_problem(src, d) is None
    assert plain("A > [B](http://x) and [C](y)") == "A > B and C"


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


def test_prerequisite_chain_lists_named_courses_and_what_they_name():
    chain = prerequisite_chain("DEN 2400", data())
    assert chain["prerequisite_text"].startswith("Prerequisites: DEN 2300")
    assert [c["code"] for c in chain["named"]] == ["DEN 2300", "DEN 2315", "DEN 2413"]
    assert chain["named"][0]["names"] == ["DEN 1200"]
    assert chain["named"][1]["prerequisite_text"] is None
    assert chain["named"][2]["in_catalog"] is False
    assert prerequisite_chain("ZZZ 1", data())["prerequisite_text"] is None


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


def test_review_shows_the_chain_for_q20_and_q22_only(tmp_path):
    d = data()
    src = [{"id": "catalog:DEN 2400", "source": "catalog_course", "heading": "DEN 2400"}]
    text = render([good(id="q20", gold_sources=src), good(id="q21", gold_sources=src)], d)
    assert text.count("Suggestion for gold_sources (not in the file)") == 1
    assert "DEN 2300: Prerequisites: DEN 1200" in text and "names: DEN 1200" in text


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not (ROOT / "eval" / "questions.jsonl").exists(), reason="no questions file")
def test_the_real_file_has_30_well_formed_rows_with_unique_ids():
    rows = load_questions()
    assert [r["id"] for r in rows] == [f"q{n:02d}" for n in range(1, 31)]
    assert all(row_problems(r) == [] for r in rows) and duplicate_ids(rows) == set()


@pytest.mark.skipif(
    not (ROOT / "data" / "processed" / "pages").exists(), reason="no processed data"
)
def test_the_real_gold_sources_resolve_except_the_open_todo():
    results = check_all(load_questions(), load_gold_data())
    assert {q: p for q, p in results.items() if p} == {"q12": ["unresolved (TODO)"]}
