"""Post-freeze safety sweep: every phrase of tests/crisis_sweep.py reaches the tier it should."""

import pytest

from cta.api import screen
from cta.settings import load_models
from tests.crisis_sweep import SWEEP

G = load_models(env={})["guardrails"]
TIER = {"D": "distress", "S": "stress", "X": "danger", "N": None, "L": None}


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


@pytest.mark.parametrize("question", phrases("X"))
def test_danger_from_someone_else_gets_its_own_reply(question):
    result = screen.screen(question, G)
    assert result.reason == "danger"
    assert screen.reply("danger", G) == screen.TEXTS["danger"]


@pytest.mark.parametrize("question", phrases("L"))
def test_phrases_the_owner_decided_to_leave_have_no_tier(question):
    assert screen.screen(question, G).reason is None


def test_the_danger_reply_is_the_owner_text_exactly():
    text = screen.TEXTS["danger"]
    assert text.startswith(
        "I'm really sorry this is happening to you. If you are in immediate danger, call 911 "
    )
    for number in ("(718) 260-5550", "5555", "1-800-799-7233", "88788", "1-800-621-4673"):
        assert number in text
    assert "988" not in text  # the 988 line belongs to Tier 1


def test_the_danger_reply_matches_the_public_safety_page_of_oct_19():
    text = screen.TEXTS["danger"]
    # the official page: Dispatcher 5555 on campus, 718-260-5555 otherwise; 9-911 on campus
    for fact in ("9-911", "718-260-5555", "dialing 5555 from any on-campus telephone"):
        assert fact in text
    # claims the page does not confirm
    assert "24 hours" not in text and "dial 5550" not in text


def test_the_sweep_has_the_expected_shape():
    assert len(SWEEP) >= 40
    assert {e for _, e in SWEEP} == {"D", "S", "N", "X", "L"}
