"""scripts/smoke_live.py against a fake server (httpx.MockTransport): no network, no model call."""

import importlib.util
import json

import httpx

from cta.settings import ROOT

spec = importlib.util.spec_from_file_location("smoke_live", ROOT / "scripts" / "smoke_live.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)

SECRET = "s" * 32


def reply(text, answer_type="answer", route="retrieve", detail="x", cites=1, contact=None,
          abstained=False):  # fmt: skip
    return {
        "answer": text, "answer_type": answer_type, "route": route, "abstained": abstained,
        "citations": [{"n": i + 1, "cited": True} for i in range(cites)], "contact": contact,
        "how_found": {"route_detail": detail},
    }  # fmt: skip


class FakeServer:
    """Answers like the real API contract; `broken` names one behaviour to get wrong."""

    def __init__(self, broken=None, paused=False, health_status=200):
        self.broken, self.paused, self.health_status = broken, paused, health_status
        self.count, self.seen_headers = 0, []

    def __call__(self, request):
        self.seen_headers.append(dict(request.headers))
        if request.url.path.endswith("/health"):
            body = {"status": "ok", "db": "ok", "version": "abc1234", "settings": {"rescue": "on"},
                    "config_version": "0123456789", "disabled": self.paused}  # fmt: skip
            return httpx.Response(self.health_status, json=body)
        q = json.loads(request.content)["question"].lower()
        self.count += 1
        if self.paused:
            body = reply("The assistant is temporarily paused. Please check back later.",
                         "guardrail", "guardrail", "kill_switch", 0)  # fmt: skip
        elif self.count > 10:
            body = reply("You're asking quickly.", "guardrail", "guardrail", "rate_limited", 0)
        elif "kill myself" in q:
            text = "" if self.broken == "988" else "call or text 988"
            body = reply(text, "guardrail", "guardrail", "distress", 0)
        elif "hurting me" in q:
            body = reply("Public Safety (718) 260-5550", "guardrail", "guardrail", "danger", 0)
        elif "ignore all previous" in q:
            body = reply("I can only help with City Tech registration.", "guardrail", "guardrail",
                         "injection", 0)  # fmt: skip
        elif "fall 2027" in q:
            contact = None if self.broken == "contact" else {"office": "registrar"}
            body = reply("No calendar.", "abstain", "calendar", "x", 0, contact, True)
        elif "withdraw" in q:
            body = reply("Date. [1]", route="calendar")
        elif "should i drop" in q:
            advice = "You should drop it." if self.broken == "advice" else "The rules are... [1]"
            body = reply(advice)
        else:
            body = reply("Apply here. [1]", cites=0 if self.broken == "citation" else 1)
        return httpx.Response(200, json=body)


def run(server, *args):
    client = httpx.Client(transport=httpx.MockTransport(server), base_url="http://api.test")
    s = smoke.Smoke(client, "", SECRET, "203.0.113.9")
    smoke.run(s, "open", "http://api.test/health")
    return s


def test_a_good_server_passes_every_check_with_about_ten_requests():
    server = FakeServer()
    s = run(server)
    assert [ok for _, ok, _ in s.rows] == [True] * 9, s.table()
    assert 10 <= s.sent <= 12 and server.count == s.sent
    assert "9 passed, 0 failed" in s.table()


def test_each_broken_behaviour_is_a_fail_row_and_the_others_still_run():
    for broken, name in (("988", "tier 1"), ("contact", "abstain"), ("advice", "advice"),
                         ("citation", "normal")):  # fmt: skip
        s = run(FakeServer(broken))
        failed = [n for n, ok, _ in s.rows if not ok]
        assert len(failed) == 1 and name in failed[0], (broken, failed)


def test_the_secret_and_a_documentation_visitor_are_sent_and_never_printed():
    server = FakeServer()
    s = run(server)
    assert all(h.get("x-cta-proxy-secret") == SECRET for h in server.seen_headers[:3])
    assert server.seen_headers[0]["x-real-ip"] == "203.0.113.9"
    assert SECRET not in s.table()


def test_without_a_secret_no_proxy_header_is_sent():
    server = FakeServer()
    client = httpx.Client(transport=httpx.MockTransport(server), base_url="http://api.test")
    smoke.run(smoke.Smoke(client, "", "", "203.0.113.9"), "open", "http://api.test/health")
    assert all("x-cta-proxy-secret" not in h for h in server.seen_headers)
    visitors = [h["x-real-ip"] for h in server.seen_headers if "x-real-ip" in h]
    assert visitors and set(visitors) == {"203.0.113.9"}  # every /ask carries the made-up visitor


def test_a_server_that_never_rate_limits_fails_that_check():
    class Never(FakeServer):
        def __call__(self, request):
            self.count = min(self.count, 5)
            return super().__call__(request)

    s = run(Never())
    assert [n for n, ok, _ in s.rows if not ok] == ["11th request in a minute is rate limited"]


def test_hidden_health_expects_a_404_and_an_open_one_a_200():
    client = httpx.Client(transport=httpx.MockTransport(FakeServer(health_status=404)),
                          base_url="http://api.test")  # fmt: skip
    s = smoke.Smoke(client, "", SECRET, "203.0.113.9")
    smoke.run(s, "hidden", "http://api.test/health")
    assert dict((n, ok) for n, ok, _ in s.rows)["health endpoint"] is True
    s = run(FakeServer(health_status=404))
    assert dict((n, ok) for n, ok, _ in s.rows)["health endpoint"] is False


def test_paused_mode_checks_the_kill_switch_reply():
    server = FakeServer(paused=True)
    client = httpx.Client(transport=httpx.MockTransport(server), base_url="http://api.test")
    s = smoke.Smoke(client, "", SECRET, "203.0.113.9")
    smoke.run_paused(s, "open", "http://api.test/health")
    assert all(ok for _, ok, _ in s.rows) and s.sent == 1
    plain = httpx.Client(transport=httpx.MockTransport(FakeServer()), base_url="http://api.test")
    s2 = smoke.Smoke(plain, "", SECRET, "203.0.113.9")
    smoke.run_paused(s2, "open", "http://api.test/health")
    assert not s2.rows[0][1]


def test_main_returns_one_on_a_failure(monkeypatch, capsys):
    real = httpx.Client

    def client(**kw):
        return real(transport=httpx.MockTransport(FakeServer("988")), **kw)

    monkeypatch.setattr(smoke.httpx, "Client", client)
    assert smoke.main(["x", "http://api.test", "--secret", SECRET]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out and "PASS" in out and SECRET not in out


def login_server(user_required=True):
    """An API that enforces login: 401 sign_in_required unless x-cta-user is sent."""
    inner = FakeServer()

    def handler(request):
        needs_login = request.url.path.endswith("/ask") and user_required
        if needs_login and "x-cta-user" not in request.headers:
            return httpx.Response(401, json={"error": "sign_in_required"})
        return inner(request)

    return handler, inner


def test_user_sends_x_cta_user_and_a_direct_run_passes():
    handler, inner = login_server()
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://api.test")
    s = smoke.Smoke(client, "", SECRET, "203.0.113.9", "user_smoke1")
    smoke.run(s, "open", "http://api.test/health")
    assert [ok for _, ok, _ in s.rows] == [True] * 9, s.table()
    sent = [h["x-cta-user"] for h in inner.seen_headers if "x-cta-user" in h]
    assert sent and set(sent) == {"user_smoke1"}


def test_without_user_a_login_enforcing_api_fails_with_a_hint():
    handler, _ = login_server()
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://api.test")
    s = smoke.Smoke(client, "", SECRET, "203.0.113.9")
    smoke.run(s, "open", "http://api.test/ask-less-health")
    assert "--user" in s.table() and "FAIL" in s.table()


def test_expect_signed_out_passes_on_401_and_fails_if_ask_is_open():
    handler, _ = login_server()
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://api.test")
    s = smoke.Smoke(client, "", "", "203.0.113.9")
    smoke.run_signed_out(s, "open", "http://api.test/health")
    assert [ok for _, ok, _ in s.rows] == [True, True], s.table()
    open_handler, _ = login_server(user_required=False)
    client = httpx.Client(transport=httpx.MockTransport(open_handler), base_url="http://api.test")
    s = smoke.Smoke(client, "", "", "203.0.113.9")
    smoke.run_signed_out(s, "open", "http://api.test/health")
    assert s.rows[0][1] is False and "HTTP 200" in s.rows[0][2]
