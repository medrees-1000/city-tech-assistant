"""Step 4c: the contact line after an abstention (plain code), its switch and its wiring."""

from types import SimpleNamespace

import pytest

from cta.answer import Answer
from cta.graph import build, contact, render
from cta.graph.build import Router
from cta.index.search import Search
from cta.settings import load_models
from tests.test_router import TODAY, Script

C = contact.load_contacts()
REGISTRAR = "Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800."
CST = (
    "Contact the Computer Systems Technology department: "
    "compsystech@citytech.cuny.edu, 718-260-5170."
)
MATH = "Contact the Mathematics department: mathematics@citytech.cuny.edu, 718-260-5380."


def ans(reason="below_threshold", first=None, abstained=True, text="ABSTAIN: nothing."):
    sources = [{"id": first, "department": None} | ({"department": "CST-NYT"} if first and
               first.startswith("catalog:") else {})] if first else []  # fmt: skip
    return SimpleNamespace(abstained=abstained, abstain_reason=reason, sources=sources, text=text)


def office(question, **kw):
    return contact.office_for(question, ans(**kw), C)


# ---- the wording ----


def test_the_registrar_line_is_byte_identical_to_the_calendar_abstain_line():
    assert contact.contact_line("registrar", C) == REGISTRAR
    assert render.abstain_text("x.", render.registrar_contact()).endswith(REGISTRAR)


def test_lines_print_email_and_phone_only_never_room_or_hours():
    cst = contact.contact_line("CST-NYT", C)
    assert cst == CST and "Namm" not in cst and "Monday" not in cst


def test_advisement_has_no_phone_and_labels_its_two_emails():
    line = contact.contact_line("advisement", C)
    assert "Advisement4u@citytech.cuny.edu (prospective and new students)" in line
    assert "transferadvisement@citytech.cuny.edu (transfer students)" in line
    assert line.endswith("virtual-advisors.aspx")


def test_fax_and_ai_agent_numbers_never_appear_in_any_line():
    lines = " ".join(contact.contact_line(k, C) for k in C["offices"])
    for number in ("718-254-8643", "718-254-8525", "718-682-7179"):
        assert number not in lines
    assert "Pena" not in lines  # Special Circumstances: role only


# ---- the rules, in order ----


@pytest.mark.parametrize("reason", ["calendar_no_row", "calendar_unsupported_term"])
def test_rule_1_calendar_abstains_go_to_the_registrar(reason):
    assert office("Last day to drop in CST 1101 in Summer 2027?", reason=reason) == "registrar"


def test_rule_2_chain_no_record_goes_to_the_department_of_the_prefix_else_advisement():
    kw = {"reason": "chain_no_record"}
    assert office("What are the prerequisites for CST 4999?", **kw) == "CST-NYT"
    assert office("Prerequisites for ENG 1101?", **kw) == "advisement"


def test_rule_3_one_named_department_or_prefix_wins_over_the_best_chunk():
    q = "What are the student hours for the Electrical Engineering Technology department?"
    assert office(q, first="page/advisement/virtual-advisors#15") == "EET-NYT"
    assert office("Who is teaching MAT 1475 this semester?") == "MATH-NYT"
    assert office("Are there open seats in CST 1101?") == "CST-NYT"
    assert contact.contact_line("MATH-NYT", C) == MATH
    assert office("How do I apply to Dental Hygiene?") == "DENT-NYT"


def test_rule_3_two_departments_do_not_pick_one():
    q = "Is CST 1101 harder than MAT 1275?"
    assert office(q, first="page/bursar/refund-policy#1") == "bursar"


def test_rule_4_account_cues_come_before_the_best_chunk():
    first = "page/MATH-NYT/faqs#12"
    assert office("What is my GPA this semester?", first=first) == "registrar"
    assert office("Where are my grades?", first=first) == "registrar"
    assert office("What is my balance?", first=first) == "bursar"
    assert office("When is my financial aid coming?", first=first) == "financial-aid"
    assert office("what is my gpa", first=first) == "registrar"  # case does not matter


def test_rule_4_needs_the_whole_word():
    assert office("What is the gpa of the program?") == "registrar"  # fallback, not a cue
    assert contact.cue_office("What is the gpa of the program?", C) is None
    assert contact.cue_office("my gpas", C) is None


@pytest.mark.parametrize(
    ("chunk", "expected"),
    [
        ("page/registrar/incomplete#1", "registrar"),
        ("page/advisement/virtual-advisors#2", "advisement"),
        ("page/admissions/tuition-refund#1", "admissions"),
        ("page/bursar/payment-plan#3", "bursar"),
        ("page/financial-aid/sap#1", "financial-aid"),
        ("page/DENT-NYT/faq#4", "DENT-NYT"),
        ("dept/EET-NYT/program-x#6", "EET-NYT"),
        ("contact:bursar", "bursar"),
        ("contact:MATH-NYT", "MATH-NYT"),
        ("catalog:CST 2403", "CST-NYT"),
        ("pdf/dropping-withdrawing-fall-2026#4", "registrar"),
        ("pdf/financial-aid-refund-calendar-2026-2027#5", "financial-aid"),
        ("pdf/special-circumstances-flyer#2", "special-circumstances"),
        ("pdf/cunyfirst-student-reference#7", "financial-aid"),
    ],
)
def test_rule_5_the_best_ranked_chunk_names_the_office(chunk, expected):
    assert office("Can I take a class at another college?", first=chunk) == expected


def test_rule_6_fallback_is_the_registrar():
    assert office("Something unrelated?") == "registrar"  # no chunk at all
    assert office("Something unrelated?", first="pdf/unknown-file#1") == "registrar"
    assert office("Something unrelated?", first="page/nowhere/x#1") == "registrar"


def test_every_office_key_the_rules_can_return_has_an_entry():
    keys = set(C["cues"]) | set(C["pdf_offices"].values()) | {C["fallback"], "advisement"}
    assert keys <= set(C["offices"])


# ---- add_contact ----


def test_a_non_abstaining_answer_is_never_touched():
    a = ans(abstained=False, text="Yes. [1]")
    assert contact.add_contact(a, "q?", C) is None and a.text == "Yes. [1]"


def test_an_abstention_gets_the_line_once():
    a = ans(first="page/registrar/incomplete#1", text="ABSTAIN: I could not find this.")
    assert contact.add_contact(a, "Should I take an Incomplete?", C) == "registrar"
    assert a.text == f"ABSTAIN: I could not find this. {REGISTRAR}"
    contact.add_contact(a, "Should I take an Incomplete?", C)
    assert a.text.count("Contact the Registrar") == 1 and a.text.startswith("ABSTAIN:")


# ---- config switch and wiring ----


def test_the_switch_defaults_to_off_and_is_validated():
    assert load_models(env={})["router"]["contacts"] == "off"
    assert load_models(env={"CTA_ROUTER_CONTACTS": "on"})["router"]["contacts"] == "on"
    with pytest.raises(ValueError, match="router.contacts"):
        load_models(env={"CTA_ROUTER_CONTACTS": "maybe"})


def test_the_cli_flag_overrides_the_config(monkeypatch):
    from contextlib import nullcontext

    from cta.eval import run_answers

    seen = []
    monkeypatch.setattr(run_answers, "connect", lambda: nullcontext())
    monkeypatch.setattr(run_answers, "relabel", lambda conn, label, cfg: seen.append(cfg) or "")
    for flag, expected in (
        (["--contacts", "on"], "on"),
        (["--contacts", "off"], "off"),
        ([], "off"),
    ):
        run_answers.main(["x", "--relabel", "some-label", *flag])
        assert seen[-1]["router"]["contacts"] == expected


def make_router(monkeypatch, events, contacts, abstain=True):
    cfg = load_models(
        env={"CTA_RERANK": "off", "CTA_ROUTER_MODE": "on", "CTA_ROUTER_SELECTOR": "1",
             "CTA_ROUTER_CHAIN": "off", "CTA_ROUTER_CONTACTS": contacts}
    )  # fmt: skip
    text = "ABSTAIN: I could not find this." if abstain else "Fine. [1]"
    reason = "below_threshold" if abstain else None
    sources = [{"id": "page/registrar/incomplete#1"}]
    stub = Answer(text, abstain, reason, sources, [1], [], Search([], False, 0, 0, 0.0))
    monkeypatch.setattr(build, "answer", lambda *a, **k: stub)
    script = Script("other")
    return Router(None, cfg, lambda: script, events=events), script


@pytest.fixture(scope="module")
def events():
    return build.load_events()


def test_contacts_on_adds_the_line_to_a_retrieve_abstain_and_records_the_office(
    monkeypatch, events
):
    router, _ = make_router(monkeypatch, events, "on")
    got = router.answer("Should I take an Incomplete?", TODAY, log=False)
    assert got.text == f"ABSTAIN: I could not find this. {REGISTRAR}" and got.abstained
    assert got.router["contact_office"] == "registrar"


def test_contacts_off_leaves_the_answer_as_it_was(monkeypatch, events):
    router, _ = make_router(monkeypatch, events, "off")
    got = router.answer("Should I take an Incomplete?", TODAY, log=False)
    assert got.text == "ABSTAIN: I could not find this." and "contact_office" not in got.router


def test_contacts_on_does_not_touch_a_non_abstaining_answer(monkeypatch, events):
    router, _ = make_router(monkeypatch, events, "on", abstain=False)
    got = router.answer("Anything?", TODAY, log=False)
    assert got.text == "Fine. [1]" and got.router["contact_office"] is None


def test_a_calendar_abstain_is_byte_identical_with_the_switch_on(monkeypatch, events):
    registrar = render.registrar_contact()
    texts = {}
    for mode in ("off", "on"):
        router, _ = make_router(monkeypatch, events, mode)
        router.deps.contact = registrar
        router.deps.client_factory = lambda: Script("calendar", "Summer 2027", [])
        texts[mode] = router.answer("Last day to drop in Summer 2027?", TODAY, log=False).text
    assert texts["on"] == texts["off"] and texts["on"].count("Contact the Registrar") == 1


def test_the_replay_rebuilds_a_logged_calendar_abstain_exactly():
    from cta.eval.contact_replay import rebuild
    from cta.redact import redact

    real = render.abstain_text("I could not find that.", render.registrar_contact())
    assert rebuild(redact(real)) == real
    with pytest.raises(ValueError):
        rebuild("ABSTAIN: text with [ID] redacted")
