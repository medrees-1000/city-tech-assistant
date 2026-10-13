import json

import pytest
import yaml

from cta.settings import ROOT
from cta.validate.contacts import check_entry, phone_problem, run_contact_checks

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
