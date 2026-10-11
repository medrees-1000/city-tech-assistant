"""Catalog collector: page through the course search API, resolve rule IDs, write course records.

Run: uv run python -m cta.crawl.catalog
"""

import json
import re
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx

from cta.crawl.fetcher import Fetcher
from cta.crawl.store import RawStore, utc_now
from cta.settings import ROOT, build_user_agent, load_sources

# Same body the catalog website sends (see scripts/test_catalog_api.py).
SEARCH_BODY = {
    "condition": "AND",
    "filters": [
        {
            "id": "K87u6eND",
            "condition": "and",
            "filters": [
                {"id": "status-course", "condition": "field", "name": "status",
                 "inputType": "select", "group": "course", "type": "is",
                 "value": "Active", "customField": False},
                {"id": "catalogPrint-course", "condition": "field", "name": "catalogPrint",
                 "inputType": "boolean", "group": "course", "type": "is",
                 "value": True, "customField": False},
            ],
        }
    ],
}  # fmt: skip


def api_headers(cfg: dict) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Origin": cfg["origin"],
        "Referer": cfg["origin"] + "/",
        "x-requested-with": "catalog",
    }


def search_url(cfg: dict, skip: int, limit: int) -> str:
    return (
        f"{cfg['base_url']}{cfg['search_path']}?catalogId={cfg['catalog_id']}"
        f"&skip={skip}&limit={limit}&orderBy=code&columns={cfg['columns']}"
        f"&effectiveDatesRange={cfg['effective_date']},{cfg['effective_date']}"
        "&ignoreEffectiveDating=false"
    )


def rule_url(cfg: dict, rule_id: str) -> str:
    path = cfg["rule_path"].format(rule_id=rule_id)
    return f"{cfg['base_url']}{path}?returnFields={cfg['rule_return_fields']}"


def _get_json(fetcher: Fetcher, url: str, cfg: dict, body: object | None = None) -> dict:
    method = "POST" if body is not None else "GET"
    result = fetcher.fetch(url, method=method, json=body, headers=api_headers(cfg))
    if result.status != 200:
        raise RuntimeError(f"{method} {url} returned {result.status}")
    return json.loads(result.content)


@dataclass
class CourseDownload:
    total_before: int
    total_after: int
    courses: list[dict]


def fetch_all_courses(fetcher: Fetcher, cfg: dict) -> CourseDownload:
    """Page with skip until every course is downloaded; read the total before and after."""
    limit = cfg["page_size"]
    courses: list[dict] = []
    total_before = None
    skip = 0
    while total_before is None or skip < total_before:
        page = _get_json(fetcher, search_url(cfg, skip, limit), cfg, SEARCH_BODY)
        if total_before is None:
            total_before = page["listLength"]
        if not page["data"]:
            break
        courses.extend(page["data"])
        skip += limit
    after = _get_json(fetcher, search_url(cfg, 0, 1), cfg, SEARCH_BODY)
    return CourseDownload(total_before or 0, after["listLength"], courses)


def keep_departments(courses: list[dict], dept_ids: set[str]) -> list[dict]:
    """Keep courses with at least one department in dept_ids. Cross-listed ones stay separate."""
    return [c for c in courses if any(d["id"] in dept_ids for d in c.get("departments", []))]


class RuleResolver:
    """Look up each rule ID once; results are cached in a JSON file between runs."""

    def __init__(self, fetcher: Fetcher, cfg: dict, cache_path: Path):
        self.fetcher = fetcher
        self.cfg = cfg
        self.cache_path = cache_path
        self.cache: dict[str, dict] = (
            json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        )
        self.calls = 0

    def resolve(self, rule_id: str) -> dict | None:
        """Return {"code", "text"} for a rule ID, or None if the lookup has no answer."""
        if rule_id not in self.cache:
            data = _get_json(self.fetcher, rule_url(self.cfg, rule_id), self.cfg)["data"]
            self.calls += 1
            rule = data.get(rule_id)
            text = rule and (rule.get("descriptionLong") or rule.get("catalogDisplayName"))
            self.cache[rule_id] = {"code": rule_id, "text": text} if text else {"code": rule_id}
        entry = self.cache[rule_id]
        return entry if entry.get("text") else None

    def save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, indent=1, sort_keys=True), "utf-8")


# Rule text like PRE_CST3500_CST3600: the catalog stores a code, not readable text, and the rule
# response has no structured fields to build text from. Kept as is and marked.
SHORTHAND = re.compile(r"[A-Z]+(?:_[A-Z0-9]+)+")


def prereq_style(rule_id: str | None, text: str | None) -> str:
    """ "none" (no rule), "unresolved" (rule without text), "shorthand" or "text"."""
    if not rule_id:
        return "none"
    if not text:
        return "unresolved"
    return "shorthand" if SHORTHAND.fullmatch(text) else "text"


def to_record(course: dict, dept_ids: set[str], rule_text: str | None, fetched_at: str) -> dict:
    kept = [d for d in course["departments"] if d["id"] in dept_ids]
    credits = course.get("credits") or {}
    return {
        "code": course.get("code"),
        "title": course.get("name"),
        "description": course.get("description"),
        "credits": credits.get("numberOfCredits"),
        "department": kept[0]["id"],
        "department_name": kept[0].get("name"),
        "all_departments": [d["id"] for d in course["departments"]],
        "status": course.get("status"),
        "subject_code": course.get("subjectCode"),
        "course_number": course.get("courseNumber"),
        "course_group_id": course.get("courseGroupId"),
        "rule_id": course.get("requirementGroup") or None,
        "prerequisite_text": rule_text,
        "prereq_style": prereq_style(course.get("requirementGroup") or None, rule_text),
        "source": "catalog_api",
        "fetched_at": fetched_at,
    }


def write_records(records: list[dict], out_dir: Path) -> None:
    for rec in records:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", rec["code"] or "unknown").strip("-")
        path = out_dir / "courses" / rec["department"] / f"{slug}_{rec['course_group_id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")


def collect(fetcher: Fetcher, cfg: dict, out_dir: Path) -> dict:
    """Download, filter, resolve rules, write records. Returns the run summary."""
    dept_ids = {d["id"] for d in cfg["departments"]}
    download = fetch_all_courses(fetcher, cfg)
    kept = keep_departments(download.courses, dept_ids)
    resolver = RuleResolver(fetcher, cfg, out_dir / "rules_cache.json")
    fetched_at = utc_now()
    try:
        records = build_records(kept, dept_ids, resolver.resolve, fetched_at)
    finally:
        resolver.save()
    write_records(records, out_dir)
    return write_summary(download, records, resolver, out_dir, fetched_at)


def build_records(
    kept: list[dict], dept_ids: set[str], resolve: Callable[[str], dict | None], fetched_at: str
) -> list[dict]:
    records = []
    for course in kept:
        rule_id = course.get("requirementGroup")
        rule = resolve(rule_id) if rule_id else None
        records.append(to_record(course, dept_ids, rule["text"] if rule else None, fetched_at))
    return records


def load_saved_courses(raw_root: Path, cfg: dict) -> list[dict]:
    """Read the course pages from the saved raw JSON (via the fetch log), in skip order."""
    pages: dict[int, str] = {}
    for row in RawStore(raw_root).read_log():
        url = row["url"]
        if row["method"] != "POST" or row["status"] != 200 or "/courses/search/" not in url:
            continue
        query = parse_qs(urlsplit(url).query)
        if query["limit"] == [str(cfg["page_size"])]:
            pages[int(query["skip"][0])] = row["saved_as"]  # a later fetch replaces an earlier one
    courses: list[dict] = []
    for skip in sorted(pages):
        page = json.loads((raw_root / pages[skip]).read_text(encoding="utf-8"))
        courses.extend(page["data"])
    return courses


def rebuild_from_raw(cfg: dict, raw_root: Path, out_dir: Path) -> dict:
    """Recreate the processed records from saved raw data and the rule cache. No network."""
    dept_ids = {d["id"] for d in cfg["departments"]}
    summary_path = out_dir / "catalog_run.json"
    old = json.loads(summary_path.read_text(encoding="utf-8"))
    courses = load_saved_courses(raw_root, cfg)
    if len(courses) != old["downloaded"]:
        raise RuntimeError(
            f"saved raw has {len(courses)} courses, last run had {old['downloaded']}"
        )
    cache = json.loads((out_dir / "rules_cache.json").read_text(encoding="utf-8"))

    def lookup(rule_id: str) -> dict | None:
        entry = cache[rule_id]  # KeyError means the rule was never fetched: do not guess
        return entry if entry.get("text") else None

    kept = keep_departments(courses, dept_ids)
    records = build_records(kept, dept_ids, lookup, old["fetched_at"])
    write_records(records, out_dir)
    download = CourseDownload(old["total_before"], old["total_after"], courses)
    stub = SimpleNamespace(calls=0)
    return write_summary(download, records, stub, out_dir, old["fetched_at"])


def write_summary(download, records, resolver, out_dir: Path, fetched_at: str) -> dict:
    summary_path = out_dir / "catalog_run.json"
    previous = {}
    if summary_path.exists():
        previous = json.loads(summary_path.read_text("utf-8")).get("counts_per_department", {})
    counts: dict[str, int] = {}
    for rec in records:
        counts[rec["department"]] = counts.get(rec["department"], 0) + 1
    summary = {
        "prereq_styles": dict(sorted(Counter(r["prereq_style"] for r in records).items())),
        "fetched_at": fetched_at,
        "total_before": download.total_before,
        "total_after": download.total_after,
        "downloaded": len(download.courses),
        "kept": len(records),
        "counts_per_department": dict(sorted(counts.items())),
        "previous_counts_per_department": previous,
        "rule_lookups_this_run": resolver.calls,
        "all_codes": sorted({c["code"] for c in download.courses if c.get("code")}),
    }
    summary_path.write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


def main() -> None:
    sources = load_sources()
    cfg = sources["catalog_api"]
    if "--from-raw" in sys.argv:
        out = rebuild_from_raw(cfg, ROOT / "data" / "raw", ROOT / "data" / "processed")
        print({k: v for k, v in out.items() if k != "all_codes"})
        return
    crawl = sources["crawl"]
    client = httpx.Client(timeout=30)
    fetcher = Fetcher(
        client,
        RawStore(ROOT / "data" / "raw"),
        build_user_agent(sources),
        set(sources["allowed_hosts"]),
        min_interval=crawl["min_interval_seconds"],
        max_redirects=crawl["max_redirects"],
    )
    summary = collect(fetcher, cfg, ROOT / "data" / "processed")
    print({k: v for k, v in summary.items() if k != "all_codes"})


if __name__ == "__main__":
    main()
