import json
from urllib.parse import parse_qs

import httpx
import pytest

from cta.crawl.catalog import RuleResolver, collect, fetch_all_courses, keep_departments
from cta.crawl.fetcher import FetchBlocked
from cta.settings import load_sources
from tests.conftest import FIXTURES

CFG = {**load_sources()["catalog_api"], "page_size": 4}  # 6 courses -> 2 pages
COURSES = json.loads((FIXTURES / "catalog_courses.json").read_text())["data"]
RULES = json.loads((FIXTURES / "catalog_rules.json").read_text())


@pytest.fixture
def api(make_fetcher):
    """Fetcher over a fake catalog API. `calls` lists the (method, path+query) it received."""
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.method == "POST":
            q = parse_qs(request.url.query.decode())
            skip, limit = int(q["skip"][0]), int(q["limit"][0])
            body = {"listLength": len(COURSES), "skip": skip, "limit": limit,
                    "data": COURSES[skip : skip + limit]}  # fmt: skip
            return httpx.Response(200, json=body)
        rule_id = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=RULES.get(rule_id, {"data": {}}))

    fetcher, store = make_fetcher(handler, hosts=("app.coursedog.com",))
    return fetcher, calls


def test_fetch_all_courses_pages_through_everything(api):
    fetcher, _ = api
    download = fetch_all_courses(fetcher, CFG)
    assert download.total_before == download.total_after == 6
    assert [c["code"] for c in download.courses] == [c["code"] for c in COURSES]


def test_keep_departments_keeps_cross_listed_courses_separate():
    kept = keep_departments(COURSES, {"CST-NYT", "MATH-NYT", "EET-NYT", "DENT-NYT"})
    codes = [c["code"] for c in kept]
    assert codes == ["CST 1101", "CST 2201", "EET 3672", "MATH 1101"]
    assert "CET 3672" not in codes  # other department, never merged into EET 3672


def test_rule_resolver_makes_one_call_per_unique_id(api, tmp_path):
    fetcher, calls = api
    resolver = RuleResolver(fetcher, CFG, tmp_path / "cache.json")
    for _ in range(3):
        assert resolver.resolve("100002")["text"].startswith("Prerequisite: CST 1101")
    assert resolver.calls == 1
    resolver.save()
    reloaded = RuleResolver(fetcher, CFG, tmp_path / "cache.json")
    reloaded.resolve("100002")
    assert reloaded.calls == 0


def test_unknown_rule_returns_none_and_is_not_guessed(api, tmp_path):
    fetcher, _ = api
    assert RuleResolver(fetcher, CFG, tmp_path / "c.json").resolve("999999") is None


def test_collect_writes_one_record_per_kept_course(api, tmp_path):
    fetcher, _ = api
    cfg = {**CFG, "departments": [{"id": "CST-NYT"}, {"id": "MATH-NYT"}, {"id": "EET-NYT"}]}
    summary = collect(fetcher, cfg, tmp_path / "processed")
    assert summary["counts_per_department"] == {"CST-NYT": 2, "EET-NYT": 1, "MATH-NYT": 1}
    files = sorted((tmp_path / "processed" / "courses").rglob("*.json"))
    assert len(files) == 4
    rec = json.loads(next(f for f in files if "EET-3672" in f.name).read_text())
    assert rec["prerequisite_text"] == "Prerequisite: EET 2101 and MATH 1101."
    assert rec["credits"] == 3 and rec["status"] == "Active"
    math = json.loads(next(f for f in files if "MATH-1101" in f.name).read_text())
    assert math["rule_id"] is None and math["prerequisite_text"] is None


def test_collect_stops_if_robots_disallows_api(make_fetcher, tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /api/\n")
        raise AssertionError("API must not be called")

    fetcher, _ = make_fetcher(handler, hosts=("app.coursedog.com",))
    with pytest.raises(FetchBlocked):
        collect(fetcher, CFG, tmp_path)
