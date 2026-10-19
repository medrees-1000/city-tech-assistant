"""The one diagnostic line per /ask (booleans only) and which header the limiter key comes from."""

import json

from tests.test_api import Client, make_client_app, retrieve_answer
from tests.test_guard import cfg_guard

SECRET, SALT = "s" * 32, "x" * 32
ENV = {"CTA_PROXY_SECRET": SECRET, "CTA_IP_SALT": SALT}
IP = "203.0.113.7"


def lines(capsys):
    out = capsys.readouterr().out
    return [json.loads(ln) for ln in out.splitlines() if ln.startswith('{"event": "ask"')]


def post(c, secret=SECRET, ip=IP, **extra):
    headers = dict(extra)
    if secret is not None:
        headers["x-cta-proxy-secret"] = secret
    if ip is not None:
        headers["x-real-ip"] = ip
    return c.post("/ask", json={"question": "I want to kill myself"}, headers=headers)


def app(monkeypatch, env=ENV):
    return make_client_app(Client(), monkeypatch, retrieve_answer(), env=env, cfg=cfg_guard())


def test_a_valid_secret_is_logged_as_trusted_with_a_forwarded_visitor(monkeypatch, capsys):
    c = app(monkeypatch)
    post(c)
    post(c)
    first, second = lines(capsys)
    assert first["proxy_required"] is True and first["proxy_trusted"] is True
    assert first["forwarded_present"] is True and second["proxy_trusted"] is True


def test_a_wrong_or_missing_secret_is_logged_as_not_trusted_and_still_rejected(monkeypatch, capsys):
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
    ok = g.visitor_key(FakeRequest({"x-cta-visitor": IP, "x-cta-proxy-secret": SECRET}))
    assert ok == g.tag(IP) and ok != conn


def cfg_guard_guard():
    from cta.api.guard import Guard

    return Guard({"disabled": False, "rate_limit_max_keys": 100}, proxy_secret=SECRET, ip_salt=SALT)


def key_for(g, **headers):
    return g.visitor_key(FakeRequest({"x-cta-proxy-secret": SECRET, **headers}))


def test_x_cta_visitor_is_the_visitor_even_when_x_real_ip_changes():
    g = cfg_guard_guard()
    a = key_for(g, **{"x-cta-visitor": "203.0.113.9", "x-real-ip": "198.51.100.1"})
    b = key_for(g, **{"x-cta-visitor": "203.0.113.9", "x-real-ip": "198.51.100.2"})
    other = key_for(g, **{"x-cta-visitor": "203.0.113.10", "x-real-ip": "198.51.100.1"})
    assert a == b and a != other


def test_an_invalid_x_cta_visitor_falls_back_to_x_real_ip():
    g = cfg_guard_guard()
    assert key_for(g, **{"x-cta-visitor": "junk", "x-real-ip": IP}) == g.tag(IP)
