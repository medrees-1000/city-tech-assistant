"""Tester round 1, item D: a course outside the four departments. No network, no model."""

import yaml

from cta.api import convert
from cta.graph import build, chain_render
from cta.graph import chain as ch
from cta.settings import ROOT, load_models
from tests.test_api import Client, ask, make_client_app
from tests.test_router import TODAY, Script, make_router

RECORDS = ch.load_records()
CFG = load_models(env={"CTA_RERANK": "off", "CTA_ROUTER_CHAIN": "on", "CTA_ROUTER_CONTACTS": "on"})
URL = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text())["catalog_api"]["origin"]
NEW = (
    "ABSTAIN: I only have catalog records for Computer Systems Technology, Mathematics, "
    "Electrical and Telecommunications Engineering Technology, and Dental Hygiene, so I can't "
    "tell you about {code}. The City Tech catalog is at {url}."
)


def test_the_prefix_set_is_read_from_the_records_and_has_no_eng():
    prefixes = ch.known_prefixes(RECORDS)
    assert prefixes == {code.split()[0] for code in RECORDS}
    assert {"CST", "MAT"} <= prefixes and "ENG" not in prefixes and "BIO" not in prefixes
    assert any(p.startswith(("EET", "ELET", "DEN")) for p in prefixes) or len(prefixes) >= 4
    # no hand-typed list: the function holds no prefix literal
    import inspect

    body = inspect.getsource(ch.known_prefixes).split('"""')[2]  # after the docstring
    assert "CST" not in body and "MAT" not in body


def test_the_catalog_url_is_the_one_in_the_config():
    assert ch.catalog_url() == URL == "https://citytech.catalog.cuny.edu"


def test_eng_1101_gets_the_new_text_and_no_contact(monkeypatch):
    router, _ = make_router(Script("prerequisite"), monkeypatch, build.load_events(), CFG)
    ans = router.answer("prereq for ENG 1101", TODAY, log=False)
    assert ans.text == NEW.format(code="ENG 1101", url=URL)
    assert ans.route == "abstain" and ans.abstain_reason == "chain_outside_departments"
    assert ans.router.get("contact_office") is None and "Contact" not in ans.text


def test_cst_9999_keeps_todays_no_record_text(monkeypatch):
    router, _ = make_router(Script("prerequisite"), monkeypatch, build.load_events(), CFG)
    ans = router.answer("prereq for CST 9999", TODAY, log=False)
    assert ans.text.startswith(
        "ABSTAIN: No record exists in the catalog data for CST 9999 in the four"
    )
    assert ans.abstain_reason == "chain_no_record"
    assert ans.router["contact_office"] == "CST-NYT"  # the department's card, as before


def test_a_code_with_a_known_prefix_but_no_record_is_not_outside():
    assert not ch.outside_departments("MAT 9999", RECORDS)
    assert ch.outside_departments("ENG 1101", RECORDS) and ch.outside_departments(
        "BIO 1101", RECORDS
    )


def test_through_the_api_it_is_a_chain_abstention_with_its_own_code_and_no_card(monkeypatch):
    c = make_client_app(Client("prerequisite"), monkeypatch)
    body = ask(c, "prereq for ENG 1101").json()
    assert body["abstained"] and body["route"] == "chain" and body["contact"] is None
    assert body["abstain_reason"] == "chain_outside_departments"
    assert body["answer"] == NEW.format(code="ENG 1101", url=URL).removeprefix("ABSTAIN: ")


def test_named_courses_and_the_chain_renderer_are_untouched():
    # a course named inside prerequisite text keeps "(no catalog record)", and the asked-course
    # sentence of a multi-course answer is the same one as before
    titles = {c: r["title"].strip() for c, r in RECORDS.items()}
    # MAT is in the data, so MAT 1476 keeps "(no catalog record)"
    assert chain_render.named("MAT 1476", titles) == "MAT 1476 (no catalog record)"
    assert "There is no catalog record for {code} " in chain_render.NO_RECORD_ASKED
    assert convert.abstain_code("chain_outside_departments") == "chain_outside_departments"
    assert (
        convert.public_route(
            build.RoutedAnswer("t", True, "chain_outside_departments", [], route="abstain")
        )
        == "chain"
    )
