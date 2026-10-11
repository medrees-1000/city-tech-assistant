import json
from pathlib import Path

import pytest

from cta.index.metadata import chunk_metadata, null_problems
from cta.validate.metadata import check_record_metadata, load_records, run_metadata_checks

ALLOWED = ["policy", "calendar", "program", "department", "faq", "aid", "howto", "contacts"]


def sec(**over):
    return {"heading": "H", "level": 1, "parents": [], "markdown": "text", **over}


def page(**over):
    return {
        "source_url": "https://www.citytech.cuny.edu/registrar/faqs.aspx",
        "doc_type": "faq", "department": None, "scope": "city_tech", "term": None,
        "fetched_at": "2026-10-11T16:49:30+00:00", "last_updated": None,
        "index": True, "status": "collected", "sections": [sec()], **over,
    }  # fmt: skip


def pdf(**over):
    return {
        "source_file": "data/pdfs/a.pdf", "doc_type": "aid", "department": None,
        "scope": "city_tech", "term": None, "aid_year": "2026-2027",
        "pdf_last_updated": "2026-06-08", "file_modified": "2026-07-27T09:22:20-04:00",
        "file_created": None, "index": True, "sections": [sec()], **over,
    }  # fmt: skip


def dept(**over):
    return {
        "source_file": "data/pdfs/CST.pdf", "doc_type": "program", "department": "CST-NYT",
        "scope": "department", "term": None, "file_date": "2026-09-10T19:16:13",
        "last_updated": None, "index": True, "sections": [sec()], **over,
    }  # fmt: skip


def checks(record):
    return {f.check for f in check_record_metadata(record, ALLOWED)}


def test_complete_records_of_each_kind_pass():
    for record in (page(), pdf(), dept()):
        assert check_record_metadata(record, ALLOWED) == []


def test_chunk_metadata_reads_the_source_date_and_updated_keys_each_kind_uses():
    values, missing = chunk_metadata(pdf())
    assert missing == []
    assert values["source"] == "data/pdfs/a.pdf" and values["date"] == "2026-07-27T09:22:20-04:00"
    assert values["last_updated"] == "2026-06-08" and values["term"] is None
    values, _ = chunk_metadata(dept())
    assert values["date"] == "2026-09-10T19:16:13"
    values, _ = chunk_metadata(page())
    assert values["source"].endswith("faqs.aspx") and values["date"].startswith("2026-10-11")


def test_a_missing_key_fails_for_each_field():
    keys = [
        ("source_url", "source"), ("doc_type", "doc_type"), ("department", "department"),
        ("scope", "scope"), ("term", "term"), ("fetched_at", "date"),
        ("last_updated", "last_updated"),
    ]  # fmt: skip
    for key, field in keys:
        broken = page()
        del broken[key]
        found = check_record_metadata(broken, ALLOWED)
        assert [f.check for f in found] == ["metadata_missing_key"], key
        assert f"no key for {field}" in found[0].message


def test_a_null_where_null_is_not_allowed_fails():
    assert checks(page(scope=None)) == {"metadata_null"}
    assert checks(page(fetched_at=None)) == {"metadata_null"}
    assert checks(page(source_url=None)) == {"metadata_null"}
    assert checks(dept(department=None)) == {"metadata_null"}  # a department record needs one
    assert checks(page(doc_type=None)) == {"doc_type_missing"}


def test_null_is_fine_for_department_term_and_last_updated_on_office_records():
    record = page(department=None, term=None, last_updated=None)
    assert check_record_metadata(record, ALLOWED) == []
    ok = {"source": "s", "doc_type": "d", "scope": "cuny", "date": "x", "department": None,
          "term": None, "last_updated": None}  # fmt: skip
    assert null_problems(ok) == []


def test_a_doc_type_outside_the_allowed_list_fails():
    assert checks(page(doc_type="advisement_contacts")) == {"doc_type_not_allowed"}


def test_a_deliberately_broken_record_reports_every_problem_once():
    broken = page(scope=None, doc_type="made_up")
    del broken["fetched_at"]
    found = {(f.check, f.message.split(" (")[0]) for f in check_record_metadata(broken, ALLOWED)}
    assert found == {
        ("metadata_missing_key", "no key for date"),
        ("metadata_null", "scope is null"),
        ("doc_type_not_allowed", "'made_up' is not in the allowed list"),
    }


def test_records_with_nothing_to_embed_are_not_checked_except_for_a_missing_doc_type():
    off = page(index=False, scope=None)
    assert check_record_metadata(off, ALLOWED) == []
    flagged = check_record_metadata(page(index=False, doc_type=None), ALLOWED)
    assert [(f.check, f.severity) for f in flagged] == [("doc_type_missing", "warning")]
    gone = page(index=False, status="not_collected", doc_type=None)
    assert check_record_metadata(gone, ALLOWED) == []
    only_hidden = dept(sections=[sec(embed=False)], scope=None)
    assert check_record_metadata(only_hidden, ALLOWED) == []


def test_sections_with_embed_false_do_not_count_but_others_in_the_record_do():
    record = dept(sections=[sec(embed=False), sec()], scope=None)
    found = check_record_metadata(record, ALLOWED)
    assert [f.check for f in found] == ["metadata_null"] and "(1 sections)" in found[0].message


def test_run_checks_over_many_records_and_the_loader(tmp_path):
    (tmp_path / "pages" / "x").mkdir(parents=True)
    (tmp_path / "pages" / "x" / "a.json").write_text(json.dumps(page()), encoding="utf-8")
    (tmp_path / "pdfs").mkdir()
    (tmp_path / "pdfs" / "b.json").write_text(json.dumps(pdf(scope=None)), encoding="utf-8")
    records = load_records(tmp_path)
    assert len(records) == 2
    assert [f.check for f in run_metadata_checks(records, ALLOWED)] == ["metadata_null"]


REAL = Path(__file__).resolve().parents[1] / "data" / "processed"


@pytest.mark.skipif(not (REAL / "pages").exists(), reason="data/processed is not committed")
def test_the_real_records_pass():
    from cta.settings import load_sources

    records = load_records(REAL)
    assert run_metadata_checks(records, load_sources()["doc_types"]) == []
