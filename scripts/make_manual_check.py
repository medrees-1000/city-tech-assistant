"""Write docs/manual-check-courses.md: 20 random courses for the owner's manual check.

Run: uv run python scripts/make_manual_check.py
Reads saved data only (data/processed and data/raw). No network.
"""

import random
from collections import defaultdict
from pathlib import Path

from cta.crawl.catalog import load_saved_courses
from cta.settings import ROOT, load_sources
from cta.validate.courses import load_records

SEED = 2026
TOTAL = 20
PER_DEPT = 3
CROSS_LISTED = 2
CATALOG = "https://citytech.catalog.cuny.edu/courses"


def cross_listed_twins(cfg: dict) -> dict[str, list[str]]:
    """code -> codes with the same description in a different department."""
    by_desc = defaultdict(list)
    for c in load_saved_courses(ROOT / "data" / "raw", cfg):
        if c.get("description"):
            by_desc[c["description"]].append((c["code"], c["departments"][0]["id"]))
    twins = {}
    for group in by_desc.values():
        for code, dept in group:
            others = [o for o, d in group if d != dept]
            if others:
                twins[code] = others
    return twins


def pick(records: list[dict], twins: dict[str, list[str]]) -> list[dict]:
    rng = random.Random(SEED)
    chosen = rng.sample([r for r in records if r["code"] in twins], CROSS_LISTED)
    for dept in sorted({r["department"] for r in records}):
        have = sum(r["department"] == dept for r in chosen)
        pool = [r for r in records if r["department"] == dept and r not in chosen]
        chosen += rng.sample(pool, max(0, PER_DEPT - have))
    rest = [r for r in records if r not in chosen]
    chosen += rng.sample(rest, TOTAL - len(chosen))
    return sorted(chosen, key=lambda r: (r["department"], r["code"]))


def cell(text: str | None) -> str:
    return " ".join((text or "").split()).replace("|", "\\|") or "(none)"


def main() -> None:
    cfg = load_sources()["catalog_api"]
    records = load_records(ROOT / "data" / "processed")
    twins = cross_listed_twins(cfg)
    rows = pick(records, twins)
    lines = [
        "# Manual check: courses",
        "",
        "Compare each row with the live catalog page: code, title, credits and prerequisite text.",
        "Tick the last column when all four match, and note any difference below the table.",
        "",
        f"Sample: {len(rows)} random courses (seed {SEED}), at least {PER_DEPT} per department, "
        f"plus {CROSS_LISTED} cross-listed ones (same description, different department).",
        "Data is from the crawl of "
        f"{records[0]['fetched_at']}. Prerequisite text is shown exactly as the catalog rule returns it.",
        "",
        "Catalog page: the URL pattern in CLAUDE.md is `/courses/<courseGroupId>/<slug>`. The slug is",
        "not stored, so the links below use the courseGroupId only. They are NOT verified; if one does",
        "not open, search the code on https://citytech.catalog.cuny.edu/ instead.",
        "",
        "| # | Code | Dept | Title | Cr | Prerequisite text (as resolved) | Style | Cross-listed with | Page | OK |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        link = f"[{r['course_group_id']}]({CATALOG}/{r['course_group_id']})"
        cross = ", ".join(twins.get(r["code"], [])) or ""
        lines.append(
            f"| {i} | {r['code']} | {r['department']} | {cell(r['title'])} | {r['credits']} | "
            f"{cell(r['prerequisite_text'])} | {r['prereq_style']} | {cross} | {link} | [ ] |"
        )
    lines += ["", "## Differences found", "", "(none recorded yet)", ""]
    out = ROOT / "docs" / "manual-check-courses.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out} with {len(rows)} rows")


if __name__ == "__main__":
    main()
