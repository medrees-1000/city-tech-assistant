"""Feedback votes and the logs inspection (step: thumbs up/down). Scripted client and a throwaway
schema; no paid call."""

from contextlib import nullcontext
from datetime import date

import pytest
from fastapi.testclient import TestClient

from cta.api import app as api_app
from cta.api import logs, purge, requestlog
from cta.index.db import migration_files
from tests.test_api import (
    EVENTS,
    TODAY,
    Client,
    ask,
    cfg_for,
    make_client_app,
    retrieve_answer,
)
from tests.test_chain import WORLD
from tests.test_requestlog import insert

UNKNOWN = "7f0f3a4e00004000800000000000ffff"


def vote(client, request_id, value, **extra):
    return client.post("/feedback", json={"request_id": request_id, "vote": value, **extra})


def answered(monkeypatch, **kw):
    c = make_client_app(Client(), monkeypatch, retrieve_answer(), **kw)
    return c, ask(c).json()["request_id"]


# ---- the endpoint ----


def test_vote_up_down_and_change_the_latest_vote_wins(monkeypatch):
    c, rid = answered(monkeypatch)
    r = vote(c, rid, "up")
    assert r.status_code == 200 and r.json() == {"request_id": rid, "vote": "up"}
    assert c.votes == {rid: "up"}
    assert vote(c, rid, "down").json() == {"request_id": rid, "vote": "down"}
    assert c.votes == {rid: "down"}  # a person may change their mind
    assert vote(c, rid, "down").status_code == 200  # the same vote again is harmless


def test_the_request_id_may_be_written_with_dashes_and_the_reply_uses_the_api_form(monkeypatch):
    c, rid = answered(monkeypatch)
    dashed = f"{rid[:8]}-{rid[8:12]}-{rid[12:16]}-{rid[16:20]}-{rid[20:]}"
    assert vote(c, dashed, "up").json()["request_id"] == rid


def test_an_unknown_id_and_something_that_is_not_an_id_are_404_in_the_standard_envelope(
    monkeypatch,
):
    c, rid = answered(monkeypatch)
    for bad in (UNKNOWN, "not-a-uuid", "", "1234"):
        r = vote(c, bad, "up")
        body = r.json()
        assert r.status_code == 404 and body["error"]["code"] == "not_found"
        assert body["request_id"] == r.headers["X-Request-ID"]
    assert c.votes == {}


@pytest.mark.parametrize("value", ["sideways", "UP", "Up", "", None, 1, True, ["up"]])
def test_only_up_or_down_is_accepted(monkeypatch, value):
    c, rid = answered(monkeypatch)
    r = vote(c, rid, value)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"
    assert c.votes == {}


@pytest.mark.parametrize("extra", [{"comment": "wrong date"}, {"text": "x"}, {"reason": "y"}])
def test_free_text_and_any_extra_field_are_rejected(monkeypatch, extra):
    c, rid = answered(monkeypatch)
    r = vote(c, rid, "down", **extra)
    assert r.status_code == 422 and c.votes == {}
    assert "wrong date" not in r.text  # nothing the client sent is echoed back


def test_a_missing_field_or_a_non_object_is_422(monkeypatch):
    c, rid = answered(monkeypatch)
    assert c.post("/feedback", json={"request_id": rid}).status_code == 422
    assert c.post("/feedback", json={"vote": "up"}).status_code == 422
    assert c.post("/feedback", json=["up"]).status_code == 422
    assert (
        c.post(
            "/feedback", content=b"nope", headers={"content-type": "application/json"}
        ).status_code
        == 422
    )


def test_an_oversized_body_is_413(monkeypatch):
    c, rid = answered(monkeypatch)
    r = vote(c, rid, "up", comment="x" * 5000)
    assert r.status_code == 413 and r.json()["error"]["code"] == "too_large"
    assert c.votes == {}


def test_a_failed_vote_write_is_503_counted_in_health_and_shows_nothing_inside(monkeypatch):
    def broken(conn, request_id, value):
        raise RuntimeError("update failed for password=secret host=10.0.0.5")

    c, rid = answered(monkeypatch, feedback_writer=broken)
    r = vote(c, rid, "up")
    assert r.status_code == 503 and r.json()["error"]["code"] == "unavailable"
    assert "secret" not in r.text and "10.0.0.5" not in r.text
    assert c.get("/health").json()["feedback_failures"] == 1
    assert c.get("/health").json()["log_failures"] == 0  # a separate counter
    vote(c, rid, "down")
    assert c.get("/health").json()["feedback_failures"] == 2


def test_the_vote_endpoint_does_not_log_a_request_row_or_call_the_model(monkeypatch):
    client = Client()
    c = make_client_app(client, monkeypatch, retrieve_answer())
    rid = ask(c).json()["request_id"]
    calls, rows = list(client.calls), len(c.logs)
    vote(c, rid, "up")
    assert client.calls == calls and len(c.logs) == rows


# ---- the migration and the real writer, in a throwaway schema ----


@pytest.mark.integration
def test_migration_006_adds_the_columns_a_check_and_a_partial_index_and_can_run_again(conn):
    cols = {r[0] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'request_logs' AND table_schema = current_schema()")}  # fmt: skip
    assert {"feedback", "feedback_at"} <= cols
    migration = next(p for p in migration_files() if p.name.startswith("006"))
    conn.execute(migration.read_text(encoding="utf-8"))
    conn.commit()
    index = conn.execute(
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'request_logs_feedback_idx' "
        "AND schemaname = current_schema()"
    ).fetchone()[0]
    assert "WHERE (feedback IS NOT NULL)" in index
    with pytest.raises(Exception, match="feedback_check|violates check"):
        conn.execute("INSERT INTO request_logs (question, feedback) VALUES ('q', 'maybe')")
    conn.rollback()


def api_row(conn, rid, source="api", **extra):
    record = {**requestlog.error_record(rid, "ok", "q", date(2026, 10, 13), "m", 5.0), **extra}
    if source == "api":
        requestlog.write(conn, record)
    else:  # an eval-style row that happens to carry a request id
        conn.execute(
            "INSERT INTO request_logs (source, question, request_id) VALUES ('eval', 'q', %s)",
            (rid,),
        )
        conn.commit()


@pytest.mark.integration
def test_write_feedback_changes_only_the_two_columns_and_the_latest_vote_wins(conn):
    rid = "7f0f3a4e00004000800000000000a001"
    api_row(conn, rid, answer="the answer", cost_usd=0.001)
    columns = "request_id, source, status, question, answer, cost_usd, route, trace, ts"
    before = conn.execute(f"SELECT {columns} FROM request_logs").fetchone()
    assert conn.execute("SELECT feedback, feedback_at FROM request_logs").fetchone() == (None, None)
    assert requestlog.write_feedback(conn, rid, "up") is True
    up_at = conn.execute("SELECT feedback_at FROM request_logs").fetchone()[0]
    assert requestlog.write_feedback(conn, rid, "down") is True
    vote, down_at = conn.execute("SELECT feedback, feedback_at FROM request_logs").fetchone()
    assert vote == "down" and down_at >= up_at
    assert (
        conn.execute(f"SELECT {columns} FROM request_logs").fetchone() == before
    )  # nothing else moved
    assert conn.execute("SELECT count(*) FROM request_logs").fetchone()[0] == 1


@pytest.mark.integration
def test_an_unknown_id_and_an_eval_row_can_never_be_voted_on(conn):
    api_row(conn, "7f0f3a4e00004000800000000000a002", source="eval")
    assert requestlog.write_feedback(conn, "7f0f3a4e00004000800000000000a002", "up") is False
    assert requestlog.write_feedback(conn, UNKNOWN, "down") is False
    assert (
        conn.execute("SELECT count(*) FROM request_logs WHERE feedback IS NOT NULL").fetchone()[0]
        == 0
    )


@pytest.mark.integration
def test_vote_end_to_end_through_the_api_into_the_database(conn):
    client = Client()
    from cta.graph import build
    from cta.graph.build import Router

    def factory(c, cfg):
        return Router(c, cfg, lambda: client, events=EVENTS, contact="r@x.edu")

    app = api_app.create_app(
        cfg_for(), connect=lambda: nullcontext(conn), check_startup=False, router_factory=factory,
        clock=lambda: TODAY, client_factory=lambda: client,
    )  # fmt: skip
    web = TestClient(app, raise_server_exceptions=False)
    import cta.graph.chain as chains

    chains.load_records = lambda *a, **k: WORLD  # the chain walk is not used here
    build.answer = lambda *a, **k: retrieve_answer()
    rid = web.post("/ask", json={"question": "How do I apply?"}).json()["request_id"]
    assert web.post("/feedback", json={"request_id": rid, "vote": "down"}).json()["vote"] == "down"
    assert conn.execute(
        "SELECT feedback, source FROM request_logs WHERE request_id = %s", (rid,)
    ).fetchone() == ("down", "api")


# ---- purge takes votes with their rows ----


@pytest.mark.integration
def test_purge_removes_old_votes_with_their_rows_and_keeps_recent_ones(conn):
    insert(conn, "api", 40, "7f0f3a4e00004000800000000000b001")
    insert(conn, "api", 3, "7f0f3a4e00004000800000000000b002")
    conn.execute("UPDATE request_logs SET feedback = 'down', feedback_at = ts")
    conn.commit()
    assert purge.purge(conn, 30) == 1
    left = conn.execute("SELECT request_id, feedback FROM request_logs").fetchall()
    assert [(r[0].hex, r[1]) for r in left] == [("7f0f3a4e00004000800000000000b002", "down")]
    tables = {
        r[0]
        for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()")
    }
    assert not {t for t in tables if "feedback" in t or "vote" in t}  # no second table to clean up


# ---- the logs command: vote column, filter, footer, --id ----


def seed(conn):
    api_row(conn, "7f0f3a4e00004000800000000000c001", question_note=None) if False else None
    for n, (q, v) in enumerate(
        [("good one", "up"), ("bad one", "down"), ("no vote", None), ("another bad", "down")]
    ):
        rid = f"7f0f3a4e00004000800000000000c10{n}"
        requestlog.write(
            conn,
            {
                **requestlog.error_record(rid, "ok", q, date(2026, 10, 13), "m", 5.0),
                "route": "retrieve",
                "cost_usd": 0.001,
            },
        )
        if v:
            requestlog.write_feedback(conn, rid, v)


@pytest.mark.integration
def test_logs_shows_the_vote_filters_by_it_and_counts_votes_in_the_footer(
    conn, monkeypatch, capsys
):
    seed(conn)
    monkeypatch.setattr(logs, "connect", lambda: nullcontext(conn))
    assert logs.main(["x", "--last", "10"]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert sum("vote=down" in ln for ln in out) == 2 and sum("vote=up" in ln for ln in out) == 1
    assert sum("vote=-" in ln for ln in out) == 1
    assert out[-1].endswith("votes: 1 up, 2 down, 1 no vote") and out[-1].startswith(
        "4 API requests, "
    )
    assert logs.main(["x", "--feedback", "down"]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 3 and all("vote=down" in ln for ln in out[:-1])
    assert out[-1].startswith("2 API requests matching") and out[-1].endswith(
        "votes: 0 up, 2 down, 0 no vote"
    )
    assert logs.main(["x", "--feedback", "any"]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1].startswith("3 API requests matching")
    assert logs.main(["x", "--feedback", "up"]) == 0
    assert "good one" in capsys.readouterr().out


@pytest.mark.integration
def test_logs_id_prints_the_whole_row_redacted_again(conn, monkeypatch, capsys):
    rid = "7f0f3a4e00004000800000000000d001"
    base = requestlog.error_record(rid, "ok", "q", date(2026, 10, 13), "gpt-6-luna", 12.0)
    trace = {"answer_type": "abstain", "stages_ms": {"total": 12.0}}
    requestlog.write(conn, {
        **base, "route": "retrieve", "answer": "the answer", "abstained": True,
        "abstain_reason": "below_threshold", "contact_office": "registrar", "trace": trace,
    })  # fmt: skip
    # unredacted text planted by hand (it could only come from outside the API): never printed
    planted = '{"note": "id 23456789", "answer_type": "abstain"}'
    conn.execute(
        "UPDATE request_logs SET question = 'mail jane@x.edu', answer = 'call 718-260-5800', "
        "trace = %s::jsonb WHERE request_id = %s",
        (planted, rid),
    )
    requestlog.write_feedback(conn, rid, "down")
    monkeypatch.setattr(logs, "connect", lambda: nullcontext(conn))
    assert logs.main(["x", "--id", rid]) == 0
    text = capsys.readouterr().out
    for secret in ("jane@x.edu", "718-260-5800", "23456789"):
        assert secret not in text
    expected = [
        "question: mail [EMAIL]", "answer: call [PHONE]", "[ID]", "route: retrieve",
        "abstain_reason: below_threshold", "contact_office: registrar", "feedback: down",
        "feedback_at:", "status: ok", "latency_ms: 12", "chat_model: gpt-6-luna", "source: api",
        f"request_id: {rid}",
    ]  # fmt: skip
    for item in expected:
        assert item in text
    assert '"answer_type": "abstain"' in text and "trace:\n" in text  # pretty-printed JSON
    dashed = f"{rid[:8]}-{rid[8:12]}-{rid[12:16]}-{rid[16:20]}-{rid[20:]}"
    assert logs.main(["x", "--id", dashed]) == 0


@pytest.mark.integration
def test_logs_id_for_an_unknown_id_an_eval_row_or_garbage_prints_nothing_stored(
    conn, monkeypatch, capsys
):
    api_row(conn, "7f0f3a4e00004000800000000000d002", source="eval")
    monkeypatch.setattr(logs, "connect", lambda: nullcontext(conn))
    for bad in (UNKNOWN, "7f0f3a4e00004000800000000000d002", "garbage"):
        assert logs.main(["x", "--id", bad]) == 1
        assert capsys.readouterr().out.strip() == "no API request with that id"
