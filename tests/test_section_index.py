import json

from cta.index.section_index import (
    by_source,
    calendar_rows,
    course_counts,
    heading_path,
    is_indexable,
    load_rows,
    null_counts,
    render,
    section_rows,
    term_cell,
)


def section(heading, markdown="text", parents=(), **extra):
    return {
        "heading": heading,
        "level": len(parents) + 1,
        "parents": [{"level": i + 1, "heading": p} for i, p in enumerate(parents)],
        "markdown": markdown,
        **extra,
    }


def page(**over):
    return {
        "source_url": "https://x/y.aspx",
        "kind": "department",
        "owner": "CST-NYT",
        "status": "collected",
        "index": True,
        "doc_type": "department",
        "department": "CST-NYT",
        "scope": "department",
        "term": None,
        "fetched_at": "2026-10-11T16:49:30+00:00",
        "last_updated": None,
        "sections": [section("A", "12345"), section("B", "123", parents=("A",))],
        **over,
    }


def test_heading_path_is_parents_then_heading():
    assert heading_path(section("C", parents=("A", "B"))) == "A > B > C"
    assert heading_path(section(None)) == "(no heading)"


def test_page_rows_have_the_requested_fields_and_stable_ids():
    rows = section_rows(page(), "page", "CST-NYT/y")
    assert rows[1] == {
        "id": "page/CST-NYT/y#2", "source": "https://x/y.aspx", "doc_type": "department",
        "department": "CST-NYT", "scope": "department", "term": None,
        "date": "2026-10-11T16:49:30+00:00", "last_updated": None, "aid_year": None, "terms": [],
        "heading_path": "A > B", "heading": "B", "chars": 3,
    }  # fmt: skip
    assert rows[0]["chars"] == 5


def test_office_pages_have_a_null_department_and_city_tech_scope():
    rows = section_rows(page(department=None, scope="city_tech", doc_type="policy"), "page", "r/z")
    assert (rows[0]["scope"], rows[0]["department"], rows[0]["doc_type"]) == (
        "city_tech",
        None,
        "policy",
    )


def test_sections_with_embed_false_are_left_out_but_ids_keep_counting():
    record = {
        "department": "DENT-NYT", "doc_type": "department", "scope": "department",
        "source_file": "data/pdfs/D.pdf", "term": None, "index": True,
        "sections": [section("Chair", embed=False), section("Description", "abc")],
    }  # fmt: skip
    rows = section_rows(record, "dept", "DENT-NYT/overview")
    assert [(r["id"], r["source"]) for r in rows] == [
        ("dept/DENT-NYT/overview#2", "data/pdfs/D.pdf")
    ]


def test_term_stays_null_for_aid_year_documents_but_the_table_shows_the_aid_year():
    pdf = {"doc_type": "aid", "scope": "city_tech", "source_file": "f.pdf", "aid_year": "2026-2027",
           "department": None, "term": None, "pdf_last_updated": None,
           "file_modified": "2026-07-27", "sections": [section("H")]}  # fmt: skip
    row = section_rows(pdf, "pdf", "f")[0]
    assert row["term"] is None and row["aid_year"] == "2026-2027" and row["date"] == "2026-07-27"
    assert term_cell(row) == "aid year 2026-2027"
    assert term_cell({**row, "aid_year": None}) == "-"
    assert term_cell({**row, "term": "Fall 2026"}) == "Fall 2026"


def test_null_counts_per_doc_type_count_sections_not_records():
    rows = section_rows(page(), "page", "a") + section_rows(
        page(department=None, scope="city_tech", doc_type="policy"), "page", "b"
    )
    counts = null_counts(rows)
    assert counts["department"]["sections"] == 2 and counts["department"]["department"] == 0
    assert counts["department"]["term"] == 2 and counts["department"]["last_updated"] == 2
    assert counts["policy"]["department"] == 2 and counts["policy"]["scope"] == 0


def test_only_indexed_and_collected_records_are_indexable():
    assert is_indexable(page())
    assert not is_indexable(page(index=False))
    assert not is_indexable(page(status="not_collected"))


def test_load_rows_reads_pages_pdfs_and_departments_and_counts_what_it_leaves_out(tmp_path):
    def write(path, record):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record), encoding="utf-8")

    write(tmp_path / "pages" / "CST-NYT" / "y.json", page())
    write(tmp_path / "pages" / "CST-NYT" / "n.json", page(index=False))
    pdf = {"doc_type": "aid", "scope": "city_tech", "source_file": "f.pdf", "index": True,
           "sections": [section("H")]}  # fmt: skip
    write(tmp_path / "pdfs" / "f.json", pdf)
    dept = {**pdf, "department": "CST-NYT", "doc_type": "program", "source_file": "d.pdf"}
    write(tmp_path / "departments" / "CST-NYT" / "program-x.json", dept)
    rows, left_out = load_rows(tmp_path)
    assert left_out == {"page": 1}
    assert [r["id"] for r in rows] == [
        "page/CST-NYT/y#1", "page/CST-NYT/y#2", "pdf/f#1", "dept/CST-NYT/program-x#1"
    ]  # fmt: skip
    assert list(by_source(rows)) == ["https://x/y.aspx", "f.pdf", "d.pdf"]


def test_calendar_and_course_counts(tmp_path):
    events = [{"term": "Fall 2026", "source_pdf": "a.pdf"}] * 2 + [
        {"term": "Winter 2027", "source_pdf": "b.pdf"}
    ]
    assert calendar_rows(events) == [
        {"term": "Fall 2026", "events": 2, "source_pdf": "a.pdf"},
        {"term": "Winter 2027", "events": 1, "source_pdf": "b.pdf"},
    ]
    for dept, n in (("CST-NYT", 2), ("MATH-NYT", 1)):
        (tmp_path / "courses" / dept).mkdir(parents=True)
        for i in range(n):
            (tmp_path / "courses" / dept / f"{i}.json").write_text("{}")
    assert course_counts(tmp_path) == {"CST-NYT": 2, "MATH-NYT": 1}


def test_render_groups_rows_by_source_and_ends_with_the_calendar_and_course_tables():
    rows = section_rows(page(), "page", "CST-NYT/y")
    text = render(rows, {"page": 1}, [{"term": "Fall 2026", "source_pdf": "a.pdf"}], {"CST-NYT": 4})
    assert "**2 sections** in 1 sources" in text and "| department | 2 |" in text
    assert "| department | 2 | 0 | 0 | 0 | 0 | 2 | 0 | 2 |" in text  # the null-count table
    assert text.count("### https://x/y.aspx") == 1
    row = "| page/CST-NYT/y#2 | department | CST-NYT | department | - | - | https://x/y.aspx"
    assert f"{row} | A > B | 3 |" in text
    assert "| Fall 2026 | 1 | a.pdf |" in text and "| total | 4 |" in text


def test_terms_counts_and_the_terms_column():
    from cta.index.section_index import terms_cell, terms_counts

    rows = section_rows(page(), "page", "a")
    rows[0]["terms"] = ["Fall 2026"]
    rows[1]["terms"] = ["Fall 2026", "Spring 2027"]
    assert terms_counts(rows) == {"department": {"sections": 2, "with_terms": 2, "several": 1}}
    assert terms_cell(rows[0]) == "Fall 2026" and terms_cell(rows[1]) == "Fall 2026; Spring 2027"
    assert terms_cell({"terms": []}) == "-"
    text = render(rows, {}, [], {})
    assert "| department | 2 | 2 | 1 |" in text and "| total | 2 | 2 | 1 |" in text
    assert "| Fall 2026; Spring 2027 |" in text
