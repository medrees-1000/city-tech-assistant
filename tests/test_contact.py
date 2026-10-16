"""Step 4c: the contact line after an abstention (plain code), its switch and its wiring."""

from types import SimpleNamespace

import pytest

from cta.answer import Answer
from cta.graph import build, contact, render
from cta.graph.build import Router
from cta.index.departments import load_departments
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


@pytest.mark.needs_data
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


# ---- the rules (contact policy v2: a contact only when the office clearly applies) ----


@pytest.mark.parametrize("reason", ["calendar_no_row", "calendar_unsupported_term"])
def test_rule_calendar_abstains_go_to_the_registrar(reason):
    assert office("Last day to drop in CST 1101 in Summer 2027?", reason=reason) == "registrar"
    assert office("When does Summer 2027 start?", reason=reason) == "registrar"


def test_rule_chain_no_record_goes_to_the_department_of_a_prefix_of_the_four_else_none():
    kw = {"reason": "chain_no_record"}
    assert office("What are the prerequisites for CST 4999?", **kw) == "CST-NYT"
    assert office("What are the prerequisites for MAT 9999?", **kw) == "MATH-NYT"
    assert office("Prerequisites for ENG 1101?", **kw) is None  # no longer defaults to Advisement


def test_rule_one_named_department_or_prefix():
    q = "What are the student hours for the Electrical Engineering Technology department?"
    assert office(q, first="page/advisement/virtual-advisors#15") == "EET-NYT"
    assert office("Who is teaching MAT 1475 this semester?") == "MATH-NYT"
    assert office("Are there open seats in CST 1101?") == "CST-NYT"
    assert office("How do I apply to Dental Hygiene?") == "DENT-NYT"
    assert contact.contact_line("MATH-NYT", C) == MATH


def test_two_departments_named_do_not_pick_one():
    assert office("Is CST 1101 harder than MAT 1275?", first="page/bursar/refund-policy#1") is None


def test_rule_account_cues_map_to_their_office():
    assert office("What is my GPA this semester?") == "registrar"
    assert office("Where are my grades?") == "registrar"
    assert office("what is my gpa") == "registrar"  # case does not matter
    assert office("What is my balance?") == "bursar"
    assert office("When is my financial aid coming?") == "financial-aid"


def test_account_cues_need_the_whole_phrase():
    assert contact.cue_office("What is the gpa of the program?", C) is None
    assert contact.cue_office("my gpas", C) is None
    assert office("What is the gpa of the program?") is None


@pytest.mark.parametrize(
    "chunk",
    [
        "page/registrar/incomplete#1", "page/advisement/virtual-advisors#2",
        "page/admissions/tuition-refund#1", "page/bursar/payment-plan#3",
        "page/financial-aid/sap#1", "page/DENT-NYT/faq#4", "dept/EET-NYT/program-x#6",
        "contact:bursar", "contact:MATH-NYT", "catalog:CST 2403",
        "pdf/dropping-withdrawing-fall-2026#4", "pdf/special-circumstances-flyer#2",
        "page/MATH-NYT/faqs#12",
    ],
)  # fmt: skip
def test_the_best_ranked_chunk_no_longer_adds_a_contact(chunk):
    for reason in ("below_threshold", "The sources do not say."):
        assert office("Can I take a class at another college?", first=chunk, reason=reason) is None


@pytest.mark.parametrize(
    "question",
    [
        "what questions can I ask you",  # the screenshot cases: a low-similarity best chunk
        "my mom died",
        "I can't log in to CUNYfirst with my email address student@mail.citytech.cuny.edu",
    ],
)
def test_the_manual_test_questions_get_no_contact_even_with_a_low_similarity_best_chunk(question):
    for chunk in ("page/MATH-NYT/faqs#12", "page/financial-aid/faqs#9", "page/DENT-NYT/faq#2"):
        a = ans(first=chunk, text="ABSTAIN: I could not find this in the City Tech sources I have.")
        assert contact.add_contact(a, question, C) is None
        assert a.text == "ABSTAIN: I could not find this in the City Tech sources I have."


def test_every_office_key_the_rules_can_return_has_an_entry():
    keys = set(C["cues"]) | {"registrar"} | set(load_departments())
    assert keys <= set(C["offices"])


# ---- add_contact ----


def test_a_non_abstaining_answer_is_never_touched():
    a = ans(abstained=False, text="Yes. [1]")
    assert contact.add_contact(a, "q?", C) is None and a.text == "Yes. [1]"


def test_an_abstention_with_a_clear_office_gets_the_line_once():
    a = ans(first=None, text="ABSTAIN: I could not find this.")
    assert contact.add_contact(a, "What is my GPA this semester?", C) == "registrar"
    assert a.text == f"ABSTAIN: I could not find this. {REGISTRAR}"
    contact.add_contact(a, "What is my GPA this semester?", C)
    assert a.text.count("Contact the Registrar") == 1 and a.text.startswith("ABSTAIN:")


def test_an_abstention_with_no_clear_office_is_left_as_it_was():
    a = ans(first="page/registrar/incomplete#1", text="ABSTAIN: I could not find this.")
    assert contact.add_contact(a, "Should I take an Incomplete?", C) is None
    assert a.text == "ABSTAIN: I could not find this."


# ---- config switch and wiring ----


def test_the_switch_defaults_to_on_can_be_turned_off_and_is_validated():
    assert load_models(env={})["router"]["contacts"] == "on"  # on since step 4c
    assert load_models(env={"CTA_ROUTER_CONTACTS": "off"})["router"]["contacts"] == "off"
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
        ([], "on"),
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


def test_contacts_on_adds_the_line_to_a_clear_retrieve_abstain_and_records_the_office(
    monkeypatch, events
):
    router, _ = make_router(monkeypatch, events, "on")
    got = router.answer("What is my GPA this semester?", TODAY, log=False)
    assert got.text == f"ABSTAIN: I could not find this. {REGISTRAR}" and got.abstained
    assert got.router["contact_office"] == "registrar"


def test_contacts_on_adds_nothing_when_no_office_clearly_applies(monkeypatch, events):
    router, _ = make_router(monkeypatch, events, "on")
    got = router.answer("what questions can I ask you", TODAY, log=False)
    assert got.text == "ABSTAIN: I could not find this." and got.abstained
    assert got.router["contact_office"] is None


def test_contacts_off_leaves_the_answer_as_it_was(monkeypatch, events):
    router, _ = make_router(monkeypatch, events, "off")
    got = router.answer("What is my GPA this semester?", TODAY, log=False)
    assert got.text == "ABSTAIN: I could not find this." and "contact_office" not in got.router


def test_contacts_on_does_not_touch_a_non_abstaining_answer(monkeypatch, events):
    router, _ = make_router(monkeypatch, events, "on", abstain=False)
    got = router.answer("Anything?", TODAY, log=False)
    assert got.text == "Fine. [1]" and got.router["contact_office"] is None


@pytest.mark.needs_data
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
        rebuild("ABSTAIN: write to a@b.edu")  # a real email: the log would have redacted it


# ---- account cues added in the chat polish ----


@pytest.mark.parametrize(
    "question",
    [
        "My EMPLID is 12345678, why is something wrong?",
        "What is my student ID?",
        "I forgot my password",
        "Can I use my email to log in to CUNYfirst?",
        "login problem",
        "Do I have a hold on my account?",
        "How do I remove my hold?",
        "Why are there holds? Where are my holds listed?",
        "What is the balance on my account?",
    ],
)
def test_account_only_words_are_account_questions_with_no_office(question):
    assert contact.account_cue(question, C) is True
    assert contact.cue_office(question, C) is None
    assert office(question) is None  # no card: the data names no office for these


def test_my_aid_maps_to_financial_aid_and_wins_over_an_account_only_word():
    assert office("Why is my aid late?") == "financial-aid"
    assert office("My EMPLID is 12345678, why is my aid late?") == "financial-aid"
    assert contact.account_cue("Why is my aid late?", C)


def test_account_words_need_the_whole_word_and_a_plain_question_is_not_one():
    assert not contact.account_cue("What is a logon page?", C)
    assert not contact.account_cue("Who can help me with aid?", C)  # not first person
    assert not contact.account_cue("How do I apply?", C)
    assert not contact.account_cue("A student identification card", C)


def test_hold_and_account_cues_name_no_office_because_the_data_names_none():
    for word in ("my hold", "my holds", "a hold on my", "my account"):
        assert word in C["account_only"]
        assert not any(word in words for words in C["cues"].values())
    assert office("Do I have a hold on my account?") is None


def test_a_hold_question_that_is_not_about_the_students_own_account_is_not_a_cue():
    assert not contact.account_cue("What is a hold?", C)
    assert not contact.account_cue("Can a hold be placed by the Bursar?", C)
    assert not contact.account_cue("Do holds stop registration?", C)
