import json

import httpx

from cta.crawl.pages import crawl_pages, page_targets, write_manifest
from cta.settings import load_sources
from tests.conftest import fixture_bytes

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


def test_sources_yaml_has_59_pages():
    targets = page_targets(load_sources())
    assert sum(t.kind == "office" for t in targets) == 24
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
