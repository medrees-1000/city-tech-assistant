"""Tester round 2, item B (T13): input hygiene and the cost of unlogged requests."""

from datetime import UTC, datetime

import pytest

from cta.api import guard, hygiene
from tests.helpers import (
    Client,
    SpendConn,
    ask,
    cfg_guard,
    make_client_app,
    retrieve_answer,
    settings,
)

CLEAN = "when is add/drop dl"
WEIRD = [
    ("nul", "when is\x00 add/drop dl"),
    ("c0 and c1", "when\x01 is\x1f add/drop\x85 dl\x7f"),
    ("bidi", "‮when is‬ add/drop⁦ dl⁩"),
    ("zero width", "when​ is‌ add/drop‍ dl⁠﻿"),
    ("soft hyphen", "when is add/dr­op dl"),
    ("spaces", "  when   is\t\t add/drop\n\n dl \r\n"),
    ("mixed", "\x00wh‮en​   is\x07 add/﻿drop ­dl\x00"),
]


@pytest.mark.parametrize(("name", "text"), WEIRD)
def test_hidden_characters_are_removed_and_whitespace_collapsed(name, text):
    assert hygiene.normalize(text) == CLEAN


@pytest.mark.parametrize(("name", "text"), WEIRD)
def test_normalizing_twice_changes_nothing(name, text):
    once = hygiene.normalize(text)
    assert hygiene.normalize(once) == once


def test_ordinary_text_and_accents_are_untouched():
    assert hygiene.normalize("¿Cuándo es la fecha límite?") == "¿Cuándo es la fecha límite?"
    assert hygiene.normalize("a\tb") == "a b"


@pytest.mark.parametrize(("name", "text"), WEIRD)
def test_a_weird_question_logs_and_answers_like_the_clean_one(monkeypatch, name, text):
    c = make_client_app(Client(), monkeypatch, retrieve_answer())
    clean = ask(c, CLEAN).json()
    weird = ask(c, text).json()
    assert weird["answer"] == clean["answer"] and weird["question"] == CLEAN
    assert [r["question"] for r in c.logs] == [CLEAN, CLEAN]
    assert c.get("/health").json()["log_failures"] == 0


def test_a_question_that_is_empty_after_normalizing_is_rejected_like_an_empty_one(monkeypatch):
    client = Client()
    c = make_client_app(client, monkeypatch, retrieve_answer())
    plain = c.post("/ask", json={"question": "   "})
    hidden = c.post("/ask", json={"question": "\x00​‮ ﻿"})
    assert hidden.status_code == plain.status_code == 422
    assert hidden.json()["error"] == plain.json()["error"] and client.calls == []
    assert c.logs[1]["status"] == "invalid_question" and c.logs[1]["question"] == ""


def test_screens_run_on_the_normalized_text(monkeypatch):
    c = make_client_app(Client(), monkeypatch, retrieve_answer())
    body = ask(c, "i dont want to​ be al\x00ive anymore").json()
    assert body["how_found"]["route_detail"] == "distress"


# ---- a log write that fails still counts for the daily cap ----


def test_a_failed_log_write_adds_its_cost_and_the_cap_then_trips(monkeypatch):
    def broken(conn, record):
        raise RuntimeError("insert failed")

    client = Client()
    c = make_client_app(client, monkeypatch, retrieve_answer(), log_writer=broken,
                        cfg=cfg_guard(daily_spend_cap_usd=0.0001, spend_cache_s=0),
                        connect=lambda: SpendConn(0.0))  # fmt: skip
    first = ask(c).json()
    cost = first["how_found"]["cost_usd"]["total"]
    assert cost > 0.0001 or pytest.skip("the scripted request costs too little for this cap")
    health = c.get("/health").json()
    assert health["log_failures"] == 1
    assert health["spend_today_usd"] == pytest.approx(cost, abs=1e-6)
    again = ask(c).json()
    assert again["answer"] == guard.TEXTS["daily_cap"]


def test_the_counter_adds_to_the_database_sum_resets_each_day_and_fails_open():
    now = [datetime(2026, 10, 15, 23, 0, tzinfo=UTC)]
    g = guard.Guard(settings(daily_spend_cap_usd=1.0, spend_cache_s=0), now=lambda: now[0])
    g.add_unlogged({"cost_usd": 0.6, "status": "ok"})
    assert g.over_cap(lambda: SpendConn(0.3)) is False
    assert g.over_cap(lambda: SpendConn(0.4)) is True  # 0.4 + 0.6
    g.add_unlogged({"cost_usd": None, "status": "provider_error"})  # the flat estimate
    assert g.unlogged_today() > 0.6
    now[0] = datetime(2026, 10, 16, 0, 1, tzinfo=UTC)
    assert g.unlogged_today() == 0.0 and g.over_cap(lambda: SpendConn(0.3)) is False

    def failing():
        raise RuntimeError("db down")

    g.add_unlogged({"cost_usd": 5.0, "status": "ok"})
    assert g.over_cap(failing) is False  # a read error still fails open
