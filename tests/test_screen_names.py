"""Batch 1, item 2 (docs/polish-triage.md G1-3): names typed without "my name is". Plain patterns on
the question only; no network, no database, no model."""

import pytest

from cta.api import screen
from cta.settings import load_models

G = load_models(env={})["guardrails"]


@pytest.mark.parametrize(
    "question,expected",
    [
        (
            "I'm Maria Lopez, when is the tuition deadline?",
            "I'm [NAME], when is the tuition deadline?",
        ),
        ("im Pat and I need the drop date", "im [NAME] and I need the drop date"),
        ("I am Jonathan Natov and I need help", "I am [NAME] and I need help"),
        (
            "this is Priya, what is the last day to add",
            "this is [NAME], what is the last day to add",
        ),
        ("name is Dwayne when do classes start", "name is [NAME] when do classes start"),
        ("Name: Aisha Khan. When is the deadline?", "Name: [NAME]. When is the deadline?"),
        ("call me Sam, how do I drop a class", "call me [NAME], how do I drop a class"),
        (
            "my name is jane doe and I need the deadline",
            "my name is [NAME] and I need the deadline",
        ),
        ("my name's priya, when is the deadline", "my name's [NAME], when is the deadline"),
        (
            "My name is Jane Doe and I need help",
            "My name is [NAME] and I need help",
        ),  # unchanged rule
        ("my name is jane when is tuition due", "my name is [NAME] when is tuition due"),
    ],
)
def test_names_typed_in_the_listed_ways_are_removed(question, expected):
    assert screen.scrub(question) == expected


@pytest.mark.parametrize(
    "question",
    [
        "i'm in my 7th semester when do i graduate",
        "this is the registrar office phone number right",
        "I am CST student, what do I need for CST 2403",
        "name of the chair",
        "what is the name of the chair of the math department",
        "I'm Not sure how to register",
        "I'm Confused about the tuition deadline",
        "I am Lost, how do I drop",
        "I'm Fine, just asking about fees",
        "This is Fall 2026, when is the last day to drop",
        "this is Computer Systems related, who is the chair",
        "I'm Sure the deadline is in October, right?",
        "My name is on the waitlist but I don't see the class",
        "my name is not on the roster",
        "my name is wrong on my transcript",
        "my name is missing from the list",
        "Prof. Natov is the chair, how do I email him",
        "the chair's name is a secret",
        "I am EET major, who do I ask",
        "I'm MAT 1475 Calculus I, help",
    ],
)
def test_course_department_acronym_and_ordinary_words_are_not_masked(question):
    assert screen.scrub(question) == question


def test_only_the_question_text_is_scrubbed_not_the_staff_names_in_an_answer():
    # the scrub is applied to the question in screen(); answers are never passed through it
    got = screen.screen("I'm Maria, who is the CST chair", G)
    assert "[NAME]" in got.question and got.removed_details is True


def test_a_question_with_a_name_gets_the_same_note_flag_as_my_name_is():
    a = screen.screen("my name is Jane Doe, when is the tuition deadline", G)
    b = screen.screen("I'm Jane Doe, when is the tuition deadline", G)
    assert a.removed_details is True and b.removed_details is True
    assert "Jane" not in b.question


def test_a_name_tag_already_in_the_question_is_not_masked_again():
    assert screen.scrub("my name is [NAME] and I'm [NAME]") == "my name is [NAME] and I'm [NAME]"


def test_the_existing_numbers_and_emails_are_still_removed_with_a_name():
    out = screen.scrub("I'm Maria, mail maria@example.edu, EMPLID 23456789")
    assert out == "I'm [NAME], mail [EMAIL], EMPLID [ID]"


def test_no_dev_or_held_out_question_is_changed_by_the_name_patterns():
    import json

    from cta.settings import ROOT

    changed = []
    for name in ("questions.jsonl", "questions_casual_v2.jsonl"):
        for line in (ROOT / "eval" / name).read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["split"] != "test" and screen.scrub_names(row["question"]) != row["question"]:
                changed.append(row["id"])
    assert changed == []
