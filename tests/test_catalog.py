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
from cta.crawl.fetcher import FetchBlocked
from cta.settings import load_sources
from tests.conftest import FIXTURES

CFG = {**load_sources()["catalog_api"], "page_size": 4}  # 10 courses -> 3 pages
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
        "CST-NYT": 4, "DENT-NYT": 1, "EET-NYT": 1, "MATH-NYT": 2,
    }  # fmt: skip
    assert summary["prereq_styles"] == {"none": 1, "shorthand": 2, "text": 5}
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


def test_list_request_asks_for_the_pathways_column():
    assert "requirementDesignation" in CFG["columns"].split(",")


def test_collect_stops_if_robots_disallows_api(make_fetcher, tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /api/\n")
        raise AssertionError("API must not be called")

    fetcher, _ = make_fetcher(handler, hosts=("app.coursedog.com",))
    with pytest.raises(FetchBlocked):
        collect(fetcher, CFG, tmp_path)
