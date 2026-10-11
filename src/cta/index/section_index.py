"""The list of indexable sections, used to pick gold_sources for eval questions.

A section is indexable when its record is `index: true`, the page was collected, and the section
itself is not `embed: false` (the PDF contact block). Contact blocks are not sections at all.
Built into docs/section-index.md by scripts/make_section_index.py. Nothing here is embedded.
"""

import json
from collections import Counter
from pathlib import Path

from cta.index.metadata import FIELDS, chunk_metadata


def heading_path(section: dict) -> str:
    """Parents then heading, outermost first ("Program > Requirements > General Education")."""
    names = [p["heading"] for p in section["parents"] if p["heading"]]
    if section["heading"]:
        names.append(section["heading"])
    return " > ".join(names) or "(no heading)"


def section_rows(record: dict, kind: str, stem: str) -> list[dict]:
    """One row per indexable section of one record. The id counts all sections of the record, so it
    does not change when another section is excluded. Metadata values are as the chunk carries them
    (None stays None; the table shows it as "-")."""
    rows = []
    for n, s in enumerate(record["sections"], 1):
        if s.get("embed") is False:
            continue
        values, _ = chunk_metadata(record, s)
        rows.append(
            {
                "id": f"{kind}/{stem}#{n}",
                **values,
                "terms": s.get("terms", []),
                "aid_year": record.get("aid_year"),
                "heading_path": heading_path(s),
                "heading": s["heading"],
                "chars": len(s["markdown"]),
            }
        )
    return rows


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


def null_counts(rows: list[dict]) -> dict[str, dict]:
    """Per doc_type: the number of sections and, for each metadata field, how many are null."""
    out: dict[str, dict] = {}
    for r in rows:
        entry = out.setdefault(
            r["doc_type"] or "(null)", {"sections": 0, **dict.fromkeys(FIELDS, 0)}
        )
        entry["sections"] += 1
        for f in FIELDS:
            entry[f] += r[f] is None
    return dict(sorted(out.items()))


def term_cell(row: dict) -> str:
    if row["term"]:
        return row["term"]
    return f"aid year {row['aid_year']}" if row.get("aid_year") else "-"


def terms_counts(rows: list[dict]) -> dict[str, dict[str, int]]:
    """Per doc_type: sections, sections with `terms`, and sections with more than one term."""
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        e = out.setdefault(
            r["doc_type"] or "(null)", {"sections": 0, "with_terms": 0, "several": 0}
        )
        e["sections"] += 1
        e["with_terms"] += bool(r["terms"])
        e["several"] += len(r["terms"]) > 1
    return dict(sorted(out.items()))


def terms_cell(row: dict) -> str:
    return "; ".join(row["terms"]) if row["terms"] else "-"


def show(value: object) -> str:
    return "-" if value is None else str(value)


def render(rows: list[dict], left_out: dict, events: list[dict], courses: dict[str, int]) -> str:
    per_type = Counter(r["doc_type"] for r in rows)
    nulls = null_counts(rows)
    with_terms = terms_counts(rows)
    lines = [
        "# Section index",
        "",
        "Every indexable section (record `index: true`, section not `embed: false`), for choosing",
        "`gold_sources` for eval questions. Built by `scripts/make_section_index.py`; do not edit.",
        "The id is `<kind>/<record>#<section number>`; it does not change when a section is left",
        "out. Chars is the length of the section's markdown. Chunking may merge a section's tables",
        "into its parent section (`merge_tables_into_parents`), so a chunk can exceed a row.",
        "`-` means null. Term is null where none is printed; aid-year documents show the year.",
        "",
        f"**{len(rows)} sections** in {len(by_source(rows))} sources. "
        f"Records left out: {left_out or 'none'} (index false or not collected).",
        "",
        "| doc_type | sections |",
        "|---|---|",
        *[f"| {t} | {n} |" for t, n in sorted(per_type.items())],
        "",
        "## Null counts per field and doc_type",
        "",
        "Sections whose metadata field is null. Null is allowed for department (central offices,",
        "CUNY-wide documents), term and last_updated. `date` is the fetch date or the file date.",
        "`catalog_course` has no sections here: a course is one chunk of its own record.",
        "",
        "| group (doc_type) | sections | " + " | ".join(FIELDS) + " |",
        "|---|---|" + "---|" * len(FIELDS),
        *[
            f"| {t} | {e['sections']} | " + " | ".join(str(e[f]) for f in FIELDS) + " |"
            for t, e in nulls.items()
        ],  # fmt: skip
        "",
        "## Sections with terms per doc_type",
        "",
        "`terms` is filled only from explicit term names (Summer I, Summer II, Summer, Fall,",
        "Winter, Spring + a year) in a section's heading path or table title; never from body",
        "text or dates.",
        "`term` is the single entry when there is exactly one, else null.",
        "",
        "| doc_type | sections | with terms | with several terms |",
        "|---|---|---|---|",
        *[
            f"| {t} | {e['sections']} | {e['with_terms']} | {e['several']} |"
            for t, e in with_terms.items()
        ],  # fmt: skip
        f"| total | {len(rows)} | {sum(e['with_terms'] for e in with_terms.values())} | "
        f"{sum(e['several'] for e in with_terms.values())} |",
        "",
        "## Sections by source",
    ]
    for source, group in by_source(rows).items():
        first = group[0]
        lines += [
            "",
            f"### {source}",
            "",
            f"{first['doc_type']}, department {show(first['department'])}, scope {first['scope']}, "
            f"term {term_cell(first)}: {len(group)} sections, "
            f"{sum(r['chars'] for r in group)} chars.",
            "",
            "| id | doc_type | department | scope | term | terms | source | heading path | chars |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for r in group:
            cells = [r["id"], show(r["doc_type"]), show(r["department"]), r["scope"], term_cell(r),
                     terms_cell(r), r["source"], r["heading_path"], str(r["chars"])]  # fmt: skip
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
