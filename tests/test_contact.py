"""The contact line after an abstention (plain code, step 4c): its rules, its switch and its wiring;
the topic cues that add an office to a refusal that would carry none (batch 1, item 1); the
department detection it uses; and the personal-account label (near-miss polish and possessive
cue, item 2). No network, no database, no model, no paid call.
"""

import json
import re
from types import SimpleNamespace

import pytest

from cta.answer import THRESHOLD_ABSTAIN, Answer
from cta.api import convert
from cta.graph import build, contact, render
from cta.graph.build import Router
from cta.index import departments as deps
from cta.index.departments import load_departments
from cta.index.search import Search
from cta.settings import ROOT, load_models
from tests.helpers import TODAY, Client, Script, ask, make_client_app, retrieve_answer

# ---- from test_contact.py ----
#
# Step 4c: the contact line after an abstention (plain code), its switch and its wiring.

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
    found = contact.offices_for(question, ans(**kw), C)
    return found[0] if found else None


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
    assert contact.cue_office(question, C) is None
    assert office(question) is None  # no card: the data names no office for these


def test_my_aid_maps_to_financial_aid_and_wins_over_an_account_only_word():
    assert office("Why is my aid late?") == "financial-aid"
    assert office("My EMPLID is 12345678, why is my aid late?") == "financial-aid"


def test_hold_and_account_cues_name_no_office_because_the_data_names_none():
    for word in ("my hold", "my holds", "a hold on my", "my account"):
        assert word in C["account_only"]
        assert not any(word in words for words in C["cues"].values())
    assert office("Do I have a hold on my account?") is None


# ---- from test_contact_topics.py ----
#
# Batch 1, item 1 (docs/archive/polish-triage.md G1-1): topic cues add an office to a refusal
# that would carry none. No network, no database, no model.

def topic_ans(reason="below_threshold", abstained=True, text="ABSTAIN: I could not find this."):
    return SimpleNamespace(abstained=abstained, abstain_reason=reason, sources=[], text=text)


def offices(question, **kw):
    return contact.offices_for(question, topic_ans(**kw), C)


@pytest.mark.parametrize(
    "question,expected",
    [
        ("how much fafsa pays", ["financial-aid"]),  # cv2-02
        ("i am in 7th semester when do i graudate", ["registrar"]),  # cv2-03 (typo alias)
        ("how mnay credits still left", ["advisement"]),  # cv2-05
        ("why am I taking finaincal managment", ["advisement"]),  # cv2-10
        ("I want to graudate early", ["advisement", "registrar"]),  # cv2-13, priority order
        ("why does dental hygine students gets charged 20$ per patinet", ["DENT-NYT"]),  # cv2-37
        ("who is the chair of registrar I want to email this trash guy", ["registrar"]),  # cv2-40
        ("does dental hugein share classes", ["DENT-NYT"]),
        ("who is my advsor", ["advisement"]),
        ("what if I don't pay my tution", ["bursar"]),
        ("what is the SAP rule", ["financial-aid"]),
        ("How do I get a TRANSCRIPT", ["registrar"]),  # case-insensitive
    ],
)
def test_topic_words_choose_the_office(question, expected):
    assert offices(question) == expected


@pytest.mark.parametrize(
    "question",
    ["how to become a senator in SGA", "is mechanical engineering hard", "payload tapestry aids"],
)
def test_no_topic_word_or_only_part_of_a_word_means_no_office(question):
    assert offices(question) == []  # whole words only: payload, tapestry and aids match nothing


def test_at_most_two_offices_in_the_order_of_the_priority_list():
    q = "fafsa tuition graduate advisor dental"
    assert offices(q) == ["DENT-NYT", "financial-aid"]
    assert C["topic_priority"][:2] == ["DENT-NYT", "financial-aid"]


def test_the_existing_rules_come_first_and_topics_are_not_added_to_them():
    assert offices("what is my gpa and tuition") == ["registrar"]  # a first-person cue
    assert offices("CST tuition") == ["CST-NYT"]  # a named department
    assert offices("when is it", reason="calendar_no_row") == ["registrar"]
    assert offices("tuition", reason="chain_outside_departments") == []
    assert offices("tuition", reason="chain_no_record") == []  # no department named: still none


def test_the_cues_live_in_config_not_in_code():
    custom = {**C, "topic_priority": ["bursar"], "topic_cues": {"bursar": ["zebra"]}}
    assert contact.offices_for("a zebra question", topic_ans(), custom) == ["bursar"]
    assert contact.offices_for("fafsa", topic_ans(), custom) == []


def test_every_topic_office_exists_and_every_word_is_lowercase():
    for office in C["topic_priority"]:
        assert office in C["offices"] and office in C["topic_cues"]
    for words in C["topic_cues"].values():
        assert all(w == w.lower() and w.strip() == w for w in words)


# ---- only text is added ----


def test_add_contact_only_appends_text_and_keeps_everything_else():
    a = topic_ans(text="ABSTAIN: I could not find this.")
    before = a.text
    key = contact.add_contact(a, "how much fafsa pays")
    assert key == "financial-aid"
    assert a.text.startswith(before) and a.text.startswith("ABSTAIN:")
    assert a.abstained is True and a.abstain_reason == "below_threshold"
    assert a.text == f"{before} {contact.contact_line('financial-aid', C)}"


def test_two_offices_put_the_main_one_last_so_the_page_card_can_strip_it():
    a = topic_ans()
    assert contact.add_contact(a, "I want to graudate early") == "advisement"
    main, second = contact.contact_line("advisement", C), contact.contact_line("registrar", C)
    assert a.text.endswith(main) and second in a.text
    assert a.text.removesuffix(main).rstrip().endswith(second)  # the other line stays in the text


def test_an_answer_that_did_not_abstain_is_never_touched():
    a = topic_ans(abstained=False, reason=None, text="Fall classes start on ...")
    assert contact.add_contact(a, "how much fafsa pays") is None
    assert a.text == "Fall classes start on ..."


def test_adding_twice_adds_nothing_the_second_time():
    a = topic_ans()
    contact.add_contact(a, "I want to graudate early")
    once = a.text
    contact.add_contact(a, "I want to graudate early")
    assert a.text == once


def test_a_question_with_no_office_leaves_the_refusal_exactly_as_it_was():
    a = topic_ans()
    assert contact.add_contact(a, "how to become a senator in SGA") is None
    assert a.text == "ABSTAIN: I could not find this."


def test_the_eval_harness_still_reads_the_same_abstain_marker():
    from cta.answer import MARKER, parse_reply

    a = topic_ans(text=f"{MARKER} nothing found.")
    contact.add_contact(a, "how much fafsa pays")
    assert parse_reply(a.text, 3)["abstained"] is True  # the same detection as before


@pytest.mark.parametrize(
    "question",
    [
        "when do I get a refund",
        "how are refunds paid",
        "was it refunded",
        "can I get my money back",
    ],
)
def test_refund_words_name_the_bursar(question):
    assert offices(question) == ["bursar"]


def test_drop_and_refund_list_the_bursar_first_and_the_registrar_second():
    # the fixed priority order puts the Bursar before the Registrar; two offices at most
    assert offices("if I drop with W do I get money refunded") == ["bursar", "registrar"]
    assert offices("drop a class, withdraw, refund, tuition, fafsa") == ["financial-aid", "bursar"]


# ---- register, enroll, sign up for classes (added Oct 17, 2026, found by review) ----


@pytest.mark.parametrize(
    "question",
    [
        "how do I register for classes",
        "how to register",
        "i am registering late, what do i do",
        "I already registered but the class is gone",
        "how do I sign up for classes",
        "how do I sign up for a class",
        "how do I enroll",
        "can I still enroll in a course",
        "I'm enrolling next semester",
    ],
)
def test_register_and_enroll_words_name_the_registrar(question):
    assert offices(question) == ["registrar"]


def test_a_named_department_or_a_first_person_cue_behaves_as_before():
    assert offices("how do I register for CST 1101") == ["CST-NYT"]  # the department rule first
    assert offices("how do I register for dental hygiene") == ["DENT-NYT"]
    assert offices("what is my gpa after I registered") == ["registrar"]  # a first-person cue


def test_registrar_still_ranks_after_the_other_offices_and_two_is_the_most():
    assert offices("how do I register and pay the tuition bill") == ["bursar", "registrar"]
    assert offices("register, fafsa, tuition, advisor") == ["financial-aid", "bursar"]


def test_registered_nurse_does_not_add_a_card_but_other_uses_do():
    assert offices("is the registered nurse program here") == []
    assert offices("do you offer registered nurses courses") == []
    assert (
        offices("registered dental hygienist exam dates") == []
    )  # a profession, not a department word
    assert offices("I registered nurse training but how do I register") == ["registrar"]
    assert "registered nurse" in C["topic_ignore"]


def test_the_ignore_phrases_live_in_config():
    custom = {**C, "topic_ignore": ["zebra register"], "topic_priority": ["registrar"]}
    assert contact.offices_for("zebra register", topic_ans(), custom) == []
    assert contact.offices_for("register", topic_ans(), custom) == ["registrar"]


# ---- from test_detect_departments.py ----
#
# Department detection by alias and code (used by the contact, clarify and screen steps).

def found(question: str) -> set[str]:
    return deps.detect_departments(question)


# ---- detection (no database) ----


def test_aliases_match_whole_words_and_ignore_case():
    assert found("What does the Electrical Engineering Technology department offer?") == {"EET-NYT"}
    assert found("what does the eet department offer") == {"EET-NYT"}
    assert found("Is there a Computer Systems Technology internship?") == {"CST-NYT"}
    assert found("How do I join the dental hygiene program?") == {"DENT-NYT"}
    assert found("What is my math placement?") == {"MATH-NYT"}
    assert found("Electrical & Telecommunications Engineering Technology degrees") == {"EET-NYT"}
    assert found("Electrical and Telecommunications Engineering Technology degrees") == {"EET-NYT"}


def test_aliases_do_not_match_inside_other_words():
    assert found("Meet the chair of the college") == set()  # "meet" is not "EET"
    assert found("How many feet is it?") == set()
    assert found("Is mathematical logic offered?") == set()  # "Math" is not "mathematical"
    assert found("What is the CSTA award?") == set()


def test_etet_and_eet_both_mean_the_electrical_department():
    assert found("ETET office hours") == {"EET-NYT"} == found("EET office hours")
    assert found("etet student hours") == {"EET-NYT"}


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What are the prerequisites for EET 3672?", {"EET-NYT"}),
        ("What are the prerequisites for EET3672?", {"EET-NYT"}),
        ("prerequisites for eet 3672", {"EET-NYT"}),
        ("What do I need before MAT 1275CO?", {"MATH-NYT"}),
        ("Can I take TCET 4102?", {"EET-NYT"}),  # a second EET-department prefix
        ("Is MEDU 4000 offered?", {"MATH-NYT"}),
        ("What is DEN 2400?", {"DENT-NYT"}),
        ("What is MST 1101?", {"CST-NYT"}),  # legacy prefix the catalog lists under CST
        ("What is CET 3672?", set()),  # a cross-listed prefix of another department: not mapped
        ("What is MECH 3672?", set()),
        ("What is the deadline for Fall 2026?", set()),  # "Fall 2026" looks like a code and is not
    ],
)
def test_course_codes_map_through_their_prefix(question, expected):
    assert found(question) == expected


def test_two_departments_in_one_question():
    assert found("Compare MAT 2675 with CST 1101") == {"MATH-NYT", "CST-NYT"}
    assert found("Do Dental Hygiene students take math?") == {"DENT-NYT", "MATH-NYT"}


def test_no_department_detected():
    assert found("How do I apply for graduation at City Tech?") == set()
    assert found("") == set()


def test_every_prefix_belongs_to_one_department_in_the_config():
    seen: dict[str, str] = {}
    for dept_id, info in deps.load_departments().items():
        for prefix in info["prefixes"]:
            assert seen.setdefault(prefix, dept_id) == dept_id
    assert set(deps.load_departments()) == {"CST-NYT", "MATH-NYT", "EET-NYT", "DENT-NYT"}


# ---- from test_personal_account.py ----
#
# Near-miss polish and possessive cue, item 2 (docs/decisions.md): a possessive plus an office noun
# alone no longer makes a policy abstention a personal-account refusal. The two lists were written
# before the code. No network, no database, no paid call. Only dev questions are read.

TABLE = contact.load_contacts()

MUST_REFUSE = [
    "what is my financial aid status", "do I have a hold on my account", "how much do I owe",
    "did my TAP get approved", "when will my refund be deposited", "what are my grades",
    "why was my financial aid denied", "is my application complete", "wheres my refund at",
    "did my fafsa go thru", "why is my aid so late", "whats my gpa rn",
    "i cant log in to cunyfirst", "what is my balance", "has my tap been approved yet",
    "do i have any holds on my account",
]  # fmt: skip
MUST_NOT = [
    "what happens if i dont accept my financial aid award by the deadline",
    "how does my financial aid get disbursed",
    "what do i need to do to keep my financial aid",
    "how do i accept my loan on cunyfirst",
    "when is my tuition bill due this fall",
    "how does my tuition get refunded if i drop",
    "does my financial aid cover books",
    "what happens to my refund if i withdraw",
    "how is my tuition calculated",
    "do i need to reapply for my tap every year",
    "what is the deadline to renew my fafsa",
    "how do i set up a payment plan for my tuition",
    "can i use my financial aid for summer classes",
    "what is the last day to drop to get my tuition back",
]  # fmt: skip


def code(question, reason="below_threshold"):
    return convert.abstain_code(reason, question, TABLE)


def test_the_lists_have_the_pre_registered_sizes():
    assert (len(MUST_REFUSE), len(MUST_NOT)) == (16, 14)


@pytest.mark.parametrize("question", MUST_REFUSE)
def test_every_must_refuse_question_is_still_a_personal_account_refusal(question):
    assert code(question) == "personal_account"
    assert code(question, "some model sentence") == "personal_account"


@pytest.mark.parametrize("question", MUST_NOT)
def test_no_must_not_question_is_relabelled(question):
    assert code(question) == "below_threshold"
    assert code(question, "some model sentence") == "model"


def test_the_cd9d2a93_question_is_a_plain_abstention_with_the_financial_aid_card_kept():
    q = "what happens if i dont accept my financial aid award by the deadline"
    assert code(q) == "below_threshold"
    assert (
        contact.cue_office(q, TABLE) == "financial-aid"
    )  # the contact logic is untouched (policy v2)
    assert old_account_cue(q, TABLE) is True  # the old rule, kept below, still says yes


def test_the_two_new_cues_are_the_only_account_only_additions_and_the_new_keys_exist():
    assert {"how much do i owe", "is my application complete"} <= set(TABLE["account_only"])
    assert len(TABLE["account_only"]) == 11
    assert set(TABLE["noun_cues"]) == {
        "my financial aid", "my aid", "my fafsa", "my tap", "my refund", "my tuition", "my bill",
    }  # fmt: skip
    for word in ("status", "approved", "denied", "deposited", "did my", "why is my", "wheres my"):
        assert word in TABLE["account_signals"]
    # every noun cue is one of the existing office cues: nothing new chooses a card
    existing = {w for words in TABLE["cues"].values() for w in words}
    assert set(TABLE["noun_cues"]) <= existing


def test_a_possessive_noun_alone_is_not_enough_but_with_a_signal_it_is():
    assert not contact.personal_account_cue("what is my financial aid", TABLE)
    assert contact.personal_account_cue("what is my financial aid status", TABLE)
    assert not contact.personal_account_cue("how does my tuition work", TABLE)
    assert contact.personal_account_cue("what is my balance", TABLE)  # a data cue by itself
    assert contact.personal_account_cue(
        "Why hasn’t my aid arrived", TABLE
    )  # a curly apostrophe works
    assert not contact.personal_account_cue("what is the status of the registrar line", TABLE)


def test_cue_office_is_unchanged():
    assert contact.cue_office("why is my aid late", TABLE) == "financial-aid"
    assert contact.cue_office("whats my gpa", TABLE) == "registrar"
    assert contact.cue_office("what is my balance", TABLE) == "bursar"
    assert contact.cue_office("do i have a hold on my account", TABLE) is None


# ---- zero changes for the dev questions ----


def dev_questions():
    out = {}
    for line in (ROOT / "eval/questions.jsonl").read_text(encoding="utf-8").splitlines():
        if re.search(r'"split": ?"dev"', line):  # selected by its raw text before it is parsed
            row = json.loads(line)
            out[row["id"]] = row["question"]
    return out


def old_account_cue(question, contacts):
    """The rule that chose "personal account" before this change: any office cue or account word."""
    text = question.lower()
    return contact.has_word(text, contacts.get("account_only", [])) or any(
        contact.has_word(text, words) for words in contacts["cues"].values()
    )


def old_code(reason, question):
    """The relabel rule before this change: any office cue or account word."""
    if reason is None:
        return None
    if reason.startswith(convert.OWN_CODES):
        return reason
    if old_account_cue(question, TABLE):
        return "personal_account"
    return reason if reason == "below_threshold" else "model"


# The pre-registered "zero changes" check could not be literally empty: q13 ("When is my tuition
# bill due this fall?") is a dev question AND on the owner's must-not list, so its relabel must
# change if it ever abstained. Checked instead: the exact set of dev questions whose relabel would
# differ, and that only q98 of them actually abstained through retrieval in the stored dev runs.
HYPOTHETICAL_CHANGES = {
    "q13",
    "q14",
    "q53",
    "q59",
    "q96",
    "q97",
    "q98",
}  # all personal_account -> plain


def test_exactly_these_dev_questions_would_be_relabelled_differently_and_none_else():
    dev = dev_questions()
    assert len(dev) == 91
    differ = set()
    for qid, question in dev.items():
        for reason in ("below_threshold", "some model sentence", "calendar_unsupported_term", None):
            if code(question, reason) != old_code(reason, question):
                differ.add(qid)
    assert differ == HYPOTHETICAL_CHANGES
    for qid in (
        differ
    ):  # each is a possessive plus an office noun with no account signal: a policy question
        assert old_account_cue(dev[qid], TABLE) and not contact.personal_account_cue(
            dev[qid], TABLE
        )
        assert (
            code(dev[qid]) == "below_threshold"
            and old_code("below_threshold", dev[qid]) == "personal_account"
        )


def test_in_the_stored_dev_runs_only_q98_abstained_through_retrieval_among_them():
    dev = dev_questions()
    abstained = set()
    for label in ("tester1-dev", "tester1-new8", "tester1-nearmiss2"):
        run = json.loads((ROOT / f"eval/results/{label}.json").read_text(encoding="utf-8"))
        for r in run["per_question"]:
            if (
                r["id"] in dev
                and r["abstained"]
                and r["route"] in ("other", "calendar_fallthrough")
            ):
                abstained.add(r["id"])
    assert abstained & HYPOTHETICAL_CHANGES == {
        "q98"
    }  # the others were answered: no relabel applies
    # every dev question that abstained and is not q98 gets the same code before and after
    for qid in abstained - {"q98"}:
        assert code(dev[qid]) == old_code("below_threshold", dev[qid]), qid


def test_the_eval_path_never_calls_the_relabel():
    for path in (ROOT / "src" / "cta" / "eval").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "abstain_code" not in text and "personal_account_cue" not in text, path


# ---- through the API ----


def abstain_app(monkeypatch):
    stub = retrieve_answer(THRESHOLD_ABSTAIN, True, "below_threshold", citations=())
    return make_client_app(Client(), monkeypatch, stub)


def test_the_cd9d2a93_question_gets_the_plain_abstention_and_the_financial_aid_card(monkeypatch):
    body = ask(
        abstain_app(monkeypatch),
        "what happens if i dont accept my financial aid award by the deadline",
    ).json()
    assert body["abstained"] and body["abstain_reason"] == "below_threshold"
    assert body["contact"]["office"] == "financial-aid"
    assert "personal account" not in body["answer"]


def test_a_must_refuse_question_is_still_refused_through_the_api(monkeypatch):
    body = ask(abstain_app(monkeypatch), "what is my financial aid status").json()
    assert (
        body["abstain_reason"] == "personal_account"
        and body["contact"]["office"] == "financial-aid"
    )
