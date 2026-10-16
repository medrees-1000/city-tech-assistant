"""Post-freeze safety sweep: every phrase of tests/crisis_sweep.py reaches the tier it should."""

import pytest

from cta.api import screen
from cta.settings import load_models
from tests.crisis_sweep import SWEEP

G = load_models(env={})["guardrails"]
TIER = {"D": "distress", "S": "stress", "N": None}


def phrases(code):
    return [q for q, expected in SWEEP if expected == code]


@pytest.mark.parametrize("question", phrases("D"))
def test_tier_1_phrases_get_the_988_reply(question):
    assert screen.screen(question, G).reason == "distress"


@pytest.mark.parametrize("question", phrases("S"))
def test_tier_2_phrases_get_the_gentle_reply(question):
    assert screen.screen(question, G).reason == "stress"


@pytest.mark.parametrize("question", phrases("N"))
def test_student_life_phrases_fire_nothing(question):
    assert screen.screen(question, G).reason is None


@pytest.mark.parametrize("question", phrases("A"))
def test_ambiguous_phrases_are_unchanged_until_the_owner_decides(question):
    # no tier decides these silently; moving one is a deliberate edit of this test and the list
    assert screen.screen(question, G).reason is None


def test_the_sweep_has_the_expected_shape():
    assert len(SWEEP) >= 40
    assert {e for _, e in SWEEP} == {"D", "S", "N", "A"}
