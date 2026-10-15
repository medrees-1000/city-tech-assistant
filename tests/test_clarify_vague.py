"""Tester round 2, item C (T08): "when is it due" gets the clarify template. The phrase sets are
in tests/clarify_phrases.py (written before the code)."""

import pytest

from cta.eval.questions import load_questions
from cta.graph import clarify
from tests.clarify_phrases import NEGATIVES, POSITIVES
from tests.test_api import Client, ask, make_client_app

DEV = [q for q in load_questions() if q["split"] == "dev"]


def test_the_sets_have_the_pre_registered_sizes():
    assert (len(POSITIVES), len(NEGATIVES)) == (8, 13)


@pytest.mark.parametrize("question", POSITIVES)
def test_vague_when_questions_clarify(question):
    assert clarify.needs_clarification(question)


@pytest.mark.parametrize("question", NEGATIVES)
def test_questions_that_name_something_do_not(question):
    assert not clarify.needs_clarification(question)


def test_a_prerequisite_classification_still_blocks_it():
    assert not clarify.needs_clarification("when is it due", "prerequisite")


def test_dev_questions_that_clarify_are_the_same_as_before():
    # q88 and q89 were the only ones before this round (tests/test_clarify.py); the vague pattern
    # adds none
    assert sorted(q["id"] for q in DEV if clarify.needs_clarification(q["question"])) == [
        "q88", "q89",
    ]  # fmt: skip


def test_through_the_api_it_is_the_template_not_outside_what_i_can_answer(monkeypatch):
    client = Client()
    c = make_client_app(client, monkeypatch)
    body = ask(c, "when is it due").json()
    assert body["answer_type"] == "clarify" and body["answer"] == clarify.reply_text()
    assert "outside what I can answer" not in body["answer"]
