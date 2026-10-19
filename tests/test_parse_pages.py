import json
import shutil
from pathlib import Path

from cta.parse.pages import build_contacts, build_pages, record_for, slug_of
from tests.test_parse_html import PAGES

HOST = "https://www.citytech.cuny.edu"


def entry(path, name, kind="office", owner="bursar", status=200, error=""):
    return {
        "url": HOST + path, "kind": kind, "owner": owner, "status": status, "error": error,
        "final_url": HOST + path if status else None,
        "saved_as": f"raw/{name}.html" if name else None,
        "content_hash": "h" if status else None, "fetched_at": "2026-10-11T00:00:00+00:00",
    }  # fmt: skip


def test_slug_of():
    assert slug_of(HOST + "/bursar/refund-policy.aspx") == "refund-policy"
    assert slug_of(HOST + "/computer-systems/") == "index"


def test_build_pages_writes_one_json_per_page_and_uses_manifest_owner(tmp_path):
    raw = tmp_path / "raw_root"
    (raw / "raw").mkdir(parents=True)
    for name in ("bursar_refund_policy", "writing_intensive_empty"):
        shutil.copy(PAGES / f"{name}.html", raw / "raw" / f"{name}.html")
    manifest = [
        entry("/bursar/refund-policy.aspx", "bursar_refund_policy"),
        entry(
            "/advisement/writing-intensive-fall26.aspx",
            "writing_intensive_empty",
            owner="advisement",
        ),
        entry(
            "/computer-systems/",
            None,
            "department",
            "CST-NYT",
            status=None,
            error="FetchBlocked: x",
        ),
        entry("/dental/gone.aspx", None, "department", "DENT-NYT", status=404),
    ]
    records = build_pages(manifest, raw, tmp_path / "out")
    assert [r["status"] for r in records] == ["collected"] + ["not_collected"] * 3
    assert records[1]["reason"] == "main content empty in raw HTML"
    assert records[2]["reason"] == "not fetched: FetchBlocked: x"
    assert records[3]["reason"] == "http 404"
    written = sorted(
        p.relative_to(tmp_path / "out") for p in (tmp_path / "out" / "pages").rglob("*.json")
    )
    assert [str(p) for p in written] == [
        "pages/CST-NYT/index.json", "pages/DENT-NYT/gone.json",
        "pages/advisement/writing-intensive-fall26.json", "pages/bursar/refund-policy.json",
    ]  # fmt: skip
    saved = json.loads((tmp_path / "out/pages/bursar/refund-policy.json").read_text())
    assert saved["owner"] == "bursar" and saved["sections"][0]["heading"].startswith(
        "Refund Policy and"
    )


def collected(owner, panels, url, **over):
    contact = {
        "embed": False,
        "panels": panels,
        "emails": ["a@citytech.cuny.edu"],
        "phones": [],
        "fax": [],
        "ai_agent_line": [],
    }
    return {"status": "collected", "owner": owner, "kind": "office", "source_url": url,
            "fetched_at": "2026-10-11T00:00:00+00:00", "contact": contact, **over}  # fmt: skip


CONTACT = [{"heading": "CONTACT US", "markdown": "300 Jay Street"}]
HOURS = [*CONTACT, {"heading": "OFFICE HOURS", "markdown": "Mon 9-5"}]


def test_contact_record_is_one_per_owner_when_panels_are_identical():
    recs = [collected("bursar", CONTACT, "u1"), collected("bursar", CONTACT, "u2"),
            collected("registrar", CONTACT, "u3")]  # fmt: skip
    contacts = build_contacts(recs)
    assert sorted(contacts) == ["bursar", "registrar"]
    assert contacts["bursar"]["consistent"] is True and "variants" not in contacts["bursar"]
    assert contacts["bursar"]["source_pages"] == ["u1", "u2"]
    assert contacts["bursar"]["emails"] == ["a@citytech.cuny.edu"]


def test_contact_record_reports_panels_that_differ_without_guessing():
    recs = [collected("x", CONTACT, "u1"), collected("x", HOURS, "u2"), collected("x", HOURS, "u3")]
    c = build_contacts(recs)["x"]
    assert c["consistent"] is False
    assert [p["heading"] for p in c["panels"]] == ["CONTACT US", "OFFICE HOURS"]  # most common set
    assert [v["pages"] for v in c["variants"]] == [["u2", "u3"], ["u1"]]


def test_pages_that_are_not_collected_do_not_count_for_contacts():
    gone = collected("x", [], "u9", status="not_collected")
    assert build_contacts([collected("x", CONTACT, "u1"), gone])["x"]["consistent"] is True


def test_no_index_pages_are_kept_with_index_false_and_a_reason(tmp_path):
    raw = tmp_path / "raw_root" / "raw"
    raw.mkdir(parents=True)
    shutil.copy(PAGES / "bursar_refund_policy.html", raw / "a.html")
    e = entry("/bursar/refund-policy.aspx", "a")
    e["saved_as"] = "raw/a.html"
    rec = record_for(e, tmp_path / "raw_root")
    assert rec["index"] is True and rec["index_reason"] is None
    off = record_for(e, tmp_path / "raw_root", {e["url"]: "links only"})
    assert off["index"] is False and off["index_reason"] == "links only"
    assert off["status"] == "collected" and off["sections"]  # the record is kept


def test_not_collected_pages_are_not_indexed():
    rec = record_for(entry("/x.aspx", None, status=404), Path("."))
    assert rec["index"] is False and rec["index_reason"] == "not collected: http 404"


def test_contact_panel_is_marked_embed_false():
    html = (PAGES / "bursar_refund_policy.html").read_bytes()
    from cta.parse.html import parse_page

    rec = parse_page(html, {"source_url": HOST + "/x.aspx", "final_url": HOST + "/x.aspx",
                            "fetched_at": "t", "content_hash": "h", "http_status": 200,
                            "kind": "office", "owner": "bursar"})  # fmt: skip
    assert rec["contact"]["embed"] is False


def test_page_metadata_adds_doc_type_and_note_and_no_index_overrides_index(tmp_path):
    raw = tmp_path / "raw_root" / "raw"
    raw.mkdir(parents=True)
    shutil.copy(PAGES / "bursar_refund_policy.html", raw / "a.html")
    e = entry("/bursar/refund-policy.aspx", "a")
    e["saved_as"] = "raw/a.html"
    meta = {e["url"]: {"doc_type": "contacts", "note": "lists staff emails"}}
    rec = record_for(e, tmp_path / "raw_root", None, meta)
    assert rec["doc_type"] == "contacts" and rec["note"] == "lists staff emails"
    assert rec["index"] is True  # kept for indexing
    plain = record_for(e, tmp_path / "raw_root")
    assert plain["doc_type"] is None and plain["note"] is None


def test_sources_yaml_decisions():
    from cta.settings import load_sources

    src = load_sources()
    base = "https://www.citytech.cuny.edu"
    assert src["no_index_pages"][f"{base}/advisement/interdisciplinary.aspx"] == (
        "class-section tables per term, out of scope"
    )
    assert set(src["no_index_pages"]) == {
        f"{base}/advisement/interdisciplinary.aspx",
        f"{base}/registrar/course-scheduling.aspx",
        f"{base}/electrical-telecomm/articulation-agreement.aspx",
        f"{base}/mathematics/articulation-agreement.aspx",
    }
    assert src["page_metadata"][f"{base}/advisement/virtual-advisors.aspx"] == {
        "note": "lists staff emails"
    }
    assert src["doc_types"] == [
        "policy", "calendar", "catalog_course", "program", "department", "faq", "aid", "howto",
        "contacts",
    ]  # fmt: skip


FIN_AID = (
    "300 Jay Street\n\nPhone: 718-260-5700\n\nIN-PERSON HOURS\n\n"
    "|  |  |\n| --- | --- |\n| Tuesday | 9:00 PM - 5:00 PM |\n\n"
    "PHONE HOURS\n\nPhone Number: 718-260-5700\n\n"
    "|  |  |\n| --- | --- |\n| Monday | 9:00 AM - 5:00 PM |\n\n"
    "FAFSA: 002696\n\nTAP: 1405"
)


def test_hours_inside_the_contact_panel_run_from_the_first_hours_line_to_the_last_table():
    from cta.parse.pages import hours_part

    part = hours_part(FIN_AID)
    assert part.startswith("IN-PERSON HOURS") and part.endswith("| Monday | 9:00 AM - 5:00 PM |")
    assert "PHONE HOURS" in part and "FAFSA" not in part and "300 Jay" not in part
    assert "9:00 PM - 5:00 PM" in part  # a typo on the page stays as printed
    assert hours_part("300 Jay Street\n\nPhone: 718-260-5700") is None


def test_hours_entries_take_hours_panels_and_the_hours_part_of_contact_us():
    from cta.parse.pages import hours_entries

    panels = [
        {"heading": "CONTACT US", "markdown": FIN_AID},
        {"heading": "OFFICE HOURS", "markdown": "Monday: 9:00 AM - 7:00 PM"},
        {"heading": "ANNOUNCEMENTS", "markdown": "10:00 AM party"},
    ]
    out = hours_entries(panels)
    assert [(h["heading"], h["where"]) for h in out] == [
        ("CONTACT US (hours part)", "inside the CONTACT US panel"),
        ("OFFICE HOURS", "panel"),
    ]
    assert all(h["embed"] is False for h in out)
    assert hours_entries([{"heading": "CONTACT US", "markdown": "no hours here"}]) == []


def test_the_contact_record_has_an_hours_field():
    recs = [collected("x", [{"heading": "OFFICE HOURS", "markdown": "9:00 AM - 5:00 PM"}], "u1")]
    c = build_contacts(recs)["x"]
    assert c["hours"][0]["heading"] == "OFFICE HOURS"
    assert build_contacts([collected("y", CONTACT, "u1")])["y"]["hours"] == []


RULES = [
    {"path": "/registrar/academic-calendar.aspx", "doc_type": "calendar"},
    {"path": "/advisement/virtual-advisors.aspx", "doc_type": "contacts"},
    {"path": "*/faqs.aspx", "doc_type": "faq"},
    {"path": "/registrar/*", "doc_type": "policy"},
    {"path": "/dental/*", "doc_type": "department"},
]


def test_doc_type_is_the_first_matching_rule_and_null_when_none_matches():
    from cta.parse.pages import doc_type_for

    base = "https://www.citytech.cuny.edu"
    assert doc_type_for(f"{base}/registrar/academic-calendar.aspx", RULES) == "calendar"
    assert doc_type_for(f"{base}/registrar/faqs.aspx", RULES) == "faq"  # faq before policy
    assert doc_type_for(f"{base}/registrar/grade-policies.aspx", RULES) == "policy"
    assert doc_type_for(f"{base}/dental/index.aspx", RULES) == "department"
    assert doc_type_for(f"{base}/library/hours.aspx", RULES) is None
    assert doc_type_for(f"{base}/registrar/faqs.aspx", None) is None


def test_the_real_rules_cover_every_collected_page_by_the_stated_decisions():
    from cta.parse.pages import doc_type_for
    from cta.settings import load_sources

    rules = load_sources()["page_doc_types"]
    base = "https://www.citytech.cuny.edu"
    expected = {
        "registrar/faqs.aspx": "faq", "registrar/grade-policies.aspx": "policy",
        "registrar/academic-calendar.aspx": "calendar", "bursar/refund-policy.aspx": "policy",
        "admissions/tuition-refund.aspx": "policy", "financial-aid/sap.aspx": "aid",
        "financial-aid/faqs.aspx": "faq", "advisement/six-steps.aspx": "howto",
        "advisement/virtual-advisors.aspx": "contacts",
        "computer-systems/degrees.aspx": "department",
        "mathematics/faqs.aspx": "faq", "dental/faq.aspx": "faq",
        "dental/clinic.aspx": "department", "electrical-telecomm/chairperson.aspx": "department",
    }  # fmt: skip
    for path, doc_type in expected.items():
        assert doc_type_for(f"{base}/{path}", rules) == doc_type, path
    assert doc_type_for(f"{base}/unknown/page.aspx", rules) is None


def test_page_records_carry_department_scope_term_and_last_updated(tmp_path):
    raw = tmp_path / "raw_root" / "raw"
    raw.mkdir(parents=True)
    shutil.copy(PAGES / "bursar_refund_policy.html", raw / "a.html")
    e = entry("/bursar/refund-policy.aspx", "a")
    e["saved_as"] = "raw/a.html"
    office = record_for(e, tmp_path / "raw_root", None, None, RULES)
    assert (office["department"], office["scope"], office["term"], office["last_updated"]) == (
        None, "city_tech", None, None,
    )  # fmt: skip
    e["kind"], e["owner"] = "department", "DENT-NYT"
    dept = record_for(e, tmp_path / "raw_root", None, None, RULES)
    assert (dept["department"], dept["scope"]) == ("DENT-NYT", "department")


def test_the_contact_record_carries_fax_and_the_ai_agent_line_next_to_phones():
    contact = {"embed": False, "panels": CONTACT, "emails": [], "phones": ["718-1"],
               "fax": ["718-2"], "ai_agent_line": ["718-3"]}  # fmt: skip
    rec = build_contacts([collected("admissions", CONTACT, "u1", contact=contact)])["admissions"]
    assert (rec["phones"], rec["fax"], rec["ai_agent_line"]) == (["718-1"], ["718-2"], ["718-3"])
