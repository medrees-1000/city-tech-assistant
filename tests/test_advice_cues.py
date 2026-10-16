"""Casual round, item 3: the extended NO ADVICE cues. Phrase sets in tests/advice_cue_phrases.py
(written before the code). No model call."""

import pytest

from cta.eval.questions import load_questions
from cta.graph import advice
from tests.advice_cue_phrases import NEGATIVES, POSITIVES

DEV = [q for q in load_questions() if q["split"] == "dev"]


def test_the_sets_have_the_pre_registered_sizes():
    assert (len(POSITIVES), len(NEGATIVES)) == (8, 12)


@pytest.mark.parametrize("question", POSITIVES)
def test_the_new_cues_with_an_action_word_are_detected(question):
    assert advice.needs_advice_rules(question)


@pytest.mark.parametrize("question", NEGATIVES)
def test_plain_rule_questions_and_cues_without_an_action_word_are_not(question):
    assert not advice.needs_advice_rules(question)


def test_cq14_is_the_payment_plan_action():
    names = [a.name for a in advice.matched_actions(POSITIVES[0])]
    assert names == ["payment_plan"]


def test_on_the_dev_questions_only_the_advice_ones_and_cq14_fire():
    fired = {q["id"] for q in DEV if advice.needs_advice_rules(q["question"])}
    assert fired == {"q30", "q47", "q91", "q92", "q112"}
