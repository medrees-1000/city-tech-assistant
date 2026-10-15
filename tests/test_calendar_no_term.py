"""Tester round 1, item C: a term with no calendar says so. No network, no database, no model."""

import json
import re

import pytest

from cta.eval.questions import load_questions
from cta.graph import build, terms
from cta.settings import ROOT, load_models
from tests.test_api import Client, ask, make_client_app
from tests.test_router import TODAY, Script, make_router

CFG = load_models(
    env={"CTA_RERANK": "off", "CTA_ROUTER_CHAIN": "off", "CTA_ROUTER_CONTACTS": "off"}
)
EVENTS = build.load_events()
LISTED = "Fall 2026, Winter 2027 and Spring 2027"
# the stored tester questions (5aa6e0dd, 4a7e826e) and the term the classifier gave
TESTER = [
    ("when does summer 2027 semester start", "summer 2027", "Summer 2027"),
    ("fall 2027 add/drop deadline?", "fall 2027", "Fall 2027"),
]


def wording(label: str) -> str:
    return f"No calendar has been published for {label} yet. The calendars I have cover {LISTED}."


@pytest.mark.parametrize(("question", "mention", "label"), TESTER)
def test_the_tester_questions_get_the_new_wording_and_keep_the_registrar_contact(
    monkeypatch, question, mention, label
):
    router, seen = make_router(Script("calendar", mention, []), monkeypatch, EVENTS, CFG)
    ans = router.answer(question, TODAY, log=False)
    assert ans.abstained and ans.route == "abstain" and seen == []
    assert ans.text.startswith("ABSTAIN: " + wording(label) + " Contact the Registrar: ")
    assert ans.abstain_reason == "calendar_unsupported_term"  # not calendar_no_row
    assert "I could not find that in the" not in ans.text


def test_the_listed_terms_are_read_from_the_calendar_data():
    assert terms.supported_terms(EVENTS) == ["Fall 2026", "Winter 2027", "Spring 2027"]
    assert build.no_term_text("Summer 2027", EVENTS) == wording("Summer 2027")
    assert build.no_term_text("Spring 2029", EVENTS) == wording("Spring 2029")  # any term outside


def test_the_contact_is_the_existing_registrar_one_not_a_new_one(monkeypatch):
    script = Script("calendar", "Summer 2027", [])
    router = build.Router(None, CFG, lambda: script, events=EVENTS)  # the real registrar contact
    text = router.answer("when does summer 2027 start", TODAY, log=False).text
    registrar = build.render.registrar_contact()
    assert text.endswith(f"Contact the Registrar: {registrar}.")
    record = json.loads((ROOT / "data/processed/contacts/registrar.json").read_text())
    assert all(item in text for item in [*record["emails"], *record["phones"]])


def test_an_unsupported_term_with_a_failed_selector_keeps_the_failure_code_but_the_true_wording(
    monkeypatch,
):
    script = Script("calendar", "Fall 2027", selector_text="not json")
    router, _ = make_router(script, monkeypatch, EVENTS, CFG)
    ans = router.answer("fall 2027 add/drop deadline?", TODAY, log=False)
    assert ans.abstain_reason == "calendar_selector_failed" and wording("Fall 2027") in ans.text


def test_a_published_term_with_no_matching_row_still_falls_through_to_retrieval(monkeypatch):
    router, seen = make_router(Script("calendar", "Fall 2026", []), monkeypatch, EVENTS, CFG)
    ans = router.answer("when is the faculty picnic in Fall 2026?", TODAY, log=False)
    assert len(seen) == 1 and ans.route == "calendar_fallthrough"  # unchanged: retrieval answers


def test_a_row_of_another_calendar_that_answers_is_still_used(monkeypatch):
    script = Script("calendar", "Fall 2027", ["spring-2027-040"])
    router, _ = make_router(script, monkeypatch, EVENTS, CFG)
    ans = router.answer("When does registration for Fall 2027 begin?", TODAY, log=False)
    assert ans.route == "calendar" and "No calendar has been published" not in ans.text


def test_through_the_api_it_is_a_calendar_abstention_with_the_registrar_card(monkeypatch):
    c = make_client_app(Client("calendar", "summer 2027", []), monkeypatch)
    body = ask(c, "when does summer 2027 semester start").json()
    assert body["abstained"] and body["route"] == "calendar"
    assert body["abstain_reason"] == "calendar_unsupported_term"
    assert body["contact"] and body["contact"]["office"] == "registrar"
    assert body["answer"] == wording("Summer 2027")  # the contact sentence moves to the card


def dev_term_changes() -> list[tuple[str, str, str]]:
    """Stored dev records whose classifier term resolves to an unpublished term (dev runs only)."""
    text = {q["id"]: q["question"] for q in load_questions() if q["split"] == "dev"}
    found = {}
    for path in sorted((ROOT / "eval" / "results").glob("*.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(run, dict) or run.get("split") != "dev":
            continue
        for r in run.get("per_question", []):
            mention = (r.get("router") or {}).get("term_mention")
            if r["id"] in text and mention:
                got = terms.resolve_term(mention, TODAY, EVENTS)
                if got.status == "unsupported":
                    found[r["id"]] = (text[r["id"]], mention, r.get("abstain_reason"))
    return [(k, *v[:2]) for k, v in sorted(found.items())]


def test_the_dev_questions_whose_answer_text_can_change_are_those_about_unpublished_terms():
    changed = dev_term_changes()
    print("dev questions with an unpublished term:", changed)
    # q34 ("... Summer 2027", gold ABSTAIN) and, since the tester round, q100 and q101 (Summer and
    # Fall 2027), which are about unpublished terms by design
    assert [c[0] for c in changed] == ["q100", "q101", "q34"]
    assert re.search(r"Summer 2027", {c[0]: c[1] for c in changed}["q34"])
