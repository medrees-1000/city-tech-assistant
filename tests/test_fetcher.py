import hashlib

import httpx
import pytest

from cta.crawl.fetcher import FetchBlocked
from cta.crawl.urls import normalize_url
from tests.conftest import UA, fixture_bytes

HOST = "https://www.citytech.cuny.edu"


def site(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/robots.txt":
        return httpx.Response(200, content=fixture_bytes("robots_disallow.txt"))
    if path == "/advisement/planner.aspx":
        return httpx.Response(
            302, headers={"location": "http://www.citytech.cuny.edu/advisement/p2.aspx"}
        )
    if path == "/advisement/p2.aspx":
        return httpx.Response(
            200, content=fixture_bytes("page.html"), headers={"content-type": "text/html"}
        )
    if path == "/offsite":
        return httpx.Response(302, headers={"location": "https://evil.example.com/x"})
    return httpx.Response(404)


def test_normalize_url_upgrades_http_and_drops_fragment():
    assert normalize_url("http://WWW.CityTech.cuny.edu:80/a.aspx#top") == (
        "https://www.citytech.cuny.edu/a.aspx"
    )


def test_follows_same_host_redirect_and_normalizes_to_https(make_fetcher):
    fetcher, store = make_fetcher(site)
    result = fetcher.fetch(f"{HOST}/advisement/planner.aspx")
    assert result.status == 200
    assert result.final_url == f"{HOST}/advisement/p2.aspx"
    assert result.content_hash == hashlib.sha256(fixture_bytes("page.html")).hexdigest()


def test_raw_response_saved_untouched(make_fetcher):
    fetcher, store = make_fetcher(site)
    result = fetcher.fetch(f"{HOST}/advisement/planner.aspx")
    assert (store.root / result.saved_as).read_bytes() == fixture_bytes("page.html")


def test_fetch_log_has_every_request(make_fetcher):
    fetcher, store = make_fetcher(site)
    fetcher.fetch(f"{HOST}/advisement/planner.aspx")
    rows = store.read_log()
    assert [(r["url"].rsplit("/", 1)[-1], r["status"]) for r in rows] == [
        ("robots.txt", 200),
        ("planner.aspx", 302),
        ("p2.aspx", 200),
    ]
    assert all(r["timestamp"] and r["content_hash"] for r in rows)
    assert rows[1]["note"].startswith("redirect to")


def test_redirect_to_other_host_is_blocked_and_logged(make_fetcher):
    fetcher, store = make_fetcher(site)
    with pytest.raises(FetchBlocked):
        fetcher.fetch(f"{HOST}/offsite")
    assert "redirect to another host" in store.read_log()[-1]["note"]


def test_robots_disallow_is_respected(make_fetcher):
    fetcher, store = make_fetcher(site)
    with pytest.raises(FetchBlocked):
        fetcher.fetch(f"{HOST}/academics/departments-html/x.aspx")
    assert store.read_log()[-1]["note"] == "blocked: disallowed by robots.txt"


def test_robots_404_means_allowed(make_fetcher):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, content=b"ok", headers={"content-type": "text/html"})

    fetcher, store = make_fetcher(handler)
    assert fetcher.fetch(f"{HOST}/academics/departments-html/x.aspx").status == 200
    assert "allow all" in store.read_log()[0]["note"]


def test_robots_fetched_once_per_host(make_fetcher):
    fetcher, store = make_fetcher(site)
    fetcher.fetch(f"{HOST}/advisement/p2.aspx")
    fetcher.fetch(f"{HOST}/advisement/p2.aspx")
    assert sum(r["url"].endswith("/robots.txt") for r in store.read_log()) == 1


def test_host_not_in_allow_list_is_blocked(make_fetcher):
    fetcher, _ = make_fetcher(site)
    with pytest.raises(FetchBlocked):
        fetcher.fetch("https://example.com/")


def test_login_links_are_blocked(make_fetcher):
    fetcher, _ = make_fetcher(site)
    with pytest.raises(FetchBlocked):
        fetcher.fetch(f"{HOST}/student/login.aspx")


def test_one_request_per_second(make_fetcher, fake_time):
    fetcher, _ = make_fetcher(site)
    fetcher.fetch(f"{HOST}/advisement/planner.aspx")  # robots + 302 + 200 = 3 requests
    assert fake_time.now >= 2.0
    assert all(s == pytest.approx(1.0) for s in fake_time.sleeps)
    assert len(fake_time.sleeps) == 2


def test_sends_user_agent_and_no_cookies(make_fetcher):
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(404, headers={"set-cookie": "a=b"})
        return httpx.Response(200, content=b"x", headers={"set-cookie": "sid=1"})

    fetcher, _ = make_fetcher(handler)
    fetcher.fetch(f"{HOST}/a.aspx")
    fetcher.fetch(f"{HOST}/b.aspx")
    assert all(r.headers["user-agent"] == UA for r in seen)
    assert all("cookie" not in r.headers for r in seen)


def test_post_json_is_sent_and_saved(make_fetcher):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        assert request.method == "POST"
        return httpx.Response(
            200,
            json={"echo": request.content.decode()},
            headers={"content-type": "application/json"},
        )

    fetcher, store = make_fetcher(handler)
    result = fetcher.fetch(f"{HOST}/api?skip=0", method="POST", json={"a": 1})
    assert result.saved_as.endswith(".json")
