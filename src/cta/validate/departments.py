"""Automatic checks for the department records (docs/data-validation.md, "PDFs").

Run with the build: uv run python -m cta.parse.departments
The completeness check compares every character the PDF prints (found without using the parser's
lines or blocks) with everything the records hold: kept text, stripped text, degree maps and counts.
"""

import json
import re
from collections import Counter

from cta.parse.departments import is_label
from cta.validate.findings import Finding, squash
from cta.validate.pdfs import markdown_text, normalize

REPLACEMENT = "�"
BROKEN_GLYPH = "⯑"
LIGATURES = "".join(chr(c) for c in range(0xFB00, 0xFB07))
TOTAL_LINE = re.compile(r"Total (?:General Education|Major|Minor|Elective) Credits")
BARE_NUMBERS = re.compile(r"\d+(?: - \d+)? \d+(?: - \d+)?$")
ID_ALONE = re.compile(r"(?:^|\| )\d{6}(?: \||$)")
STRAY = "Accelerator Science and Technology"


def kept_text(record: dict) -> str:
    """The text a record shows as sections (not the generated degree map tables)."""
    parts: list[str] = []
    for s in record["sections"]:
        if s.get("generated"):
            continue
        parts.append(markdown_text(s["markdown"]))
    return "\n".join(parts)


def all_text(record: dict) -> str:
    """Everything printable in a record, including generated sections (for text rules)."""
    parts = [record.get("title") or ""]
    for s in record["sections"]:
        parts += [s["heading"] or "", s["markdown"]]
    return "\n".join(parts)


def check_characters(record: dict) -> list[Finding]:
    """No replacement character, no unrepaired broken glyph, no ligature character left."""
    text = json.dumps(record, ensure_ascii=False)
    found = []
    name = record_label(record)
    if REPLACEMENT in text:
        found.append(
            Finding(
                "replacement_chars",
                "fail",
                f"{text.count(REPLACEMENT)} replacement characters",
                name,
            )
        )
    # the printed form of a repaired word is kept in `repairs`, so look only at the content
    content = json.dumps({k: v for k, v in record.items() if k != "repairs"}, ensure_ascii=False)
    if BROKEN_GLYPH in content:
        found.append(
            Finding(
                "broken_glyph",
                "fail",
                f"{content.count(BROKEN_GLYPH)} unrepaired broken glyphs",
                name,
            )
        )
    left = [c for c in content if c in LIGATURES]
    if left:
        found.append(Finding("ligatures", "fail", f"{len(left)} ligature characters left", name))
    return found


def record_label(record: dict) -> str:
    return f"{record['department']}/{record['doc_type']}/{record.get('title')}"


def check_no_rule_dumps(record: dict, generic: set[str]) -> list[Finding]:
    """No sentence that was stripped as generic rule text is left in the kept text."""
    text = re.sub(r"\W+", " ", kept_text(record)).lower()
    found = []
    for sentence in sorted(generic):
        if sentence and sentence in text:
            found.append(
                Finding(
                    "rule_dump",
                    "fail",
                    f"generic rule text left: {sentence[:90]!r}",
                    record_label(record),
                )
            )
    return found


def check_no_markers(record: dict) -> list[Finding]:
    """No "Advisory Commission", "(Inactive)", or "Total ... Credits" lines in anything kept."""
    text = (
        all_text(record)
        + "\n"
        + "\n".join(m["printed"] for m in record.get("program", {}).get("degree_maps", []))
    )
    found = []
    name = record_label(record)
    if re.search(r"Advisory Commission", text, re.I):
        found.append(Finding("advisory_commission", "fail", "Advisory Commission text kept", name))
    if "(Inactive)" in text:
        found.append(Finding("inactive", "fail", "(Inactive) course kept", name))
    if TOTAL_LINE.search(text):
        found.append(Finding("total_lines", "fail", "a 'Total ... Credits' line is kept", name))
    if STRAY.lower() in record.get("title", "").lower():
        found.append(Finding("stray_program", "fail", "the stray program has a record", name))
    return found


def check_required_parts(records: list[dict]) -> list[Finding]:
    """Each department has an overview, at least one program, requirements and one degree map."""
    dept = records[0]["department"] if records else "?"
    overview = [r for r in records if r["doc_type"] == "department"]
    programs = [r for r in records if r["doc_type"] == "program"]
    found = []
    if len(overview) != 1 or not any(
        s["heading"] == "Description" for s in overview[0]["sections"]
    ):
        found.append(Finding("overview", "fail", "no overview with a Description section", dept))
    if not programs:
        found.append(Finding("programs", "fail", "no program record", dept))
    if not any(has_heading(p, "Requirements") for p in programs):
        found.append(Finding("requirements", "fail", "no program has a Requirements section", dept))
    if not any(p["program"]["degree_maps"] for p in programs):
        found.append(Finding("degree_map", "fail", "no program has a degree map", dept))
    for p in programs:
        if (
            not p["program"]["credit_totals"]["degree_maps"]
            and not p["program"]["credit_totals"]["overall_requirement_lines"]
        ):
            found.append(
                Finding("credit_totals", "warning", "no credit total printed", record_label(p))
            )
    slugs = Counter(p["program"]["slug"] for p in programs)
    found += [
        Finding("program_slug", "fail", f"slug {s!r} used {n} times", dept)
        for s, n in slugs.items()
        if n > 1
    ]
    return found


def has_heading(record: dict, heading: str) -> bool:
    """A heading is present as a section, or as the parent of one (an empty section is not kept)."""
    return any(
        s["heading"] == heading or any(h["heading"] == heading for h in s["parents"])
        for s in record["sections"]
    )


def check_term_not_invented(records: list[dict]) -> list[Finding]:
    return [
        Finding(
            "term",
            "fail",
            f"term is {r['term']!r}: the two labels must be stored, not a term",
            record_label(r),
        )
        for r in records
        if r["term"] is not None
    ]


def check_rules_resolved(record: dict) -> list[Finding]:
    """Every 6-digit rule ID in a degree map note resolved to text (or is listed as unresolved)."""
    found = []
    for m in record.get("program", {}).get("degree_maps", []):
        for sem in m["semesters"]:
            for card in sem["cards"]:
                for rule in card["rules"]:
                    if rule["id"] and rule["status"] == "unresolved":
                        found.append(
                            Finding(
                                "rule_unresolved",
                                "fail",
                                f"rule {rule['id']} has no text",
                                record_label(record),
                            )
                        )
    for s in record["sections"]:
        if s.get("generated"):
            for line in s["markdown"].split("\n"):
                if line.startswith("|") and any(ID_ALONE.search(c) for c in [line]):
                    found.append(
                        Finding(
                            "rule_id_alone",
                            "fail",
                            f"a rule ID stands alone in: {line[:60]!r}",
                            record_label(record),
                        )
                    )
    return found


def table_rows(markdown: str) -> list[list[list[str]]]:
    """Each markdown table of a section as rows of cells (the --- row is left out)."""
    tables: list[list[list[str]]] = []
    for block in markdown.split("\n\n"):
        if not block.startswith("|"):
            continue
        rows = []
        for line in block.split("\n"):
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
            if not all(set(c) <= {"-"} and c for c in cells):
                rows.append(cells)
        tables.append(rows)
    return tables


def check_table_format(record: dict) -> list[Finding]:
    """No empty header row, no column that is "-" or "No" in every row, no rule ID at the start of
    a rule notes cell, and no semester heading that ends in two bare numbers."""
    found = []
    name = record_label(record)
    for s in record["sections"]:
        for rows in table_rows(s["markdown"]):
            head, body = rows[0], rows[1:]
            if not any(head):
                found.append(
                    Finding("table_header", "fail", f"empty header in {s['heading']!r}", name)
                )
            for i, col in enumerate(head[1:], 1):
                if body and all(r[i] in ("-", "No") for r in body if len(r) > i):
                    found.append(
                        Finding(
                            "table_constant_column",
                            "fail",
                            f"column {col!r} is '-' or 'No' in every row of {s['heading']!r}",
                            name,
                        )
                    )
            if "Rule notes" in head:
                i = head.index("Rule notes")
                if any(re.match(r"\d{6}\b", r[i]) for r in body if len(r) > i):
                    found.append(
                        Finding(
                            "rule_id_in_cell",
                            "fail",
                            f"rule ID in a cell of {s['heading']!r}",
                            name,
                        )
                    )
        if s.get("generated") and s["level"] == 4 and BARE_NUMBERS.search(s["heading"] or ""):
            found.append(
                Finding("semester_heading", "fail", f"bare credit numbers: {s['heading']!r}", name)
            )
    return found


def check_rule_ids_on_sections(record: dict) -> list[Finding]:
    """Every rule ID of a degree map card is in the rule_ids list of a semester section."""
    on_sections = {i for s in record["sections"] for i in s.get("rule_ids", [])}
    used = {
        r["id"]
        for m in record.get("program", {}).get("degree_maps", [])
        for sem in m["semesters"]
        for card in sem["cards"]
        for r in card["rules"]
        if r["id"]
    }
    missing = sorted(used - on_sections)
    return (
        [
            Finding(
                "rule_ids", "fail", f"rule IDs not on any section: {missing}", record_label(record)
            )
        ]
        if missing
        else []
    )


def check_no_empty_sections(record: dict) -> list[Finding]:
    """No section with a heading and no content, and none that ends in a bare label (a short
    Title Case line such as "Writing Intensive" with nothing under it)."""
    found = []
    name = record_label(record)
    for s in record["sections"]:
        if s["heading"] and not s["markdown"].strip():
            found.append(Finding("empty_section", "fail", f"{s['heading']!r} has no content", name))
            continue
        blocks = [b for b in s["markdown"].split("\n\n") if b]
        last = blocks[-1]
        if len(blocks) > 1 and not last.startswith(("- ", "|")) and is_label(("p", 0, last)):
            message = f"{s['heading']!r} ends in a bare label {last!r}"
            found.append(Finding("empty_label", "fail", message, name))
    return found


def check_map_labels(record: dict) -> list[Finding]:
    labels = [m["label"] for m in record.get("program", {}).get("degree_maps", [])]
    return [
        Finding("map_label", "fail", f"degree map label {label!r} used twice", record_label(record))
        for label, n in Counter(labels).items()
        if n > 1
    ]


def check_pdf_contact_not_indexed(overview: dict) -> list[Finding]:
    """The PDF "Chair" block is an office contact: embed false (the web page is the source)."""
    name = record_label(overview)
    found = []
    chair_sections = [s for s in overview["sections"] if s["heading"] == "Chair"]
    if any(s.get("embed") is not False for s in chair_sections):
        found.append(
            Finding(
                "pdf_contact_indexed", "fail", "the PDF Chair section is not embed: false", name
            )
        )
    if overview["chair_pdf"].get("embed") is not False:
        found.append(Finding("pdf_contact_indexed", "fail", "chair_pdf is not embed: false", name))
    if not overview.get("contact_pdf_vs_root"):
        found.append(
            Finding("contact_compare", "warning", "no root page contact block to compare", name)
        )
    return found


def check_chair(overview: dict) -> list[Finding]:
    chair = overview.get("chair") or {}
    found = []
    if not chair.get("name"):
        found.append(Finding("chair", "fail", "no chair name", record_label(overview)))
    if not overview.get("chair_comparison"):
        found.append(
            Finding(
                "chair",
                "warning",
                "chair was not compared with chairperson.aspx",
                record_label(overview),
            )
        )
    return found


def record_chars(records: list[dict]) -> Counter:
    """Characters accounted for by the records of one department."""
    total: Counter = Counter()
    for r in records:
        parts = [kept_text(r)]
        headings = {r.get("title") or ""}
        for s in r["sections"]:
            if s.get("generated"):
                continue  # built from the degree map data (its printed text is in the map)
            if s["heading"]:
                headings.add(s["heading"])
            headings.update(h["heading"] for h in s["parents"] if h["heading"] != "Degree Maps")
        parts += sorted(headings)
        parts += r.get("dropped_empty_headings", [])
        if r.get("program", {}).get("degree_maps"):
            parts.append("Degree Maps")  # the heading above the maps
        parts += [s["text"] for s in r["stripped"]]
        parts += [m["printed"] for m in r.get("program", {}).get("degree_maps", [])]
        parts += [f["text"] for f in r.get("page_footers", [])]
        total.update(squash(normalize("\n".join(parts))))
        for char, n in r.get("course_card_chars", {}).items():
            total[char] += n
    return total


def check_completeness(records: list[dict], pdf_chars: list[str]) -> list[Finding]:
    """Nothing printed is lost and nothing is invented: kept + stripped + counted = printed."""
    expected = Counter(squash(normalize("".join(pdf_chars))))
    produced = record_chars(records)
    for r in records:
        for rep in r["repairs"]:
            if (
                rep["kind"] == "broken_glyph"
            ):  # the PDF has the broken word, the record the repaired one
                n = rep["count"]
                for _ in range(n):
                    expected.subtract(squash(rep["printed"]))
                    expected.update(squash(rep["repaired"]))
    dept = records[0]["department"]
    missing = +(expected - produced)
    extra = +(produced - expected)
    found = []
    if missing:
        found.append(
            Finding(
                "chars_missing",
                "fail",
                f"printed in the PDF, not in the records: {dict(missing)}",
                dept,
            )
        )
    if extra:
        found.append(
            Finding(
                "chars_extra",
                "fail",
                f"in the records, not printed in the PDF: {dict(extra)}",
                dept,
            )
        )
    return found


def run_department_checks(records: list[dict], parsed, generic: set[str]) -> list[Finding]:
    found: list[Finding] = [*check_required_parts(records), *check_term_not_invented(records)]
    for r in records:
        found += [
            *check_characters(r),
            *check_no_rule_dumps(r, generic),
            *check_no_markers(r),
            *check_rules_resolved(r),
            *check_table_format(r),
            *check_rule_ids_on_sections(r),
            *check_map_labels(r),
            *check_no_empty_sections(r),
        ]
        if r["doc_type"] == "department":
            found += [*check_chair(r), *check_pdf_contact_not_indexed(r)]
    found += check_completeness(records, parsed.stream.body_chars)
    return found
