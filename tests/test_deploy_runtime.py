"""What the production container relies on at run time: New York dates, the baked commit, the
health body, the kill switch text and the listen address. No network, no database."""

import json
from datetime import UTC, date, datetime

from cta.api import __main__ as api_main
from cta.api import app as api_app
from cta.api import guard, screen
from tests.test_api import Client, ask, make_client_app, retrieve_answer
from tests.test_guard import cfg_guard


def utc(*args):
    return lambda: datetime(*args, tzinfo=UTC)


# ---- "today" is New York's today ----


def test_late_evening_in_new_york_is_still_that_day_although_utc_has_moved_on():
    # 22:30 on Oct 18 in New York (EDT, UTC-4) is 02:30 on Oct 19 in UTC
    assert api_app.today_new_york(utc(2026, 10, 19, 2, 30)) == date(2026, 10, 18)
    assert api_app.today_new_york(utc(2026, 10, 19, 3, 59)) == date(2026, 10, 18)
    assert api_app.today_new_york(utc(2026, 10, 19, 4, 0)) == date(2026, 10, 19)  # midnight EDT


def test_the_date_follows_the_winter_offset_after_daylight_saving_ends():
    # EST (UTC-5) from Nov 1, 2026: 04:30 UTC on Nov 2 is 23:30 on Nov 1 in New York
    assert api_app.today_new_york(utc(2026, 11, 2, 4, 30)) == date(2026, 11, 1)
    assert api_app.today_new_york(utc(2026, 11, 2, 5, 0)) == date(2026, 11, 2)


def test_the_year_end_in_new_york_is_not_the_new_year_in_utc():
    assert api_app.today_new_york(utc(2027, 1, 1, 3, 0)) == date(2026, 12, 31)


def test_the_default_clock_of_create_app_is_the_new_york_one():
    import inspect

    default = inspect.signature(api_app.create_app).parameters["clock"].default
    assert default is api_app.today_new_york


# ---- the commit and the health body ----


def test_the_commit_baked_into_the_image_wins_over_git(monkeypatch):
    monkeypatch.setenv("CTA_COMMIT", "abc1234def5678901")
    assert api_app.git_version() == "abc1234def56"
    monkeypatch.delenv("CTA_COMMIT")
    assert api_app.git_version()  # git, or "unknown" in an image without it


def test_health_shows_commit_config_version_and_key_settings_but_no_secret(monkeypatch):
    monkeypatch.setenv("CTA_COMMIT", "abc1234")
    secrets = {"CTA_PROXY_SECRET": "p" * 32, "CTA_IP_SALT": "q" * 32,
               "OPENAI_API_KEY": "sk-secret-value-123456"}  # fmt: skip
    c = make_client_app(Client(), monkeypatch, retrieve_answer(), env=secrets,
                        headers={"x-cta-proxy-secret": "p" * 32})  # fmt: skip
    body = c.get("/health").json()
    assert body["version"] == "abc1234" and len(body["config_version"]) == 10
    s = body["settings"]
    assert s["chat_model"] == "gpt-6-luna" and s["embedding_model"] == "text-embedding-3-small"
    assert s["rescue"] == "on" and s["tracing"] is False and s["today_zone"] == "America/New_York"
    assert {"spend_cap_usd", "monthly_cap_usd"} <= set(body)
    text = json.dumps(body)
    for value in (*secrets.values(), "LANGSMITH", "postgresql://"):
        assert value not in text
    assert "question" not in text.lower()


# ---- the kill switch and the listen address ----


def test_the_kill_switch_says_temporarily_paused_and_makes_no_model_call(monkeypatch, tmp_path):
    client = Client()
    c = make_client_app(client, monkeypatch, retrieve_answer(), cfg=cfg_guard())
    (tmp_path / "data").mkdir()
    c.app.state.guard.root = tmp_path
    assert ask(c).json()["answer_type"] == "answer"
    (tmp_path / "data" / "api_disabled").write_text("")  # the file kill switch, no restart
    calls = len(client.calls)
    body = ask(c).json()
    paused = "The assistant is temporarily paused. Please check back later."
    assert body["answer"].startswith(paused) and body["answer"].endswith(screen.CRISIS_LINE)
    assert body["answer"] == guard.TEXTS["kill_switch"] and len(client.calls) == calls
    (tmp_path / "data" / "api_disabled").unlink()
    assert ask(c).json()["answer_type"] == "answer"


def test_the_listen_address_is_local_unless_the_container_sets_it(monkeypatch):
    import importlib

    monkeypatch.delenv("CTA_API_HOST", raising=False)
    assert importlib.reload(api_main).HOST == "127.0.0.1"
    monkeypatch.setenv("CTA_API_HOST", "0.0.0.0")  # noqa: S104 - the container's own setting
    assert importlib.reload(api_main).HOST == "0.0.0.0"  # noqa: S104
    monkeypatch.delenv("CTA_API_HOST")
    importlib.reload(api_main)
    source = open(api_main.__file__, encoding="utf-8").read()
    assert "access_log=False" in source and "proxy_headers=False" in source
