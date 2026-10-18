"""The one diagnostic line per /ask: proxy_trusted and friends, as booleans only."""

import json

from tests.test_api import Client, make_client_app, retrieve_answer
from tests.test_guard import cfg_guard

SECRET, SALT = "s" * 32, "x" * 32
ENV = {"CTA_PROXY_SECRET": SECRET, "CTA_IP_SALT": SALT}
IP = "203.0.113.7"


def lines(capsys):
    out = capsys.readouterr().out
    return [json.loads(ln) for ln in out.splitlines() if ln.startswith('{"event": "ask"')]


def post(c, secret=SECRET, ip=IP):
    headers = {}
    if secret is not None:
        headers["x-cta-proxy-secret"] = secret
    if ip is not None:
        headers["x-real-ip"] = ip
    return c.post("/ask", json={"question": "I want to kill myself"}, headers=headers)


def app(monkeypatch, env=ENV):
    return make_client_app(Client(), monkeypatch, retrieve_answer(), env=env, cfg=cfg_guard())


def test_a_valid_secret_is_logged_as_trusted_with_the_visitor_seen_the_second_time(
    monkeypatch, capsys
):
    c = app(monkeypatch)
    post(c)
    post(c)
    first, second = lines(capsys)
    assert first["proxy_required"] is True and first["proxy_trusted"] is True
    assert first["forwarded_present"] is True and first["visitor_seen_before"] is False
    assert second["visitor_seen_before"] is True  # the limiter keyed the same visitor again


def test_a_changing_forwarded_visitor_shows_as_never_seen_before(monkeypatch, capsys):
    c = app(monkeypatch)
    for n in range(4):
        post(c, ip=f"203.0.113.{n + 1}")
    assert [ln["visitor_seen_before"] for ln in lines(capsys)] == [False] * 4


def test_a_wrong_or_missing_secret_is_logged_as_not_trusted_and_still_rejected(
    monkeypatch, capsys
):
    c = app(monkeypatch)
    assert post(c, secret="wrong").status_code == 403
    assert post(c, secret=None).status_code == 403
    for ln in lines(capsys):
        assert ln["proxy_required"] is True and ln["proxy_trusted"] is False


def test_a_missing_forwarded_visitor_is_logged(monkeypatch, capsys):
    c = app(monkeypatch)
    post(c, ip=None)
    post(c, ip="not-an-ip")
    assert [ln["forwarded_present"] for ln in lines(capsys)] == [False, False]


def test_local_use_with_no_secret_is_not_trusted(monkeypatch, capsys):
    c = app(monkeypatch, env={})
    post(c, secret=None)
    (ln,) = lines(capsys)
    assert ln["proxy_required"] is False and ln["proxy_trusted"] is False


def test_health_and_other_paths_make_no_line(monkeypatch, capsys):
    c = app(monkeypatch)
    c.get("/health")
    c.get("/nope", headers={"x-cta-proxy-secret": SECRET})
    assert lines(capsys) == []


def test_the_line_never_holds_the_secret_the_salt_an_address_or_a_hash(monkeypatch, capsys):
    import hashlib
    import hmac

    c = app(monkeypatch)
    post(c)
    out = capsys.readouterr().out
    key = hmac.new(SALT.encode(), IP.encode(), hashlib.sha256).hexdigest()
    for secret in (SECRET, SALT, IP, "testclient", key, key[:12]):
        assert secret not in out
    (ln,) = [json.loads(x) for x in out.splitlines() if x.startswith('{"event": "ask"')]
    assert set(ln) == {"event", "request_id", "proxy_required", "proxy_trusted",
                       "forwarded_present", "forwarded_family", "visitor_seen_before"}  # fmt: skip
    assert ln["forwarded_family"] == "ipv4"
    flags = set(ln) - {"event", "request_id", "forwarded_family"}
    assert all(isinstance(ln[k], bool) for k in flags)


def test_the_family_label_tells_ipv4_from_ipv6_from_nothing(monkeypatch, capsys):
    c = app(monkeypatch)
    post(c, ip="203.0.113.7")
    post(c, ip="2001:db8::1")
    post(c, ip=None)
    post(c, ip="junk")
    assert [ln["forwarded_family"] for ln in lines(capsys)] == ["ipv4", "ipv6", "none", "none"]
