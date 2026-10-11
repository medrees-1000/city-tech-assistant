"""The list of indexable sections, used to pick gold_sources for eval questions.

A section is indexable when its record is `index: true`, the page was collected, and the section
itself is not `embed: false` (the PDF contact block). Contact blocks are not sections at all.
Built into docs/section-index.md by scripts/make_section_index.py. Nothing here is embedded.
"""

import json
from collections import Counter
from pathlib import Path


def heading_path(section: dict) -> str:
    """Parents then heading, outermost first ("Program > Requirements > General Education")."""
    names = [p["heading"] for p in section["parents"] if p["heading"]]
    if section["heading"]:
        names.append(section["heading"])
    return " > ".join(names) or "(no heading)"


def section_rows(record: dict, kind: str, stem: str) -> list[dict]:
    """One row per indexable section of one record. The id counts all sections of the record, so it
    does not change when another section is excluded."""
    rows = []
    for n, s in enumerate(record["sections"], 1):
        if s.get("embed") is False:
            continue
        rows.append(
            {
                "id": f"{kind}/{stem}#{n}",
                "doc_type": record.get("doc_type") or "page",
                "department": record_department(record),
                "scope": record_scope(record),
                "term": record_term(record),
                "source": record.get("source_url") or record["source_file"],
                "heading_path": heading_path(s),
                "heading": s["heading"],
                "chars": len(s["markdown"]),
            }
        )
    return rows


def record_department(record: dict) -> str:
    if "department" in record:
        return record["department"]
    return record["owner"] if record.get("kind") == "department" else "-"


def record_scope(record: dict) -> str:
    if "scope" in record:
        return record["scope"]
    return "department" if record.get("kind") == "department" else "city_tech"


def record_term(record: dict) -> str:
    return record.get("term") or record.get("aid_year") or "-"


def is_indexable(record: dict) -> bool:
    return bool(record.get("index")) and record.get("status", "collected") == "collected"


def load_rows(processed: Path) -> tuple[list[dict], dict[str, int]]:
    """(rows, number of records left out because index is false or the page was not collected)."""
    rows: list[dict] = []
    left_out = Counter()
    groups = [
        ("page", "pages/*/*.json"),
        ("pdf", "pdfs/*.json"),
        ("dept", "departments/*/*.json"),
    ]
    for kind, pattern in groups:
        for path in sorted(processed.glob(pattern)):
            record = json.loads(path.read_text(encoding="utf-8"))
            if not is_indexable(record):
                left_out[kind] += 1
                continue
            stem = path.stem if kind == "pdf" else f"{path.parent.name}/{path.stem}"
            rows += section_rows(record, kind, stem)
    return rows, dict(left_out)


def by_source(rows: list[dict]) -> dict[str, list[dict]]:
    """Rows grouped by source, in the order the sources first appear."""
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["source"], []).append(row)
    return groups


def calendar_rows(events: list[dict]) -> list[dict]:
    counts = Counter((e["term"], e["source_pdf"]) for e in events)
    return [{"term": t, "events": n, "source_pdf": s} for (t, s), n in counts.items()]


def course_counts(processed: Path) -> dict[str, int]:
    folders = sorted(p for p in (processed / "courses").iterdir() if p.is_dir())
    return {p.name: len(list(p.glob("*.json"))) for p in folders}


def render(rows: list[dict], left_out: dict, events: list[dict], courses: dict[str, int]) -> str:
    per_type = Counter(r["doc_type"] for r in rows)
    lines = [
        "# Section index",
        "",
        "Every indexable section (record `index: true`, section not `embed: false`), for choosing",
        "`gold_sources` for eval questions. Built by `scripts/make_section_index.py`; do not edit.",
        "The id is `<kind>/<record>#<section number>`; it does not change when a section is left",
        "out. Chars is the length of the section's markdown. Chunking may merge a section's tables",
        "into its parent section (`merge_tables_into_parents`), so a chunk can exceed a row.",
        "Pages have no `doc_type` yet and show as `page`. Term is `-` where none is printed.",
        "",
        f"**{len(rows)} sections** in {len(by_source(rows))} sources. "
        f"Records left out: {left_out or 'none'} (index false or not collected).",
        "",
        "| doc_type | sections |",
        "|---|---|",
        *[f"| {t} | {n} |" for t, n in sorted(per_type.items())],
        "",
        "## Sections by source",
    ]
    for source, group in by_source(rows).items():
        first = group[0]
        lines += [
            "",
            f"### {source}",
            "",
            f"{first['doc_type']}, department {first['department']}, scope {first['scope']}, "
            f"term {first['term']}: {len(group)} sections, {sum(r['chars'] for r in group)} chars.",
            "",
            "| id | doc_type | department | scope | term | source | heading path | chars |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in group:
            cells = [r["id"], r["doc_type"], r["department"], r["scope"], r["term"], r["source"],
                     r["heading_path"], str(r["chars"])]  # fmt: skip
            lines.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
    lines += [
        "",
        "## Calendar (answered from the table, not from sections)",
        "",
        "| term | events | source_pdf |",
        "|---|---|---|",
        *[f"| {r['term']} | {r['events']} | {r['source_pdf']} |" for r in calendar_rows(events)],
        "",
        "## Courses (one chunk per course)",
        "",
        "| department | courses |",
        "|---|---|",
        *[f"| {d} | {n} |" for d, n in courses.items()],
        f"| total | {sum(courses.values())} |",
        "",
    ]
    return "\n".join(lines)
