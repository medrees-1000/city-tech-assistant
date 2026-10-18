"""The shared secret of the Vercel proxy, the forwarded visitor address and the keyed hash.
Fake clients only: no network, no database, no paid call."""

import hashlib
import hmac
import json
import logging

from cta.api import guard
from cta.api.checks import startup_problems
from tests.test_api import CFG, Client, FakeConn, make_client_app, retrieve_answer
from tests.test_guard import cfg_guard, req, settings

SECRET = "s" * 32
SALT = "x" * 32
ENV = {"CTA_PROXY_SECRET": SECRET, "CTA_IP_SALT": SALT}
GOOD = {"x-cta-proxy-secret": SECRET}


def post(c, ip=None, secret=SECRET, question="How do I apply for graduation?"):
    headers = {}
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
