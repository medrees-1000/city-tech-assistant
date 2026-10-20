"""Step 5: request logging: redaction, the migration, the writer, purge and the logs command.
The database tests use the throwaway-schema `conn` fixture of conftest.py (it runs every
migration); no paid call anywhere."""

from contextlib import nullcontext
from datetime import date

import pytest

from cta.api import logs, purge, requestlog
from cta.eval import judge_sheet
from cta.graph import build
from cta.index.db import migration_files
from cta.redact import redact
from tests.helpers import (
    ROUTER_CFG as CFG,
)
from tests.helpers import (
    Client,
    ask,
    insert,
    make_client_app,
    notice_text,
    retrieve_answer,
    routed_ans,
)

# ---- redaction (what is removed, and the known gap) ----


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("mail jane.doe@mail.citytech.cuny.edu now", "mail [EMAIL] now"),
        ("mail jane @ example.com now", "mail [EMAIL] now"),
        ("my ssn is 123-45-6789", "my ssn is [SSN]"),
        ("my ssn is 123 45 6789", "my ssn is [SSN]"),
        ("call 718-260-5800 today", "call [PHONE] today"),
        ("call (718) 260 5800 today", "call [PHONE] today"),
        ("call +1 718.260.5800 today", "call [PHONE] today"),
        ("my EMPLID is 23456789", "my EMPLID is [ID]"),
        ("id 23456789, email a@b.edu, phone 718-260-5800", "id [ID], email [EMAIL], phone [PHONE]"),
    ],
)
def test_redaction_removes_each_pattern(raw, clean):
    assert redact(raw) == clean


def test_known_gap_names_and_free_text_are_not_removed():
    """cta.redact is a pattern filter. It cannot recognise a name, an address or a circumstance."""
    text = "My name is Maria Lopez, I live at 123 Main Street and my GPA is 2.1"
    assert redact(text) == text
    # ids that are not exactly 8 digits, or that are written with a space inside, are not matched
    assert redact("employee id 234567890") == "employee id 234567890"
    assert redact("emplid 2345 6789") == "emplid 2345 6789"


def test_redaction_is_idempotent():
    once = redact("a@b.edu 718-260-5800")
    assert redact(once) == once


# ---- the record the API builds ----


def test_a_success_record_has_only_the_planned_columns_and_no_identifier(monkeypatch):
    c = make_client_app(Client(), monkeypatch, retrieve_answer())
    ask(c, "Hello from jane@x.edu")
    row = c.logs[0]
    assert set(row) | {"source"} == set(requestlog.COLUMNS)
    forbidden = {"ip", "user_agent", "cookie", "headers", "client", "host"}
    assert not forbidden & set(row) and not forbidden & set(row["trace"])
    assert "jane@x.edu" not in str(row)


# ---- the migration and the writer, in a throwaway schema ----


def columns(conn):
    return {
        r[0]: (r[1], r[2])
        for r in conn.execute(
            "SELECT column_name, data_type, column_default FROM information_schema.columns "
            "WHERE table_name = 'request_logs' AND table_schema = current_schema()"
        )
    }


@pytest.mark.integration
def test_migration_005_adds_the_columns_and_the_indexes_and_can_be_run_again(conn):
    cols = columns(conn)
    for name in ("request_id", "source", "status", "trace", "contact_office"):
        assert name in cols
    assert cols["trace"][0] == "jsonb" and cols["request_id"][0] == "uuid"
    assert "'eval'" in cols["source"][1]  # existing rows and eval inserts become 'eval'
    migration = next(p for p in migration_files() if p.name.startswith("005"))
    conn.execute(migration.read_text(encoding="utf-8"))  # safe to run again
    conn.commit()
    indexes = {
        r[0]
        for r in conn.execute(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'request_logs' AND schemaname = current_schema()"
        )
    }
    assert {"request_logs_ts_idx", "request_logs_request_id_idx"} <= indexes
    with pytest.raises(Exception, match="request_logs_source_check|violates check"):
        conn.execute("INSERT INTO request_logs (question, source) VALUES ('q', 'other')")
    conn.rollback()


@pytest.mark.integration
def test_the_eval_code_still_inserts_and_its_rows_are_source_eval(conn):
    ans = routed_ans(["fall-2026-040"])
    ans.text, ans.today, ans.router = "ok", date(2026, 10, 11), {}
    build.log_request(conn, "when?", ans, CFG, None)
    assert conn.execute("SELECT source, status, trace FROM request_logs").fetchone() == (
        "eval",
        None,
        None,
    )


@pytest.mark.integration
def test_the_writer_stores_a_row_per_outcome(conn, monkeypatch):
    c = make_client_app(Client(), monkeypatch, retrieve_answer())
    ask(c, "How do I apply? my phone is 718-260-5800")
    for record in c.logs:
        requestlog.write(conn, record)
    requestlog.write(
        conn,
        requestlog.error_record(
            "7f0f3a4e-0000-4000-8000-000000000001",
            "provider_error",
            "q",
            date(2026, 10, 11),
            "m",
            12.0,
        ),
    )
    rows = conn.execute(
        "SELECT source, status, question, route, abstained, trace->>'answer_type', cost_usd, "
        "latency_ms FROM request_logs ORDER BY id"
    ).fetchall()
    assert rows[0][:2] == ("api", "ok") and "[PHONE]" in rows[0][2] and rows[0][3] == "retrieve"
    assert rows[0][5] == "answer" and rows[0][6] > 0 and rows[0][7] > 0
    assert rows[1][:2] == ("api", "provider_error") and rows[1][3] is None


@pytest.mark.integration
def test_eval_reports_still_read_eval_rows_and_never_pick_up_api_rows(conn):
    conn.execute("INSERT INTO eval_runs (label, split) VALUES ('baseline-dev', 'dev')")
    run_id = conn.execute("SELECT id FROM eval_runs").fetchone()[0]
    q = "Who is the chair?"
    conn.execute(
        "INSERT INTO request_logs (run_id, question, answer, retrieved) "
        "VALUES (%s, %s, 'eval answer', '[{\"id\": \"c1\"}]'::jsonb)",
        (run_id, q),
    )
    requestlog.write(
        conn,
        {
            **requestlog.error_record(
                "7f0f3a4e-0000-4000-8000-000000000002", "ok", q, date(2026, 10, 11), "m", 1.0
            ),
            "answer": "api answer",
        },
    )
    assert judge_sheet.stored_answer(conn, "baseline-dev", q) == ("eval answer", ["c1"])


# ---- purge ----




@pytest.mark.integration
def test_purge_deletes_only_old_api_rows(conn):
    insert(conn, "api", 40, "7f0f3a4e-0000-4000-8000-000000000011")
    insert(conn, "api", 31, "7f0f3a4e-0000-4000-8000-000000000012")
    insert(conn, "api", 5, "7f0f3a4e-0000-4000-8000-000000000013")
    insert(conn, "eval", 400)  # an old eval-run row: never touched
    insert(conn, "eval", 2)
    conn.commit()
    assert purge.purge(conn, 30, dry_run=True) == 2  # a dry run counts and deletes nothing
    assert conn.execute("SELECT count(*) FROM request_logs").fetchone()[0] == 5
    assert purge.purge(conn, 30) == 2
    left = conn.execute(
        "SELECT source, count(*) FROM request_logs GROUP BY source ORDER BY source"
    ).fetchall()
    assert left == [("api", 1), ("eval", 2)]
    assert purge.purge(conn, 30) == 0


@pytest.mark.integration
def test_the_purge_command_prints_the_count_and_validates_days(conn, monkeypatch, capsys):
    insert(conn, "api", 60, "7f0f3a4e-0000-4000-8000-000000000021")
    conn.commit()
    monkeypatch.setattr(purge, "connect", lambda: nullcontext(conn))
    assert purge.main(["x", "--days", "30", "--dry-run"]) == 0
    assert "dry run: 1 API rows older than 30 days would be deleted" in capsys.readouterr().out
    assert purge.main(["x", "--days", "30"]) == 0
    assert (
        "1 API rows older than 30 days deleted (eval rows are never touched)"
        in capsys.readouterr().out
    )
    assert purge.main(["x", "--days", "0"]) == 2


# ---- the logs command ----


def test_the_logs_line_collapses_whitespace_and_line_breaks_in_the_question():
    from datetime import datetime

    row = (datetime(2026, 10, 13, 12, 0, 0), "and\ntell   me\tmore\r\nplease", "retrieve", True,
           None, "ok", 1200, 100, 10, 0.0001, "down", None)  # fmt: skip
    out = logs.line(row)
    assert "\n" not in out and "\t" not in out and "\r" not in out
    assert out.endswith("| and tell me more please") and "vote=down" in out


@pytest.mark.integration
def test_the_logs_command_prints_the_last_api_requests_redacted_and_a_total(
    conn, monkeypatch, capsys
):
    c = make_client_app(Client(), monkeypatch, retrieve_answer())
    ask(c, "How do I apply for graduation?")
    requestlog.write(conn, c.logs[0])
    other = {
        **c.logs[0],
        "request_id": "7f0f3a4e-0000-4000-8000-000000000031",
        "route": "calendar",
        "contact_office": "registrar",
    }
    requestlog.write(conn, other)
    # a row with an unredacted email (it could only come from outside the API): still hidden
    conn.execute(
        "INSERT INTO request_logs (source, question, route, status, ts) "
        "VALUES ('api', 'write to jane@x.edu', 'chain', 'ok', now() + interval '1 minute')"
    )
    insert(conn, "eval", 0)  # eval rows are not API requests
    conn.commit()
    monkeypatch.setattr(logs, "connect", lambda: nullcontext(conn))
    capsys.readouterr()  # drop the per-request diagnostic line the API printed above
    assert logs.main(["x", "--last", "2"]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 3  # two rows and the total line
    assert "jane@x.edu" not in "\n".join(out) and "[EMAIL]" in out[0] and "chain" in out[0]
    assert out[1].count("calendar") == 1 and "office=registrar" in out[1] and "ok" in out[1]
    assert out[-1].startswith("3 API requests, total cost $")
    assert logs.main(["x", "--last", "5", "--route", "retrieve"]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 2 and "retrieve" in out[0] and out[-1].startswith("1 API requests matching")
    assert logs.main(["x", "--since", "2999-01-01"]) == 0
    assert capsys.readouterr().out.strip() == (
        "0 API requests matching, total cost $0.000000; votes: 0 up, 0 down, 0 no vote"
    )


# ---- the privacy notice matches the code ----




def test_the_notice_says_what_the_code_does():
    from cta.settings import ROOT

    text = notice_text()
    # 30 days: the purge command's examples and the plan use 30, and the notice says it
    assert "saved for 30 days" in text
    # the production stack runs the purge every day (docker-compose.prod.yml, checked in
    # tests/test_deploy_files.py); the purge itself is the command below
    assert "deleted automatically every day" in text
    purge_doc = (ROOT / "src" / "cta" / "api" / "purge.py").read_text(encoding="utf-8")
    assert "--days 30" in purge_doc
    # emails, phone numbers, ID numbers (and SSN-like numbers) are the patterns of cta.redact
    assert {"EMAIL", "PHONE", "ID"} <= {
        tag
        for tag in ("EMAIL", "SSN", "PHONE", "ID")
        if f"[{tag}]" in redact("a@b.edu 718-260-5800 23456789 123-45-6789")
    }
    assert "emails, phone numbers and ID numbers removed" in text
    # names are removed after a few cues (screen.scrub, batch 1); a name written any other way
    # stays, and the notice says so
    from cta.api.screen import scrub

    assert redact("Maria Lopez") == "Maria Lopez"
    assert scrub("Maria Lopez") == "Maria Lopez"
    assert scrub("my name is Maria Lopez") == "my name is [NAME]"
    assert scrub("I'm Maria Lopez") == "I'm [NAME]"
    assert scrub("hi it's Maria Lopez") == "hi it's Maria Lopez"  # not detected, as the notice says
    assert "names removed where we can detect them" in text
    assert "A name written another way may be saved" in text
    assert "removed only when it follows" not in text


def test_the_notice_claim_of_no_ip_and_no_cookies_is_true_of_the_code():
    from cta.settings import ROOT

    assert "No IP address and no cookies are stored" in notice_text()
    assert "counted in memory per visitor" in notice_text()  # the step 7 sentence, true of guard.py
    assert "cleared when the service restarts" in notice_text()
    forbidden = {"ip", "ip_address", "client_ip", "user_agent", "cookie", "cookies", "headers"}
    assert not forbidden & set(requestlog.COLUMNS)
    sources = [
        *(ROOT / "src" / "cta" / "api").glob("*.py"),
        *(ROOT / "web" / "app").rglob("*.tsx"),
        *(ROOT / "web" / "lib").glob("*.ts"),
    ]
    for path in sources:
        code = path.read_text(encoding="utf-8")
        if path.name in ("notice.ts", "notice.test.ts"):
            continue
        assert "set_cookie" not in code and "document.cookie" not in code, path
        assert "localStorage" not in code and "sessionStorage" not in code, path
        # the API never reads x-forwarded-for; the page's proxy (web/lib/forward.ts) reads the
        # host's copy once, to pass it on in x-real-ip, and stores nothing (no cookie or storage)
        if path.name not in ("forward.ts", "forward.test.ts"):
            assert "x-forwarded-for" not in code.lower(), path
        if path.name != "guard.py":  # the one place that reads the address (step 7, rule 8)
            assert "request.client" not in code, path
    import inspect

    from cta.api import guard

    lines = [ln for ln in inspect.getsource(guard).splitlines() if "request.client" in ln]
    assert len(lines) == 1  # one read, and it is in visitor_key, which only hashes it
    key_source = inspect.getsource(guard.Guard.visitor_key)
    tag_source = inspect.getsource(guard.Guard.tag)  # the keyed hash that visitor_key calls
    assert "request.client" in key_source and "self.tag(" in key_source
    assert "sha256" in tag_source and "hmac" in tag_source
    rest = inspect.getsource(guard).replace(key_source, "").replace(tag_source, "")
    assert "address" not in rest.replace("network address", "")  # no other use of it
    assert "request.client" not in inspect.getsource(guard.Guard.stage1)
    launcher = (ROOT / "src" / "cta" / "api" / "__main__.py").read_text(encoding="utf-8")
    assert "access_log=False" in launcher  # the server's own log would print client addresses
