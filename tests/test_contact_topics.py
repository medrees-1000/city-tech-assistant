"""Batch 1, item 1 (docs/polish-triage.md G1-1): topic cues add an office to a refusal that would
carry none. No network, no database, no model."""

from types import SimpleNamespace

import pytest

from cta.graph import contact

C = contact.load_contacts()


def ans(reason="below_threshold", abstained=True, text="ABSTAIN: I could not find this."):
    return SimpleNamespace(abstained=abstained, abstain_reason=reason, sources=[], text=text)


def offices(question, **kw):
    return contact.offices_for(question, ans(**kw), C)


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
    assert contact.offices_for("a zebra question", ans(), custom) == ["bursar"]
    assert contact.offices_for("fafsa", ans(), custom) == []


def test_every_topic_office_exists_and_every_word_is_lowercase():
    for office in C["topic_priority"]:
        assert office in C["offices"] and office in C["topic_cues"]
    for words in C["topic_cues"].values():
        assert all(w == w.lower() and w.strip() == w for w in words)


# ---- only text is added ----


def test_add_contact_only_appends_text_and_keeps_everything_else():
    a = ans(text="ABSTAIN: I could not find this.")
    before = a.text
    key = contact.add_contact(a, "how much fafsa pays")
    assert key == "financial-aid"
    assert a.text.startswith(before) and a.text.startswith("ABSTAIN:")
    assert a.abstained is True and a.abstain_reason == "below_threshold"
    assert a.text == f"{before} {contact.contact_line('financial-aid', C)}"


def test_two_offices_put_the_main_one_last_so_the_page_card_can_strip_it():
    a = ans()
    assert contact.add_contact(a, "I want to graudate early") == "advisement"
    main, second = contact.contact_line("advisement", C), contact.contact_line("registrar", C)
    assert a.text.endswith(main) and second in a.text
    assert a.text.removesuffix(main).rstrip().endswith(second)  # the other line stays in the text


def test_an_answer_that_did_not_abstain_is_never_touched():
    a = ans(abstained=False, reason=None, text="Fall classes start on ...")
    assert contact.add_contact(a, "how much fafsa pays") is None
    assert a.text == "Fall classes start on ..."


def test_adding_twice_adds_nothing_the_second_time():
    a = ans()
    contact.add_contact(a, "I want to graudate early")
    once = a.text
    contact.add_contact(a, "I want to graudate early")
    assert a.text == once


def test_a_question_with_no_office_leaves_the_refusal_exactly_as_it_was():
    a = ans()
    assert contact.add_contact(a, "how to become a senator in SGA") is None
    assert a.text == "ABSTAIN: I could not find this."


def test_the_eval_harness_still_reads_the_same_abstain_marker():
    from cta.answer import MARKER, parse_reply

    a = ans(text=f"{MARKER} nothing found.")
    contact.add_contact(a, "how much fafsa pays")
    assert parse_reply(a.text, 3)["abstained"] is True  # the same detection as before
