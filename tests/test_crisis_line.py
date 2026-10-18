"""One crisis sentence ends every fixed "paused" reply: kill switch, daily cap, monthly cap. It is
built from the same two numbers as the distress reply, so the launch-day re-check covers it."""

import re

from cta.api import guard, screen
from cta.settings import ROOT
from tests.test_api import Client, ask, make_client_app, retrieve_answer
from tests.test_guard import SpendConn, cfg_guard

LINE = screen.CRISIS_LINE


def test_the_line_names_988_and_911_and_is_built_from_the_screens_numbers():
    assert "call or text 988" in LINE and "call 911" in LINE
    assert (screen.LIFELINE, screen.EMERGENCY) == ("988", "911")
    assert set(re.findall(r"\d{3}", LINE)) == {"988", "911"}
    for number in (screen.LIFELINE, screen.EMERGENCY):  # the distress reply uses the same two
        assert number in screen.TEXTS["distress"]
    assert "Social" not in LINE and "{" not in LINE


def test_each_paused_text_ends_with_the_line():
    for text in (guard.TEXTS["kill_switch"], guard.TEXTS["daily_cap"], guard.paused_text()):
        assert text.endswith(LINE), text
    assert guard.TEXTS["kill_switch"].startswith("The assistant is temporarily paused.")
    assert guard.TEXTS["daily_cap"].startswith("The assistant has reached its limit for today.")
    assert guard.paused_text().startswith("The assistant is paused for the rest of this month")
    assert "registrar@citytech.cuny.edu" in guard.paused_text()  # the contacts are still there


def test_the_other_fixed_replies_are_unchanged():
    rate = "You're asking quickly. Please wait a moment and try again."
    assert guard.TEXTS["rate_limited"] == rate
    assert "988" not in guard.TEXTS["timeout"]


def test_the_replies_the_api_returns_carry_the_line_and_no_student_text(monkeypatch):
    marker = "zebra-marker-77"
    for tweak, reason in (
        ({"disabled": True}, "kill_switch"),
        ({"daily_spend_cap_usd": 1.0}, "daily_cap"),
        ({"monthly_spend_cap_usd": 1.0, "daily_spend_cap_usd": 1000}, "monthly_cap"),
    ):
        cfg = cfg_guard(**tweak)
        c = make_client_app(Client(), monkeypatch, retrieve_answer(), cfg=cfg,
                            connect=lambda: SpendConn(50.0))  # fmt: skip
        body = ask(c, f"when is the last day to drop {marker}").json()
        assert body["how_found"]["route_detail"] == reason
        assert body["answer"].endswith(LINE) and marker not in body["answer"]


def test_the_page_copy_of_the_line_is_the_same_sentence():
    ts = (ROOT / "web" / "lib" / "errors.ts").read_text(encoding="utf-8")
    assert LINE in ts
    for code in ("kill_switch", "daily_cap", "monthly_cap"):
        assert re.search(rf"{code}: `[^`]*\$\{{CRISIS_LINE\}}`", ts), code


def test_the_distress_reply_text_did_not_change():
    assert screen.TEXTS["distress"] == (
        "I'm really sorry you're going through this. I can't help with this, but you don't have "
        "to face it alone. In the United States, you can call or text 988 (the 988 Suicide & "
        "Crisis Lifeline) at any time, day or night. If you or someone else is in immediate "
        "danger, call 911. Talking with someone you trust can help too."
    )
