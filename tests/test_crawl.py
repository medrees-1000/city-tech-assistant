"""The crawler: the polite fetcher (rate limit, robots.txt, redirects, raw store, fetch log), the
catalog collector and the office/department page crawl. No network: fake clock and fake HTTP.
"""

import hashlib
import json
from urllib.parse import parse_qs

import httpx
import pytest

from cta.crawl.catalog import (
    RuleResolver,
    collect,
    fetch_all_courses,
    keep_departments,
    prereq_style,
    rebuild_from_raw,
)
from cta.crawl.fetcher import FetchBlocked, normalize_url
from cta.crawl.pages import crawl_pages, page_targets, write_manifest
from cta.settings import load_sources
from tests.conftest import FIXTURES, UA, fixture_bytes

# ---- from test_fetcher.py ----

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


# ---- from test_catalog.py ----

CFG = {**load_sources()["catalog_api"], "page_size": 4}  # 11 courses -> 3 pages
COURSES = json.loads((FIXTURES / "catalog_page.json").read_text())["data"]
RULES = json.loads((FIXTURES / "catalog_rules.json").read_text())["data"]
PILOT = {"CST-NYT", "MATH-NYT", "EET-NYT", "DENT-NYT"}
PILOT_CFG = {**CFG, "departments": [{"id": d} for d in sorted(PILOT)]}


@pytest.fixture
def api(make_fetcher):
    """Fetcher over a fake catalog API serving the real fixtures. `calls` records requests."""
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
        return httpx.Response(
            200, json={"data": {rule_id: RULES[rule_id]} if rule_id in RULES else {}}
        )

    fetcher, store = make_fetcher(handler, hosts=("app.coursedog.com",))
    return fetcher, store, calls


def test_fetch_all_courses_pages_through_everything(api):
    fetcher, _, calls = api
    download = fetch_all_courses(fetcher, CFG)
    assert download.total_before == download.total_after == len(COURSES)
    assert [c["code"] for c in download.courses] == [c["code"] for c in COURSES]
    assert sum(m == "POST" for m, _ in calls) == 4  # 3 pages + the final total check


def test_keep_departments_drops_other_departments():
    codes = [c["code"] for c in keep_departments(COURSES, PILOT)]
    assert codes == [
        "CST 1101",
        "CST 2402",
        "CST 2406",
        "CST 4900",
        "DEN 2315",
        "EET 3672",
        "MAT 1190",
        "MAT 2540",
        "MST 1101",
    ]


def test_cross_listed_courses_stay_separate_records():
    kept = keep_departments(COURSES, PILOT | {"CET-NYT", "MET-NYT"})
    trio = {c["code"]: c for c in kept if c["code"].endswith("3672")}
    assert set(trio) == {"EET 3672", "CET 3672", "MECH 3672"}
    assert len({c["departments"][0]["id"] for c in trio.values()}) == 3
    assert len({c["description"] for c in trio.values()}) == 1  # same text, never merged


def test_rule_resolver_makes_one_call_per_unique_id(api, tmp_path):
    fetcher, _, calls = api
    resolver = RuleResolver(fetcher, CFG, tmp_path / "cache.json")
    for _ in range(3):
        assert resolver.resolve("027626")["text"] == "PRE: EET 3122"
    assert resolver.calls == 1
    resolver.save()
    reloaded = RuleResolver(fetcher, CFG, tmp_path / "cache.json")
    reloaded.resolve("027626")
    assert reloaded.calls == 0


def test_unknown_rule_returns_none_and_is_not_guessed(api, tmp_path):
    fetcher, _, _ = api
    assert RuleResolver(fetcher, CFG, tmp_path / "c.json").resolve("999999") is None


def test_full_rule_response_has_no_structured_logic():
    """Finding: shorthand rules are flat text. If the API ever adds logic fields, this fails."""
    rule = json.loads((FIXTURES / "rule_shorthand_full.json").read_text())["data"]["014763"]
    assert set(rule) == {
        "_id", "academicPlan", "academicSubPlan", "catalogDisplayName", "code", "createdAt",
        "description", "descriptionLong", "descriptionShort", "displayName",
        "effectiveStartDate", "id", "institutionId", "notes", "status", "updatedAt",
    }  # fmt: skip
    assert rule["descriptionLong"] == "PRE_CST3500_CST3600"


def test_prereq_style():
    assert prereq_style(None, None) == "none"
    assert prereq_style("014763", None) == "unresolved"
    assert prereq_style("014763", "PRE_CST3500_CST3600") == "shorthand"
    assert prereq_style("014763", "PRE_CST2309") == "shorthand"
    assert prereq_style("1", "Prerequisite: CST1201 & CST 1204") == "text"
    assert prereq_style("1", "PRE: EET 3122") == "text"


def records_by_code(out_dir):
    files = (out_dir / "courses").rglob("*.json")
    return {r["code"]: r for r in (json.loads(f.read_text()) for f in files)}


def test_collect_writes_one_record_per_kept_course(api, tmp_path):
    fetcher, _, _ = api
    summary = collect(fetcher, PILOT_CFG, tmp_path / "processed")
    assert summary["counts_per_department"] == {
        "CST-NYT": 5, "DENT-NYT": 1, "EET-NYT": 1, "MATH-NYT": 2,
    }  # fmt: skip
    assert summary["prereq_styles"] == {"none": 1, "shorthand": 2, "text": 6}
    recs = records_by_code(tmp_path / "processed")
    assert recs["EET 3672"]["prerequisite_text"] == "PRE: EET 3122"
    assert recs["CST 4900"]["prerequisite_text"] == "PRE_CST3500_CST3600"
    assert recs["CST 4900"]["prereq_style"] == "shorthand"
    assert recs["CST 1101"]["rule_id"] is None and recs["CST 1101"]["prereq_style"] == "none"
    assert recs["CST 2402"]["credits"] == 3 and recs["CST 2402"]["status"] == "Active"


def test_rebuild_from_raw_matches_the_live_run_without_network(api, tmp_path):
    fetcher, store, calls = api
    out = tmp_path / "processed"
    collect(fetcher, PILOT_CFG, out)
    live = records_by_code(out)
    for f in (out / "courses").rglob("*.json"):
        f.unlink()
    requests_before = len(calls)
    rebuild_from_raw(PILOT_CFG, store.root, out)
    assert len(calls) == requests_before
    assert records_by_code(out) == live


def test_extra_fields_come_from_raw_data(api, tmp_path):
    fetcher, _, _ = api
    collect(fetcher, PILOT_CFG, tmp_path / "processed")
    recs = records_by_code(tmp_path / "processed")
    wi = recs["MAT 2540"]  # liberal arts + writing intensive
    assert wi["liberal_arts"] is True and wi["writing_intensive"] is True
    assert any(a.startswith("WRIC") for a in wi["catalog_attributes"])
    assert recs["CST 2402"]["liberal_arts"] is False
    assert recs["CST 2402"]["writing_intensive"] is False
    assert recs["CST 2402"]["catalog_attributes"] == []
    # liberal arts, but not writing intensive: the two flags are independent
    cst1101 = recs["CST 1101"]
    assert cst1101["liberal_arts"] is True and cst1101["writing_intensive"] is False
    assert cst1101["catalog_attributes"] == ["MEBU - ME_BUSI_1 (Intro Computer Info Sys & Tech)"]
    assert recs["CST 4900"]["contact_hours"] == {"value": 9, "operator": ""}
    assert recs["CST 4900"]["credit_hours"] == {"min": 3, "max": 3, "operator": ""}
    assert all(r["pathways_category"] for r in recs.values())
    assert all(r["description"] for r in recs.values())


def test_pathways_category_is_the_api_value_unchanged(api, tmp_path):
    fetcher, _, _ = api
    collect(fetcher, PILOT_CFG, tmp_path / "processed")
    recs = records_by_code(tmp_path / "processed")
    assert recs["CST 2406"]["pathways_category"] == "Regular Non-Liberal Arts"
    assert recs["CST 1101"]["pathways_category"] == "Regular Liberal Arts"
    assert recs["MAT 2540"]["pathways_category"] == "RLA_FC_ScientificWorld"  # a code, not renamed
    # not inferred from the liberal arts flag: the API value decides
    raw = {c["code"]: c for c in COURSES}
    for code, rec in recs.items():
        assert rec["pathways_category"] == raw[code]["requirementDesignation"]


def test_pathways_label_comes_from_catalog_requirement_designation(api, tmp_path):
    fetcher, _, _ = api
    collect(fetcher, PILOT_CFG, tmp_path / "processed")
    recs = records_by_code(tmp_path / "processed")
    assert recs["MAT 2540"]["pathways_category"] == "RLA_FC_ScientificWorld"
    assert recs["MAT 2540"]["pathways_label"] == "Flexible Core - Scientific World"
    assert recs["MAT 1190"]["pathways_label"] == (
        "Required Core - Mathematical&QuantitativeReasoning"
    )
    # courses without the raw key stay null; nothing is derived from pathways_category
    assert recs["CST 2406"]["pathways_label"] is None
    assert recs["CST 1101"]["pathways_label"] is None
    for code, rec in recs.items():
        raw = next(c for c in COURSES if c["code"] == code)
        assert rec["pathways_label"] == raw["customFields"].get("catalogRequirementDesignation")


def test_legacy_prefix_courses_are_kept_and_flagged(api, tmp_path):
    fetcher, _, _ = api
    collect(fetcher, PILOT_CFG, tmp_path / "processed")
    recs = records_by_code(tmp_path / "processed")
    assert recs["MST 1101"]["legacy_prefix"] is True  # Active in the catalog: kept, not dropped
    assert recs["MST 1101"]["status"] == "Active"
    assert [c for c, r in recs.items() if r["legacy_prefix"]] == ["MST 1101"]


def test_list_request_asks_for_the_pathways_columns():
    columns = CFG["columns"].split(",")
    assert "requirementDesignation" in columns
    assert "customFields.catalogRequirementDesignation" in columns


def test_collect_stops_if_robots_disallows_api(make_fetcher, tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /api/\n")
        raise AssertionError("API must not be called")

    fetcher, _ = make_fetcher(handler, hosts=("app.coursedog.com",))
    with pytest.raises(FetchBlocked):
        collect(fetcher, CFG, tmp_path)


# ---- from test_pages_crawl.py ----

SOURCES = {
    "office_pages": [
        "https://www.citytech.cuny.edu/advisement/planner.aspx",
        "https://www.citytech.cuny.edu/bursar/refund-policy.aspx",
    ],
    "department_pages": {"CST-NYT": ["https://www.citytech.cuny.edu/computer-systems/"]},
}


def handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/robots.txt":
        return httpx.Response(404)
    if path == "/advisement/planner.aspx":
        return httpx.Response(
            302, headers={"location": "http://www.citytech.cuny.edu/advisement/p2.aspx"}
        )
    if path == "/advisement/p2.aspx":
        return httpx.Response(
            200, content=fixture_bytes("page.html"), headers={"content-type": "text/html"}
        )
    if path == "/computer-systems/":
        return httpx.Response(
            200, content=b"<html>root</html>", headers={"content-type": "text/html"}
        )
    return httpx.Response(404)


def test_page_targets_label_office_and_department():
    targets = page_targets(SOURCES)
    assert [(t.kind, t.owner) for t in targets] == [
        ("office", "advisement"),
        ("office", "bursar"),
        ("department", "CST-NYT"),
    ]


def test_sources_yaml_has_63_pages():
    targets = page_targets(load_sources())
    assert sum(t.kind == "office" for t in targets) == 28  # 24 + 4 advisement pages added later
    assert sum(t.kind == "department" for t in targets) == 35
    assert all(t.url.startswith("https://www.citytech.cuny.edu/") for t in targets)


def test_crawl_records_redirects_and_failures_without_stopping(make_fetcher, tmp_path):
    fetcher, store = make_fetcher(handler)
    results = crawl_pages(fetcher, page_targets(SOURCES))
    planner, bursar, root = results
    assert planner.status == 200 and planner.final_url.endswith("/advisement/p2.aspx")
    assert bursar.status == 404 and bursar.saved_as is None
    assert root.status == 200 and root.content_hash
    write_manifest(results, tmp_path / "manifest.json")
    assert len(json.loads((tmp_path / "manifest.json").read_text())) == 3


def test_blocked_page_is_recorded_not_raised(make_fetcher):
    fetcher, _ = make_fetcher(handler, hosts=("other.example.com",))
    results = crawl_pages(fetcher, page_targets(SOURCES))
    assert all(r.status is None and "FetchBlocked" in r.error for r in results)
