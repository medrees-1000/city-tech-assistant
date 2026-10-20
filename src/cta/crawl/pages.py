"""Crawl the office and department pages listed in config/sources.yaml (raw HTML only).

Run: uv run python -m cta.crawl.pages
Parsing is a separate step (cta.parse). The manifest written here says what happened per page.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

from cta.crawl.fetcher import FetchBlocked, Fetcher, RawStore, normalize_url, utc_now
from cta.settings import ROOT, build_user_agent, load_sources


@dataclass
class PageTarget:
    url: str
    kind: str  # "office" or "department"
    owner: str  # office folder (registrar, bursar, ...) or department id (CST-NYT, ...)


@dataclass
class PageResult:
    url: str
    kind: str
    owner: str
    status: int | None  # None when blocked or the request failed
    final_url: str | None
    saved_as: str | None
    content_hash: str | None
    fetched_at: str
    error: str = ""


def page_targets(sources: dict) -> list[PageTarget]:
    targets = []
    for url in sources["office_pages"]:
        office = url.split("citytech.cuny.edu/")[1].split("/")[0]
        targets.append(PageTarget(normalize_url(url), "office", office))
    for dept, urls in sources["department_pages"].items():
        targets.extend(PageTarget(normalize_url(u), "department", dept) for u in urls)
    return targets


def crawl_pages(fetcher: Fetcher, targets: list[PageTarget]) -> list[PageResult]:
    results = []
    for t in targets:
        base = dict(url=t.url, kind=t.kind, owner=t.owner, fetched_at=utc_now())
        try:
            r = fetcher.fetch(t.url)
        except (FetchBlocked, httpx.HTTPError) as exc:
            error = f"{type(exc).__name__}: {exc}"
            results.append(PageResult(**base, status=None, final_url=None, saved_as=None,
                                      content_hash=None, error=error))  # fmt: skip
            continue
        results.append(PageResult(**base, status=r.status, final_url=r.final_url,
                                  saved_as=r.saved_as, content_hash=r.content_hash))  # fmt: skip
    return results


def write_manifest(results: list[PageResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(r) for r in results], indent=1), encoding="utf-8")


def main() -> None:
    sources = load_sources()
    crawl = sources["crawl"]
    fetcher = Fetcher(
        httpx.Client(timeout=30),
        RawStore(ROOT / "data" / "raw"),
        build_user_agent(sources),
        set(sources["allowed_hosts"]),
        min_interval=crawl["min_interval_seconds"],
        max_redirects=crawl["max_redirects"],
    )
    targets = page_targets(sources)
    results = crawl_pages(fetcher, targets)
    write_manifest(results, ROOT / "data" / "processed" / "pages_manifest.json")
    ok = sum(r.status == 200 for r in results)
    print(f"{len(results)} pages, {ok} returned 200")
    for r in results:
        if r.status != 200:
            print("  not 200:", r.url, r.status, r.error)


if __name__ == "__main__":
    main()
