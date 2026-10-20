"""The small data-check tests: the entity check, the all-checks table, the contact checks, the
metadata checks and the heading cleanup with its check. No network, no model.
"""

import json
from pathlib import Path

import pytest
import yaml

from cta.crawl.catalog import decode_entities
from cta.index.metadata import chunk_metadata, null_problems
from cta.parse.html import clean_heading, to_sections
from cta.settings import ROOT
from cta.validate.__main__ import Area, details, table
from cta.validate.contacts import check_entry, phone_problem, run_contact_checks
from cta.validate.findings import Finding
from cta.validate.metadata import check_record_metadata, load_records, run_metadata_checks
from cta.validate.pages import check_entities, check_heading_markup, entities_in, run_heading_checks

# ---- from test_validate_entities.py ----

def test_entities_in_finds_named_and_numeric_forms_in_nested_values():
    data = {"a": "CAD&rsquo;s", "b": ["x &amp; y", {"c": "&#8217; and &#x27;"}], "n": 5}
    assert sorted(entities_in(data)) == ["&#8217;", "&#x27;", "&amp;", "&rsquo;"]
    assert entities_in({"a": "R&D and AT&T; plain text, a < b"}) == []


def test_check_fails_for_each_record_with_an_entity(tmp_path):
    (tmp_path / "courses").mkdir()
    (tmp_path / "courses" / "bad.json").write_text(json.dumps({"description": "design &amp; test"}))
    (tmp_path / "courses" / "good.json").write_text(json.dumps({"description": "design & test"}))
    count, findings = check_entities(tmp_path)
    assert count == 2 and len(findings) == 1
    assert findings[0].severity == "fail" and findings[0].course == "courses/bad.json"


def test_decode_entities():
    assert decode_entities("CAD&rsquo;s design &amp; test") == "CAD’s design & test"
    assert decode_entities(None) is None


# ---- from test_validate_all.py ----

def test_area_result_is_fail_only_for_unaccepted_failures():
    ok = Area("a", "3 things", [Finding("w", "warning", "careful")])
    assert (ok.result, len(ok.warnings), len(ok.failed)) == ("PASS", 1, 0)
    accepted = Finding("x", "fail", "known", accepted="owner knows")
    assert Area("b", "1", [accepted]).result == "PASS"
    assert Area("b", "1", [accepted]).accepted == [accepted]
    assert Area("c", "1", [Finding("x", "fail", "bad")]).result == "FAIL"


def test_a_skipped_area_is_never_a_pass():
    area = Area("pdfs", skipped="PDFs missing")
    assert area.result == "SKIPPED"
    assert "skipped: PDFs missing" in table([area]) and "SKIPPED" in table([area])


def test_table_has_one_row_per_area_with_counts():
    areas = [
        Area("courses", "197 courses", [Finding("w", "warning", "m")]),
        Area("pages", "63 pages", [Finding("f", "fail", "m")]),
    ]
    lines = table(areas).split("\n")
    assert lines[2] == "| courses | 197 courses | 0 | 0 | 1 | PASS |"
    assert lines[3] == "| pages | 63 pages | 1 | 0 | 0 | FAIL |"


def test_details_lists_every_finding_with_its_area_and_accepted_reason():
    areas = [Area("pages", "1", [Finding("k", "fail", "404", "u", accepted="known")])]
    assert details(areas) == ["[ACCEPTED] pages: k u: 404 (known)"]


# ---- from test_validate_contacts.py ----

PANEL = (
    "300 Jay Street\n\nPhone: 718-260-5300\n\nFax: 718-254-8643\n\n"
    "Call or chat 24/7 with our AI agent: 718-682-7179\n\nOffice Phone: 718-260-5500"
)
RECORD = {
    "panels": [{"markdown": PANEL}], "emails": ["a@x.edu"], "phones": ["718-254-8643"],
    "source_pages": ["https://x/p"], "fetched_at": "t1",
}  # fmt: skip


def entry(**kw):
    base = {"emails": ["a@x.edu"], "phones": ["718-260-5300"], "source": "s.json",
            "page": "https://x/p", "fetched_at": "t1"}  # fmt: skip
    return base | kw


def test_a_phone_line_and_an_office_phone_line_are_accepted():
    assert phone_problem("718-260-5300", PANEL.splitlines()) is None
    assert phone_problem("718-260-5500", PANEL.splitlines()) is None


def test_a_fax_only_number_is_refused_even_though_the_record_lists_it_as_a_phone():
    assert RECORD["phones"] == ["718-254-8643"]
    found = check_entry("EET", entry(phones=["718-254-8643"]), RECORD)
    assert [f.check for f in found] == ["contact_phone"]
    assert "only a fax" in found[0].message


def test_the_ai_agent_line_and_unknown_numbers_are_refused():
    assert "not on a Phone" in phone_problem("718-682-7179", PANEL.splitlines())
    assert "not in the record" in phone_problem("718-000-0000", PANEL.splitlines())


def test_an_email_not_in_the_record_and_a_wrong_source_are_refused():
    found = check_entry("x", entry(emails=[{"address": "b@x.edu"}], page="https://x/q",
                                    fetched_at="t2"), RECORD)  # fmt: skip
    assert sorted(f.check for f in found) == ["contact_email", "contact_source", "contact_source"]


def test_the_flyer_entry_checks_the_flyer_text_not_the_panels():
    flyer = {"sections": [{"text": "Coordinator\n718-260-5714\nf@x.edu"}]}
    ok = entry(emails=["f@x.edu"], phones=["718-260-5714"])
    assert check_entry("special-circumstances", ok, flyer) == []
    bad = check_entry(
        "special-circumstances", entry(emails=["f@x.edu"], phones=["718-000-0000"]), flyer
    )
    assert [f.check for f in bad] == ["contact_phone"]


def test_every_department_needs_an_entry(tmp_path):
    (tmp_path / "s.json").write_text(json.dumps(RECORD))
    cfg = {"offices": {"EET": entry()}}
    count, found = run_contact_checks(cfg, tmp_path, ["EET", "CST"])
    assert count == 1 and [(f.check, f.course) for f in found] == [("contact_missing", "CST")]


@pytest.mark.skipif(not (ROOT / "data" / "processed" / "contacts").exists(), reason="no data")
def test_the_real_contacts_file_passes_against_the_real_records():
    from cta.index.departments import load_departments

    cfg = yaml.safe_load((ROOT / "config" / "contacts.yaml").read_text(encoding="utf-8"))
    count, found = run_contact_checks(cfg, ROOT, list(load_departments()))
    assert count == 10 and found == []


# ---- from test_validate_metadata.py ----

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


# ---- from test_headings.py ----

LINKED = "[Computer Information Systems/AAS](https://citytech.catalog.cuny.edu/programs/CIS-AAS)"


def test_clean_heading_keeps_the_text_and_the_first_url():
    assert clean_heading(LINKED) == (
        "Computer Information Systems/AAS", "https://citytech.catalog.cuny.edu/programs/CIS-AAS",
    )  # fmt: skip
    assert clean_heading("Plain heading") == ("Plain heading", None)
    assert clean_heading(None) == (None, None)
    assert clean_heading("See [A](http://a) and [B](http://b)") == ("See A and B", "http://a")
    assert clean_heading("Fees [not a link] (really)") == ("Fees [not a link] (really)", None)


def test_to_sections_cleans_headings_parents_and_keeps_the_url_without_changing_order():
    blocks = [
        ("h", 1, "Degrees"),
        ("p", 0, "intro"),
        ("h", 2, LINKED),
        ("p", 0, "about it"),
        ("h", 3, "[Sub](https://x/y)"),
        ("p", 0, "deeper"),
        ("h", 2, "Plain"),
        ("p", 0, "text"),
    ]
    sections = to_sections(blocks)
    assert [s["heading"] for s in sections] == [
        "Degrees",
        "Computer Information Systems/AAS",
        "Sub",
        "Plain",
    ]
    assert [s["heading_url"] for s in sections] == [
        None, "https://citytech.catalog.cuny.edu/programs/CIS-AAS", "https://x/y", None,
    ]  # fmt: skip
    assert [p["heading"] for p in sections[2]["parents"]] == [
        "Degrees",
        "Computer Information Systems/AAS",
    ]
    assert all("](" not in s["heading"] for s in sections)


def record(*headings, parents=()):
    sections = [
        {"heading": h, "level": 2, "markdown": "t", "heading_url": None,
         "parents": [{"level": 1, "heading": p} for p in parents]}
        for h in headings
    ]  # fmt: skip
    return {"source_url": "https://x/p", "sections": sections}


def test_the_check_fails_for_link_markup_in_a_heading_or_a_parent():
    assert check_heading_markup(record("Plain", "Also plain")) == []
    found = check_heading_markup(record("[A](https://x)"))
    assert [f.check for f in found] == ["heading_markup"] and "section 1" in found[0].message
    found = check_heading_markup(record("Child", parents=("[Parent](https://x)",)))
    assert [f.check for f in found] == ["heading_markup"]
    assert len(run_heading_checks([record("[A](u)"), record("ok"), record("[B](u)")])) == 2


HEADINGS_ROOT = Path(__file__).resolve().parents[1] / "data" / "processed"


@pytest.mark.skipif(not (HEADINGS_ROOT / "pages").exists(), reason="no processed data")
def test_no_real_record_has_link_markup_and_linked_headings_keep_their_url():
    records = [
        json.loads(p.read_text("utf-8"))
        for g in ("pages/*/*.json", "pdfs/*.json", "departments/*/*.json")
        for p in sorted(HEADINGS_ROOT.glob(g))
    ]
    assert run_heading_checks(records) == []
    linked = [s for r in records for s in r["sections"] if s["heading_url"]]
    assert len(linked) == 11 and all(s["heading_url"].startswith("https://") for s in linked)
    assert all("heading_url" in s for r in records for s in r["sections"])
