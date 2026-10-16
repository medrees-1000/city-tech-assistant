"""Post-freeze safety fix: first-person dying statements reach Tier 1 (988), exaggerations stay
untouched, ambiguous ones get the gentle reply, and the topic sentence never restates a death."""

import pytest

from cta.api import screen
from cta.settings import load_models
from tests.crisis_phrases_postfreeze import AMBIGUOUS, KILL_MYSELF, NEGATIVES, POSITIVES

G = load_models(env={})["guardrails"]


@pytest.mark.parametrize("question", POSITIVES)
def test_first_person_dying_statements_get_the_988_reply(question):
    result = screen.screen(question, G)
    assert result.reason == "distress"
    assert "988" in screen.reply("distress", G)


@pytest.mark.parametrize("question", NEGATIVES)
def test_ordinary_uses_of_die_and_dead_fire_nothing(question):
    assert screen.screen(question, G).reason is None


@pytest.mark.parametrize("question", AMBIGUOUS)
def test_ambiguous_die_statements_get_the_gentle_reply_not_988(question):
    assert not screen.is_distress(question)
    assert screen.screen(question, G).reason == "stress"
    assert "988" not in screen.reply("stress", G)


def test_the_tuition_kill_myself_message_still_gets_988():
    assert screen.screen(KILL_MYSELF, G).reason == "distress"


@pytest.mark.parametrize(
    "answer",
    [
        "I'm sorry, but I can only help with City Tech questions, so a question about your "
        "imminent death is outside what I can answer.",
        "I'm sorry, I couldn't find anything about your own death in the City Tech pages.",
        "I'm sorry, a question about dying is outside what I can answer.",
    ],
)
def test_an_abstain_sentence_that_restates_the_students_death_becomes_the_crisis_reply(answer):
    assert screen.names_self_harm(answer)


@pytest.mark.parametrize(
    "answer",
    [
        "I'm sorry, a question about your dad's death is outside what I can answer.",
        "I'm sorry, a question about the weather today is outside what I can answer.",
        "I'm sorry, I couldn't find anything about deadlines for dead courses.",
    ],
)
def test_other_abstain_sentences_are_not_turned_into_the_crisis_reply(answer):
    assert not screen.names_self_harm(answer)
