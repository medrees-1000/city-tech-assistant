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


def post(c, secret=SECRET, ip=IP, **extra):
    headers = dict(extra)
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
    assert f'"visitor_tag": "{key[:6]}"' in out  # only the first 6 characters of the key
    (ln,) = [json.loads(x) for x in out.splitlines() if x.startswith('{"event": "ask"')]
    assert set(ln) == {"event", "request_id", "proxy_required", "proxy_trusted",
                       "forwarded_present", "forwarded_family", "visitor_seen_before",
                       "visitor_tag", "addr_tags"}  # fmt: skip
    assert ln["forwarded_family"] == "ipv4"
    flags = set(ln) - {"event", "request_id", "forwarded_family", "visitor_tag", "addr_tags"}
    assert all(isinstance(ln[k], bool) for k in flags)


def test_the_family_label_tells_ipv4_from_ipv6_from_nothing(monkeypatch, capsys):
    c = app(monkeypatch)
    post(c, ip="203.0.113.7")
    post(c, ip="2001:db8::1")
    post(c, ip=None)
    post(c, ip="junk")
    assert [ln["forwarded_family"] for ln in lines(capsys)] == ["ipv4", "ipv6", "none", "none"]


def test_the_visitor_tag_is_six_hex_characters_stable_per_visitor_and_different_between_visitors(
    monkeypatch, capsys
):
    c = app(monkeypatch)
    post(c, ip="203.0.113.1")
    post(c, ip="203.0.113.1")
    post(c, ip="203.0.113.2")
    a, b, other = (ln["visitor_tag"] for ln in lines(capsys))
    assert len(a) == 6 and all(ch in "0123456789abcdef" for ch in a)
    assert a == b and a != other


def post_visitor(c, real_ip, visitor):
    headers = {"x-cta-visitor": visitor} if visitor is not None else {}
    return post(c, ip=real_ip, **headers)


def test_x_cta_visitor_is_the_visitor_when_trusted_even_if_x_real_ip_changes(monkeypatch, capsys):
    c = app(monkeypatch)
    for node in ("198.51.100.1", "198.51.100.2", "198.51.100.3"):  # a changing hop address
        post_visitor(c, node, "203.0.113.9")
    first, second, third = lines(capsys)
    assert first["visitor_seen_before"] is False
    assert second["visitor_seen_before"] is third["visitor_seen_before"] is True
    assert first["visitor_tag"] == second["visitor_tag"] == third["visitor_tag"]


def test_an_invalid_x_cta_visitor_falls_back_to_x_real_ip(monkeypatch, capsys):
    c = app(monkeypatch)
    post_visitor(c, "203.0.113.5", "not-an-ip")
    post_visitor(c, "203.0.113.5", None)
    a, b = lines(capsys)
    assert a["visitor_tag"] == b["visitor_tag"] and b["visitor_seen_before"] is True


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


def test_addr_tags_hold_six_hex_characters_or_null_and_no_raw_value(monkeypatch, capsys):
    c = app(monkeypatch)
    post(c, **{"x-forwarded-for": "198.51.100.77, 10.0.0.1", "x-cta-visitor": "203.0.113.9"})
    out = capsys.readouterr().out
    (ln,) = [json.loads(x) for x in out.splitlines() if x.startswith('{"event": "ask"')]
    tags = ln["addr_tags"]
    assert set(tags) == {"x-real-ip", "x-forwarded-for", "x-vercel-forwarded-for",
                         "x-vercel-proxied-for", "x-cta-visitor"}  # fmt: skip
    assert tags["x-vercel-forwarded-for"] is None and tags["x-vercel-proxied-for"] is None
    for name in ("x-real-ip", "x-forwarded-for", "x-cta-visitor"):
        assert len(tags[name]) == 6 and all(ch in "0123456789abcdef" for ch in tags[name])
    for raw in (SECRET, SALT, IP, "198.51.100.77", "203.0.113.9", "10.0.0.1"):
        assert raw not in out
