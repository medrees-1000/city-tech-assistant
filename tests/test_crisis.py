"""Tester round 2, item A: crisis detection (phrase sets in tests/crisis_phrases.py, written before
the code; docs/decisions.md). Scripted client only: no paid call."""

import pytest

from cta.answer import THRESHOLD_ABSTAIN
from cta.api import screen
from cta.eval.questions import load_questions
from cta.settings import load_models
from tests.crisis_phrases import NEGATIVES, TIER1_POSITIVES, TIER2_NEW_POSITIVES
from tests.helpers import Client, ask, make_client_app, reply, retrieve_answer

G = load_models(env={})["guardrails"]
DEV = [q for q in load_questions() if q["split"] == "dev"]


def test_the_sets_have_the_pre_registered_sizes():
    assert len(TIER1_POSITIVES) >= 20 and len(NEGATIVES) >= 30
    for tester in ("i dont want to be alive anymore", "thinking about ending it all tonight"):
        assert tester in TIER1_POSITIVES


@pytest.mark.parametrize("question", TIER1_POSITIVES)
def test_tier_1_positives_get_the_988_reply(question):
    assert screen.screen(question, G).reason == "distress"


@pytest.mark.parametrize("question", TIER2_NEW_POSITIVES)
def test_tier_2_positives_get_the_stress_reply_not_988(question):
    assert not screen.is_distress(question)
    assert screen.screen(question, G).reason == "stress"


@pytest.mark.parametrize("question", NEGATIVES)
def test_negatives_fire_neither_tier(question):
    assert not screen.is_distress(question) and not screen.is_stress(question)
    assert screen.screen(question, G).reason is None


def test_zero_firings_on_the_dev_questions():
    assert DEV
    assert [q["id"] for q in DEV if screen.screen(q["question"], G).reason] == []


def test_the_idiom_list_removes_only_the_idiom():
    assert not screen.is_distress("i wanna die of embarrassment")
    assert screen.is_distress("i wanna die of embarrassment and i want to die for real")
    assert screen.without_idioms("im dead tired") == "im  "


def test_self_directed_phrases_still_fire_next_to_idioms():
    assert screen.is_distress("dying to know why i want to end it all")


TOPICS_THAT_NAME_IT = [
    "thoughts of suicide", "a desire to die", "wanting to die", "self-harm", "ending it all",
    "how to kill myself", "Suicide",
]  # fmt: skip


@pytest.mark.parametrize("topic_text", TOPICS_THAT_NAME_IT)
def test_an_abstain_whose_topic_sentence_names_self_harm_becomes_the_crisis_reply(
    monkeypatch, topic_text
):
    stub = retrieve_answer(THRESHOLD_ABSTAIN, True, "below_threshold", citations=())
    client = Client(topic=reply(topic_text, False))
    c = make_client_app(client, monkeypatch, stub)
    body = ask(c, "i feel so empty and tired of waking up every day").json()
    assert body["answer"] == screen.TEXTS["distress"] and body["answer_type"] == "guardrail"
    assert "988" in body["answer"]
    assert body["question"] == "" and c.logs[0]["status"] == "blocked_distress"
    assert c.logs[0]["question"] == ""
    assert c.get("/health").json()["blocked"]["distress"] == 1


@pytest.mark.parametrize(
    "topic_text", ["the death of a family member", "financial aid after a death"]
)
def test_a_death_in_the_topic_alone_does_not_trigger_it(monkeypatch, topic_text):
    stub = retrieve_answer(THRESHOLD_ABSTAIN, True, "below_threshold", citations=())
    c = make_client_app(Client(topic=reply(topic_text, False)), monkeypatch, stub)
    body = ask(c, "what is the meaning of the thing i read about").json()
    assert body["answer_type"] != "guardrail" and "988" not in body["answer"]


def test_a_bereavement_or_aid_question_that_mentions_a_death_is_answered(monkeypatch):
    client = Client()
    c = make_client_app(client, monkeypatch, retrieve_answer())
    body = ask(c, "what happens to my aid if a student passes away").json()
    assert body["answer_type"] != "guardrail" and client.calls


def test_a_non_abstain_answer_is_never_replaced(monkeypatch):
    c = make_client_app(Client(), monkeypatch, retrieve_answer("Suicide prevention is at 988. [1]"))
    assert ask(c, "where can I find the counseling page").json()["answer_type"] != "guardrail"
