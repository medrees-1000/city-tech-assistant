"""Phase 4 step 7, Stage 1: kill switch, rate limit, daily spend cap, timeouts, /health counts.
Fake clients, fake clocks and fake counters only: no network, no database, no paid call."""

import hashlib
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import openai
import pytest

from cta.api import convert, guard, requestlog, schema
from cta.eval.questions import load_questions
from cta.index import embed
from cta.settings import ROOT, guardrail_settings, load_models
from tests.test_api import Client, ask, cfg_for, make_client_app, retrieve_answer

DEV = [q for q in load_questions() if q["split"] == "dev"]
DEFAULTS = load_models(env={})["guardrails"]


def settings(**over):
    return {**DEFAULTS, **over}


def req(host="1.2.3.4"):
    return SimpleNamespace(client=SimpleNamespace(host=host))


class SpendConn:
    """A connection whose only job is to answer the spend query with a fixed sum."""

    def __init__(self, total=0.0, fail=False):
        self.total, self.fail, self.queries = total, fail, []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        if self.fail:
            raise ConnectionError("boom")
        self.queries.append((sql, params))
        return SimpleNamespace(fetchone=lambda: (self.total,))


def cfg_guard(**over):
    cfg = cfg_for()
    cfg["guardrails"] = {**cfg["guardrails"], **over}
    return cfg


# ---- the settings and their environment overrides ----


def test_defaults_are_the_owner_decisions():
    assert DEFAULTS["daily_spend_cap_usd"] == 1.0 and DEFAULTS["disabled"] is False
    assert (DEFAULTS["rate_per_minute"], DEFAULTS["rate_per_day"]) == (10, 100)
    assert DEFAULTS["model_call_timeout_s"] == 15 and DEFAULTS["model_retries"] == 1
    assert DEFAULTS["request_timeout_s"] == 45


def test_environment_variables_override_and_bad_values_stop_the_start():
    env = {"CTA_DAILY_SPEND_CAP_USD": "0.05", "CTA_RATE_PER_MINUTE": "2", "CTA_RATE_PER_DAY": "7",
           "CTA_MODEL_CALL_TIMEOUT_S": "3", "CTA_MODEL_RETRIES": "0", "CTA_REQUEST_TIMEOUT_S": "9",
           "CTA_API_DISABLED": "1"}  # fmt: skip
    g = load_models(env=env)["guardrails"]
    assert (g["daily_spend_cap_usd"], g["rate_per_minute"], g["rate_per_day"]) == (0.05, 2, 7)
    assert (g["model_call_timeout_s"], g["model_retries"], g["request_timeout_s"]) == (3, 0, 9)
    assert g["disabled"] is True
    for bad in ({"CTA_DAILY_SPEND_CAP_USD": "0"}, {"CTA_RATE_PER_MINUTE": "x"},
                {"CTA_REQUEST_TIMEOUT_S": "-1"}):  # fmt: skip
        with pytest.raises(ValueError, match="guardrails"):
            guardrail_settings(DEFAULTS, bad)


# ---- 1. the kill switch ----


def test_the_config_flag_answers_the_fixed_reply_and_makes_no_model_call(monkeypatch):
    client = Client()
    c = make_client_app(client, monkeypatch, cfg=cfg_guard(disabled=True))
    body = ask(c).json()
    schema.AskResponse.model_validate(body)
    assert body["answer"] == guard.TEXTS["kill_switch"]
    assert body["answer_type"] == "guardrail" and body["route"] == "guardrail"
    assert body["how_found"]["route_detail"] == "kill_switch"
    assert client.calls == [] and body["citations"] == [] and body["contact"] is None
    assert c.logs[0]["status"] == "blocked_kill_switch" and c.logs[0]["route"] == "guardrail"
    assert c.get("/health").json()["disabled"] is True


def test_the_file_switches_it_off_and_removing_it_switches_it_on(monkeypatch, tmp_path):
    (tmp_path / "data").mkdir()
    flag = tmp_path / guard.DISABLED_FILE
    client = Client()
    c = make_client_app(client, monkeypatch, retrieve_answer(), tmp_root=tmp_path)
    flag.write_text("")
    assert ask(c).json()["how_found"]["route_detail"] == "kill_switch" and client.calls == []
    flag.unlink()
    assert ask(c).json()["answer_type"] != "guardrail"


def test_the_file_is_git_ignored():
    assert "data/api_disabled" in (ROOT / ".gitignore").read_text()


# ---- 2. the rate limit ----


def test_the_eleventh_request_in_a_minute_is_refused_for_one_visitor_only():
    g = guard.Guard(settings())
    assert [g.rate_limited("a") for _ in range(10)] == [False] * 10
    assert g.rate_limited("a") is True and g.rate_limited("b") is False


def test_the_window_slides_and_the_day_limit_holds():
    clock = [0.0]
    g = guard.Guard(settings(), monotonic=lambda: clock[0])
    for _ in range(10):
        g.rate_limited("a")
    assert g.rate_limited("a") is True
    clock[0] = 61
    assert g.rate_limited("a") is False  # the minute has passed
    day = guard.Guard(settings(rate_per_minute=1000, rate_per_day=100))
    assert [day.rate_limited("a") for _ in range(100)] == [False] * 100
    assert day.rate_limited("a") is True  # the 101st


def test_the_day_counter_resets_at_the_utc_midnight():
    now = [datetime(2026, 10, 15, 23, 59, 59, tzinfo=UTC)]
    g = guard.Guard(settings(rate_per_minute=1000, rate_per_day=2), now=lambda: now[0])
    assert (g.rate_limited("a"), g.rate_limited("a"), g.rate_limited("a")) == (False, False, True)
    now[0] += timedelta(seconds=1)
    assert g.rate_limited("a") is False


def test_the_visitor_table_is_bounded_and_a_restart_is_empty():
    g = guard.Guard(settings(rate_limit_max_keys=50))
    for i in range(200):
        g.rate_limited(f"k{i}")
    assert len(g.visitors) == 50
    assert len(guard.Guard(settings()).visitors) == 0 and guard.Guard(settings()).salt != g.salt


def test_a_rate_limited_request_makes_no_model_call(monkeypatch):
    client = Client()
    c = make_client_app(client, monkeypatch, retrieve_answer(), cfg=cfg_guard(rate_per_minute=2))
    assert [ask(c).json()["answer_type"] for _ in range(2)] == ["answer", "answer"]
    calls = len(client.calls)
    body = ask(c).json()
    assert body["answer"] == guard.TEXTS["rate_limited"] and len(client.calls) == calls
    assert c.logs[-1]["status"] == "blocked_rate_limited"


def test_the_address_and_its_hash_are_nowhere_in_the_rows_the_logs_or_health(monkeypatch, caplog):
    c = make_client_app(Client(), monkeypatch, retrieve_answer(), cfg=cfg_guard(rate_per_minute=1))
    with caplog.at_level(logging.DEBUG):
        ask(c)
        ask(c)  # the second is rate limited
    g = c.app.state.guard
    digest = hashlib.sha256(g.salt + b"testclient").hexdigest()
    everything = json.dumps(c.logs, default=str) + caplog.text + json.dumps(c.get("/health").json())
    assert "testclient" not in everything
    assert digest not in everything and digest[:12] not in everything
    assert "testclient" not in json.dumps(g.health(lambda: SpendConn()), default=str)


def test_stage1_never_reads_the_question_text():
    import inspect

    assert list(inspect.signature(guard.Guard.stage1).parameters) == ["self", "request", "connect"]


# ---- 3. the daily spend cap ----


def test_just_under_the_cap_is_served_and_at_the_cap_is_refused():
    g = guard.Guard(settings(daily_spend_cap_usd=1.0, spend_cache_s=0))
    assert g.over_cap(lambda: SpendConn(0.999)) is False
    assert g.over_cap(lambda: SpendConn(1.0)) is True and g.over_cap(lambda: SpendConn(2.5)) is True


def test_the_cap_refuses_without_any_model_call(monkeypatch):
    client = Client()
    c = make_client_app(client, monkeypatch, cfg=cfg_guard(daily_spend_cap_usd=0.5),
                        connect=lambda: SpendConn(0.5))  # fmt: skip
    body = ask(c).json()
    assert body["answer"] == guard.TEXTS["daily_cap"] and client.calls == []
    health = c.get("/health").json()
    assert health["spend_cap_reached"] is True and health["blocked"]["daily_cap"] == 1


def test_the_query_counts_api_rows_since_utc_midnight_and_estimates_failures():
    now = datetime(2026, 10, 15, 13, 5, tzinfo=UTC)
    conn = SpendConn(0.1)
    g = guard.Guard(settings(failed_request_cost_usd=0.002), now=lambda: now)
    assert g.spend_today(conn) == 0.1
    sql, params = conn.queries[0]
    assert "source = 'api'" in sql and "source = 'eval'" not in sql
    assert params[0] == list(guard.FAILED_STATUSES) and params[1] == 0.002
    assert params[2] == datetime(2026, 10, 15, 0, 0, tzinfo=UTC)  # the UTC day starts at 00:00
    assert set(guard.FAILED_STATUSES) == {"provider_error", "internal_error", "timeout"}


def test_the_day_boundary_is_utc():
    before = datetime(2026, 10, 15, 23, 59, 59, tzinfo=UTC)
    assert guard.day_start(before) == datetime(2026, 10, 15, tzinfo=UTC)
    assert guard.day_start(before + timedelta(seconds=1)) == datetime(2026, 10, 16, tzinfo=UTC)


def test_the_sum_is_cached_so_a_burst_makes_one_query():
    clock = [0.0]
    conn = SpendConn(0.2)
    g = guard.Guard(settings(spend_cache_s=10), monotonic=lambda: clock[0])
    for _ in range(5):
        g.over_cap(lambda: conn)
    assert len(conn.queries) == 1
    clock[0] = 11
    g.over_cap(lambda: conn)
    assert len(conn.queries) == 2


def test_a_failed_counter_allows_the_request_and_is_counted(monkeypatch):
    client = Client()
    c = make_client_app(
        client, monkeypatch, retrieve_answer(), connect=lambda: SpendConn(fail=True)
    )
    body = ask(c).json()
    assert body["answer_type"] == "answer" and client.calls  # served
    assert c.get("/health").json()["spend_check_failures"] >= 1


def test_the_topic_call_cost_is_inside_the_logged_cost():
    # success_record stores hf.cost_usd["total"], which topic.rewrite adds the topic call to
    import inspect

    from cta.api import topic

    assert 'hf.cost_usd["total"] = hf.cost_usd["total"] + call.cost' in inspect.getsource(topic)
    assert '"cost_usd": hf.cost_usd["total"]' in inspect.getsource(requestlog.success_record)


# ---- 4. the timeouts ----


def test_the_api_client_has_a_timeout_and_the_default_client_has_none(monkeypatch):
    seen = []
    monkeypatch.setattr(openai, "OpenAI", lambda **kw: seen.append(kw))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    embed.make_client()
    embed.make_client(timeout=15)
    assert seen == [{"max_retries": 0}, {"max_retries": 0, "timeout": 15}]


def failing_call(counter):
    def call():
        counter.append(1)
        raise openai.APIConnectionError(request=httpx.Request("POST", "http://x"))

    return call


def test_eval_keeps_three_retries_and_the_api_retries_once():
    n = []
    with pytest.raises(embed.ApiError, match="after 3 retries"):
        embed.with_retries(failing_call(n), "x", sleep=lambda s: None)
    assert len(n) == 4 and embed.MAX_RETRIES == 3 and embed.retry_limit.get() == 3
    n.clear()
    token = embed.retry_limit.set(1)
    try:
        with pytest.raises(embed.ApiError, match="after 1 retries"):
            embed.with_retries(failing_call(n), "x", sleep=lambda s: None)
    finally:
        embed.retry_limit.reset(token)
    assert len(n) == 2


def test_the_api_sets_its_retry_limit_inside_the_request(monkeypatch):
    seen = []

    class Spy(Client):
        def create(self, **kw):
            seen.append(embed.retry_limit.get())
            return super().create(**kw)

    c = make_client_app(Spy(), monkeypatch, retrieve_answer())
    ask(c)
    assert seen and set(seen) == {1} and embed.retry_limit.get() == 3  # the API's request only


class Slow(Client):
    def create(self, **kw):
        time.sleep(0.4)
        return super().create(**kw)


def test_a_request_over_the_limit_gets_the_timeout_reply_and_one_row(monkeypatch):
    c = make_client_app(Slow(), monkeypatch, cfg=cfg_guard(request_timeout_s=0.1))
    started = time.perf_counter()
    body = ask(c).json()
    assert time.perf_counter() - started < 0.35
    assert body["answer"] == guard.TEXTS["timeout"] and body["answer_type"] == "guardrail"
    time.sleep(0.9)  # the abandoned worker finishes now and must not write a second row
    assert [r["status"] for r in c.logs] == ["timeout"]
    assert c.logs[0]["cost_usd"] is None  # counted by the failed-request estimate
    assert c.get("/health").json()["blocked"]["timeout"] == 1


# ---- 5. contract, page, logs ----


def test_the_guardrail_response_validates_and_holds_no_student_text():
    cfg = cfg_for()
    resp = convert.guardrail_response("daily_cap", guard.TEXTS["daily_cap"], "q?", cfg,
                                      datetime(2026, 10, 15).date(), "rid", "v", 12.0)  # fmt: skip
    schema.AskResponse.model_validate(resp.model_dump())
    row = requestlog.blocked_record(resp, "daily_cap")
    assert row["status"] == "blocked_daily_cap" and row["route"] == "guardrail"
    assert row["cost_usd"] == 0.0 and row["trace"]["answer_type"] == "guardrail"
    assert set(row) == set(requestlog.COLUMNS) - {"source"}


def test_a_text_blocked_row_keeps_only_the_length():
    cfg = cfg_for()
    resp = convert.guardrail_response("x", "fixed", "", cfg, datetime(2026, 10, 15).date(),
                                      "rid", "v", 1.0)  # fmt: skip
    row = requestlog.blocked_record(resp, "x", text_blocked=True, chars=42)
    assert row["question"] == "" and row["trace"]["chars"] == 42


# ---- 6. /health ----


def test_health_has_exactly_the_new_keys_and_no_text(monkeypatch):
    c = make_client_app(Client(), monkeypatch, cfg=cfg_guard(disabled=True))
    ask(c)
    body = c.get("/health").json()
    assert body["blocked"] == {"kill_switch": 1, "rate_limited": 0, "daily_cap": 0, "timeout": 0}
    assert {"disabled", "spend_today_usd", "spend_cap_usd", "spend_cap_reached",
            "spend_check_failures", "blocked"} <= set(body)  # fmt: skip
    strings = {k: v for k, v in body.items() if isinstance(v, str)}
    assert set(strings) == {"status", "db", "version", "router"}


def test_the_logs_reader_accepts_the_guardrail_route():
    from cta.api import logs

    assert "guardrail" in logs.ROUTES


# ---- 7. false positives over the dev questions ----


@pytest.mark.parametrize("question", [q["question"] for q in DEV])
def test_no_dev_question_is_blocked_by_a_stage_1_guard(question):
    g = guard.Guard(settings(), root=ROOT / "tests" / "no_such_dir")  # a fresh state per question
    assert g.stage1(req(), lambda: SpendConn(0.0)) is None  # none of these guards read the text


# ---- 8. the eval and the pipeline do not use any of it ----


def test_no_pipeline_or_eval_module_imports_the_guard():
    import re

    for rel in ("graph", "eval", "index", "parse", "crawl", "validate"):
        for path in (ROOT / "src" / "cta" / rel).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert not re.search(r"^\s*(from|import) cta\.api", text, re.M), path
