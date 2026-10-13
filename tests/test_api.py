"""The local API (Phase 4). No network, no database, no paid call: the connection is a stub."""

import pytest
from fastapi.testclient import TestClient

from cta.api import __main__ as api_main
from cta.api import app as api_app
from cta.api.checks import StartupError, startup_problems
from cta.index.db import migration_files
from cta.settings import ROOT, TRACING_VARIABLES, load_models

ENV = {"OPENAI_API_KEY": "sk-test"}
CFG = load_models(env={})  # router on, contacts on: the defaults


class FakeConn:
    """Answers SELECT 1 and the schema_migrations query; nothing else."""

    def __init__(self, applied):
        self.applied = applied

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, *args):
        return [(n,) for n in self.applied] if "schema_migrations" in sql else [(1,)]


def all_applied():
    return [p.name for p in migration_files()]


def ok_connect():
    return FakeConn(all_applied())


def down_connect():
    raise ConnectionError("password authentication failed for user cta at 10.0.0.5")


def make_app(**kw):
    return api_app.create_app(
        CFG, connect=kw.pop("connect", ok_connect), env=kw.pop("env", ENV), **kw
    )


# ---- /health ----


def test_health_is_ok_with_the_database_up():
    body = TestClient(make_app()).get("/health").json()
    assert body["status"] == "ok" and body["db"] == "ok" and body["router"] == "on"
    assert set(body) == {"status", "db", "version", "router"}  # nothing else is shown


def test_health_is_503_with_the_database_down_and_shows_no_driver_text():
    app = make_app(check_startup=False, connect=down_connect)
    r = TestClient(app).get("/health")
    assert r.status_code == 503 and r.json()["db"] == "down" and r.json()["status"] == "degraded"
    assert "password" not in r.text and "10.0.0.5" not in r.text


# ---- the startup guards ----


@pytest.mark.parametrize("name", TRACING_VARIABLES)
def test_the_app_refuses_to_start_with_any_tracing_variable_on(name):
    with pytest.raises(StartupError, match=name):
        make_app(env=ENV | {name: "true"})


def test_tracing_values_that_are_off_do_not_block_the_start():
    make_app(env=ENV | {"LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": ""})


@pytest.mark.parametrize("key", ["mode", "contacts"])
def test_router_and_contacts_must_be_on(key):
    cfg = load_models(env={})
    cfg["router"][key] = "off"
    with pytest.raises(StartupError, match=f"router.{key} must be on"):
        api_app.create_app(cfg, connect=ok_connect, env=ENV)


def test_a_missing_openai_key_is_refused_and_the_key_value_is_not_needed():
    with pytest.raises(StartupError, match="OPENAI_API_KEY is not set"):
        make_app(env={})


def test_missing_data_files_are_listed(tmp_path):
    problems = startup_problems(CFG, env=ENV, connect=ok_connect, root=tmp_path)
    assert any("config/contacts.yaml" in p for p in problems)
    assert any("calendar_events.json" in p for p in problems)
    assert any("data/processed/courses" in p for p in problems)


def test_database_down_gives_a_fixed_message_without_driver_text():
    problems = startup_problems(CFG, env=ENV, connect=down_connect)
    assert problems == [
        "database not reachable, or schema_migrations missing (run: docker compose up -d)"
    ]


def test_unapplied_migrations_are_named():
    problems = startup_problems(CFG, env=ENV, connect=lambda: FakeConn(all_applied()[:-1]))
    assert len(problems) == 1 and migration_files()[-1].name in problems[0]


def test_all_problems_are_reported_together():
    cfg = load_models(env={})
    cfg["router"]["mode"] = "off"
    with pytest.raises(StartupError) as e:
        api_app.create_app(cfg, connect=down_connect, env={"LANGSMITH_TRACING": "1"})
    for text in ("tracing is enabled", "router.mode", "OPENAI_API_KEY", "database not reachable"):
        assert text in str(e.value)


def test_a_good_setup_has_no_problems():
    assert startup_problems(CFG, env=ENV, connect=ok_connect) == []


def test_the_launcher_prints_the_problems_and_does_not_start_the_server(monkeypatch, capsys):
    started = []
    monkeypatch.setattr(api_main, "startup_problems", lambda cfg: ["nope"])
    monkeypatch.setattr(api_main.uvicorn, "run", lambda *a, **k: started.append((a, k)))
    assert api_main.main(["x"]) == 2 and not started
    assert "nope" in capsys.readouterr().out


def test_the_launcher_listens_on_localhost_only(monkeypatch):
    started = []
    monkeypatch.setattr(api_main, "startup_problems", lambda cfg: [])
    monkeypatch.setattr(api_main.uvicorn, "run", lambda *a, **k: started.append(k))
    assert api_main.main(["x", "--port", "8123"]) == 0
    assert started == [{"factory": True, "host": "127.0.0.1", "port": 8123}]


# ---- config ----


def test_api_config_defaults_and_the_date_override():
    assert CFG["api"] == {"today": None, "max_question_chars": 500, "max_body_bytes": 4096}
    assert str(load_models(env={"CTA_API_TODAY": "2026-10-11"})["api"]["today"]) == "2026-10-11"
    with pytest.raises(ValueError, match="api.today"):
        load_models(env={"CTA_API_TODAY": "yesterday"})


def test_env_example_lists_the_new_names():
    names = {
        ln.split("=")[0] for ln in (ROOT / ".env.example").read_text().splitlines() if "=" in ln
    }
    assert {"CTA_ROUTER_CONTACTS", "CTA_API_TODAY"} <= names
