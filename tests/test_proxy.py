"""The shared secret of the Vercel proxy, the forwarded visitor address and the keyed hash, and the
one diagnostic line per /ask (booleans only) with the header the limiter key comes from. Fake
clients only: no network, no database, no paid call.
"""

import hashlib
import hmac
import json
import logging

from cta.api import guard
from cta.api.checks import startup_problems
from tests.helpers import (
    CFG,
    Client,
    FakeConn,
    SpendConn,
    cfg_guard,
    make_client_app,
    req,
    retrieve_answer,
    settings,
)

SECRET = "s" * 32
SALT = "x" * 32
ENV = {"CTA_PROXY_SECRET": SECRET, "CTA_IP_SALT": SALT}
GOOD = {"x-cta-proxy-secret": SECRET}


USER = "user_2abcXYZ123"


def post(c, ip=None, secret=SECRET, question="How do I apply for graduation?", user=USER):
    headers = {} if user is None else {"x-cta-user": user}
    if secret is not None:
        headers["x-cta-proxy-secret"] = secret
    if ip is not None:
        headers["x-real-ip"] = ip
    return c.post("/ask", json={"question": question}, headers=headers)


def app(monkeypatch, env=ENV, **cfg):
    return make_client_app(Client(), monkeypatch, retrieve_answer(), env=env,
                           cfg=cfg_guard(**cfg))  # fmt: skip


# ---- the secret ----


def test_a_valid_secret_is_served(monkeypatch):
    c = app(monkeypatch)
    r = post(c, "203.0.113.7")
    assert r.status_code == 200 and r.json()["answer_type"] == "answer"


def test_a_wrong_or_missing_secret_is_rejected_without_any_model_call(monkeypatch):
    client = Client()
    c = make_client_app(client, monkeypatch, retrieve_answer(), env=ENV, cfg=cfg_guard())
    for secret in ("wrong", "", SECRET[:-1], SECRET + "x", None):
        r = post(c, "203.0.113.7", secret=secret)
        assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden", secret
    assert client.calls == [] and c.logs == []
    assert c.get("/health").json()["proxy_rejected"] == 5


def test_other_paths_need_the_secret_too_except_the_health_check(monkeypatch):
    c = app(monkeypatch)
    assert c.get("/health").status_code == 200  # no secret: the container health check
    for path in ("/docs", "/openapi.json", "/nope"):
        assert c.get(path).status_code == 403, path
    r = c.post("/feedback", json={"request_id": "a" * 32, "vote": "up"})
    assert r.status_code == 403
    assert c.get("/docs", headers=GOOD).status_code == 200


def test_post_to_health_is_not_exempt(monkeypatch):
    c = app(monkeypatch)
    assert c.post("/health").status_code == 403


def test_health_says_a_secret_is_required_and_never_shows_it_or_the_salt(monkeypatch):
    c = app(monkeypatch)
    text = json.dumps(c.get("/health").json())
    assert c.get("/health").json()["proxy_required"] is True
    assert SECRET not in text and SALT not in text


# ---- the forwarded visitor address ----


def test_two_visitors_behind_the_proxy_get_separate_limits(monkeypatch):
    c = app(monkeypatch, rate_per_minute=1)
    assert post(c, "203.0.113.7").json()["answer_type"] == "answer"
    again = post(c, "203.0.113.7").json()  # the same visitor
    assert again["answer"] == guard.TEXTS["rate_limited"]
    other = post(c, "198.51.100.9").json()  # another visitor, same connection address
    assert other["answer_type"] == "answer"


def test_without_a_secret_configured_the_forwarded_header_is_ignored(monkeypatch):
    c = make_client_app(Client(), monkeypatch, retrieve_answer(), env={},
                        cfg=cfg_guard(rate_per_minute=1))  # fmt: skip
    assert post(c, "203.0.113.7", secret=None).json()["answer_type"] == "answer"
    # a different forwarded address does not give a new count: local behaviour is unchanged
    second = post(c, "198.51.100.9", secret=None).json()
    assert second["answer"] == guard.TEXTS["rate_limited"]
    assert c.get("/health").json()["proxy_required"] is False


def test_a_forged_or_missing_forwarded_address_falls_back_to_the_connection(monkeypatch):
    c = app(monkeypatch, rate_per_minute=1)
    assert post(c, "not-an-address").json()["answer_type"] == "answer"
    assert post(c, None).json()["answer"] == guard.TEXTS["rate_limited"]  # same fallback key


def test_ipv6_is_accepted(monkeypatch):
    c = app(monkeypatch, rate_per_minute=1)
    assert post(c, "2001:db8::1").json()["answer_type"] == "answer"
    assert post(c, "2001:db8::2").json()["answer_type"] == "answer"


# ---- the keyed hash ----


def test_the_key_is_an_hmac_sha256_of_the_address_with_the_salt_from_the_environment():
    g = guard.Guard(settings(), proxy_secret=SECRET, ip_salt=SALT)
    request = req("10.0.0.1")
    request.headers = {"x-cta-proxy-secret": SECRET, "x-real-ip": "203.0.113.7"}
    want = hmac.new(SALT.encode(), b"203.0.113.7", hashlib.sha256).hexdigest()
    assert g.visitor_key(request) == want
    assert g.visitor_key(request) == want  # stable
    again = guard.Guard(settings(), proxy_secret=SECRET, ip_salt=SALT)
    assert again.visitor_key(request) == want  # stable across a restart when the salt is set
    other = guard.Guard(settings(), proxy_secret=SECRET, ip_salt="y" * 32)
    assert other.visitor_key(request) != want


def test_without_a_salt_the_key_is_random_per_start_and_never_the_raw_address():
    a, b = guard.Guard(settings()), guard.Guard(settings())
    request = req("203.0.113.7")
    request.headers = {}
    assert a.visitor_key(request) != b.visitor_key(request)
    assert "203.0.113.7" not in a.visitor_key(request)


def test_the_raw_address_is_in_no_row_log_or_health(monkeypatch, caplog):
    c = app(monkeypatch, rate_per_minute=1)
    with caplog.at_level(logging.DEBUG):
        post(c, "203.0.113.7")
        post(c, "203.0.113.7")  # rate limited
        post(c, "203.0.113.7", secret="wrong")  # rejected
    g = c.app.state.guard
    digest = hmac.new(g.salt, b"203.0.113.7", hashlib.sha256).hexdigest()
    everything = json.dumps(c.logs, default=str) + caplog.text + json.dumps(c.get("/health").json())
    assert "203.0.113.7" not in everything and "testclient" not in everything
    assert digest not in everything and digest[:12] not in everything


# ---- start-up checks ----


def test_a_short_secret_or_salt_stops_the_start(tmp_path):
    base = {"OPENAI_API_KEY": "sk-test"}
    problems = startup_problems(CFG, env=base | {"CTA_PROXY_SECRET": "short"},
                                connect=lambda: FakeConn([]))  # fmt: skip
    assert any("CTA_PROXY_SECRET is set but shorter than 16" in p for p in problems)
    problems = startup_problems(CFG, env=base | {"CTA_IP_SALT": "short"},
                                connect=lambda: FakeConn([]))  # fmt: skip
    assert any("CTA_IP_SALT is set but shorter than 16" in p for p in problems)
    ok = startup_problems(CFG, env=base | ENV, connect=lambda: FakeConn([]))
    assert not any("CTA_" in p and "shorter" in p for p in ok)


# ---- from test_proxy_diag.py ----
#
# The one diagnostic line per /ask (booleans only) and which header the limiter key comes from.

DIAG_SECRET, DIAG_SALT = "s" * 32, "x" * 32
DIAG_ENV = {"CTA_PROXY_SECRET": DIAG_SECRET, "CTA_IP_SALT": DIAG_SALT}
IP = "203.0.113.7"


def lines(capsys):
    out = capsys.readouterr().out
    return [json.loads(ln) for ln in out.splitlines() if ln.startswith('{"event": "ask"')]


def diag_post(c, secret=DIAG_SECRET, ip=IP, **extra):
    headers = dict(extra)
    if secret is not None:
        headers["x-cta-proxy-secret"] = secret
    if ip is not None:
        headers["x-real-ip"] = ip
    return c.post("/ask", json={"question": "I want to kill myself"}, headers=headers)


def diag_app(monkeypatch, env=DIAG_ENV):
    return make_client_app(Client(), monkeypatch, retrieve_answer(), env=env, cfg=cfg_guard())


def test_a_valid_secret_is_logged_as_trusted_with_a_forwarded_visitor(monkeypatch, capsys):
    c = diag_app(monkeypatch)
    diag_post(c)
    diag_post(c)
    first, second = lines(capsys)
    assert first["proxy_required"] is True and first["proxy_trusted"] is True
    assert first["forwarded_present"] is True and second["proxy_trusted"] is True


def test_a_wrong_or_missing_secret_is_logged_as_not_trusted_and_still_rejected(monkeypatch, capsys):
    c = diag_app(monkeypatch)
    assert diag_post(c, secret="wrong").status_code == 403
    assert diag_post(c, secret=None).status_code == 403
    for ln in lines(capsys):
        assert ln["proxy_required"] is True and ln["proxy_trusted"] is False


def test_a_missing_forwarded_visitor_is_logged(monkeypatch, capsys):
    c = diag_app(monkeypatch)
    diag_post(c, ip=None)
    diag_post(c, ip="not-an-ip")
    assert [ln["forwarded_present"] for ln in lines(capsys)] == [False, False]


def test_forwarded_present_counts_x_cta_visitor_when_trusted_but_not_otherwise(monkeypatch, capsys):
    c = diag_app(monkeypatch)
    diag_post(c, ip=None, **{"x-cta-visitor": IP})  # the header the API uses, no x-real-ip at all
    diag_post(c, ip=None, **{"x-cta-visitor": "junk"})
    # not trusted: the header is ignored
    diag_post(c, secret="wrong", ip=None, **{"x-cta-visitor": IP})
    assert [ln["forwarded_present"] for ln in lines(capsys)] == [True, False, False]


def test_local_use_with_no_secret_is_not_trusted(monkeypatch, capsys):
    c = diag_app(monkeypatch, env={})
    diag_post(c, secret=None)
    (ln,) = lines(capsys)
    assert ln["proxy_required"] is False and ln["proxy_trusted"] is False


def test_health_and_other_paths_make_no_line(monkeypatch, capsys):
    c = diag_app(monkeypatch)
    c.get("/health")
    c.get("/nope", headers={"x-cta-proxy-secret": DIAG_SECRET})
    assert lines(capsys) == []


def test_the_line_never_holds_the_secret_the_salt_an_address_or_a_hash(monkeypatch, capsys):
    import hashlib
    import hmac

    c = diag_app(monkeypatch)
    diag_post(c)
    out = capsys.readouterr().out
    key = hmac.new(DIAG_SALT.encode(), IP.encode(), hashlib.sha256).hexdigest()
    for secret in (DIAG_SECRET, DIAG_SALT, IP, "testclient", key, key[:12]):
        assert secret not in out
    (ln,) = [json.loads(x) for x in out.splitlines() if x.startswith('{"event": "ask"')]
    assert set(ln) == {"event", "request_id", "proxy_required", "proxy_trusted",
                       "forwarded_present"}  # fmt: skip
    flags = set(ln) - {"event", "request_id"}
    assert all(isinstance(ln[k], bool) for k in flags)


class FakeRequest:
    def __init__(self, headers, host="172.18.0.9"):
        self.headers = headers
        self.client = type("C", (), {"host": host})()


def test_x_cta_visitor_is_ignored_without_a_matching_secret():
    g = cfg_guard_guard()
    conn = g.visitor_key(FakeRequest({}))
    for headers in ({"x-cta-visitor": IP}, {"x-cta-visitor": IP, "x-cta-proxy-secret": "wrong"}):
        assert g.visitor_key(FakeRequest(headers)) == conn  # the connection address, as before
    ok = g.visitor_key(FakeRequest({"x-cta-visitor": IP, "x-cta-proxy-secret": DIAG_SECRET}))
    assert ok == g.tag(IP) and ok != conn


def cfg_guard_guard():
    from cta.api.guard import Guard

    cfg = {"disabled": False, "rate_limit_max_keys": 100}
    return Guard(cfg, proxy_secret=DIAG_SECRET, ip_salt=DIAG_SALT)


def key_for(g, **headers):
    return g.visitor_key(FakeRequest({"x-cta-proxy-secret": DIAG_SECRET, **headers}))


def test_x_cta_visitor_is_the_visitor_even_when_x_real_ip_changes():
    g = cfg_guard_guard()
    a = key_for(g, **{"x-cta-visitor": "203.0.113.9", "x-real-ip": "198.51.100.1"})
    b = key_for(g, **{"x-cta-visitor": "203.0.113.9", "x-real-ip": "198.51.100.2"})
    other = key_for(g, **{"x-cta-visitor": "203.0.113.10", "x-real-ip": "198.51.100.1"})
    assert a == b and a != other


def test_an_invalid_x_cta_visitor_falls_back_to_x_real_ip():
    g = cfg_guard_guard()
    assert key_for(g, **{"x-cta-visitor": "junk", "x-real-ip": IP}) == g.tag(IP)


# ---- login: x-cta-user, checked after the rate limit and before the safety screen ----

SIGN_IN = {"error": "sign_in_required"}


def signed_out_is_refused(c, client, **kw):
    r = post(c, "203.0.113.7", **kw)
    assert r.status_code == 401 and r.json() == SIGN_IN
    assert client.calls == [] and c.logs == []  # no model call, no log row


def test_a_missing_or_malformed_user_header_is_401_with_no_row_and_no_model_call(monkeypatch):
    client = Client()
    c = make_client_app(client, monkeypatch, retrieve_answer(), env=ENV, cfg=cfg_guard())
    for user in (None, "", "abc", "user_", "user_a-b", "User_abc", " user_abc", "user_abc\n",
                 "user_" + "a" * 60, "x" * 65):
        signed_out_is_refused(c, client, user=user)


def test_the_longest_allowed_user_id_is_64_characters(monkeypatch):
    c = app(monkeypatch)
    assert post(c, "203.0.113.7", user="user_" + "a" * 59).status_code == 200
    assert post(c, "203.0.113.7", user="user_" + "a" * 60).status_code == 401


def test_a_user_header_without_the_matching_secret_is_the_existing_403(monkeypatch):
    client = Client()
    c = make_client_app(client, monkeypatch, retrieve_answer(), env=ENV, cfg=cfg_guard())
    for secret in (None, "wrong"):
        r = post(c, "203.0.113.7", secret=secret)  # a forged direct call: valid user id, no secret
        assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"
    assert client.calls == [] and c.logs == []


def test_a_valid_user_header_with_the_secret_is_served_and_the_id_is_not_logged(monkeypatch):
    c = app(monkeypatch)
    r = post(c, "203.0.113.7")
    assert r.status_code == 200 and r.json()["answer_type"] == "answer"
    assert USER not in json.dumps(c.logs) + r.text + json.dumps(c.get("/health").json())


def test_login_is_not_enforced_without_a_proxy_secret(monkeypatch):
    c = make_client_app(Client(), monkeypatch, retrieve_answer(), env={}, cfg=cfg_guard())
    r = c.post("/ask", json={"question": "How do I apply for graduation?"})
    assert r.status_code == 200 and r.json()["answer_type"] == "answer"


def test_the_rate_limit_runs_before_the_login_check(monkeypatch):
    client = Client()
    c = make_client_app(client, monkeypatch, retrieve_answer(), env=ENV,
                        cfg=cfg_guard(rate_per_minute=1))  # fmt: skip
    assert post(c, "203.0.113.7", user=None).status_code == 401
    second = post(c, "203.0.113.7", user=None)  # same visitor, over the limit: the rate-limit reply
    detail = second.json()["how_found"]["route_detail"]
    assert second.status_code == 200 and detail == "rate_limited"


def test_signed_out_with_the_kill_switch_on_is_401_not_the_paused_reply(monkeypatch):
    client = Client()
    c = make_client_app(client, monkeypatch, retrieve_answer(), env=ENV,
                        cfg=cfg_guard(disabled=True))  # fmt: skip
    signed_out_is_refused(c, client, user=None)
    signed_out_is_refused(c, client, user=None, question="I want to kill myself")  # no 988 either
    signed_in = post(c, "203.0.113.7")
    assert signed_in.json()["how_found"]["route_detail"] == "kill_switch"


def test_signed_in_at_a_cap_gets_the_cap_reply(monkeypatch):
    client = Client()
    c = make_client_app(client, monkeypatch, retrieve_answer(), env=ENV,
                        cfg=cfg_guard(daily_spend_cap_usd=1.0),
                        connect=lambda: SpendConn(50.0))  # fmt: skip
    r = post(c, "203.0.113.7")
    assert r.status_code == 200 and r.json()["how_found"]["route_detail"] == "daily_cap"
    rows = len(c.logs)
    r = post(c, "203.0.113.7", user=None)
    assert r.status_code == 401 and r.json() == SIGN_IN and len(c.logs) == rows
