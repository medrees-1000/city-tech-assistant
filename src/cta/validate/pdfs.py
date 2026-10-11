"""Automatic checks for the PDF records (docs/data-validation.md, "PDFs").

Each check re-reads the PDF with its own, simpler logic (all characters, or pdfplumber's own
line and table finder) and compares it with the record, so a dropped, repeated or invented
line is found.
"""

import json
import re
from collections import Counter
from pathlib import Path

import pdfplumber

from cta.parse.pdf_docs import BULLETS, LIGATURES, in_box
from cta.validate.findings import Finding

REPLACEMENT = "�"
TERM = re.compile(r"\b(Fall|Spring|Summer|Winter)\s+(20\d\d)\b")
AID_YEAR = re.compile(r"\b20\d\d\s*-\s*20\d\d\b(?:\s*&\s*20\d\d\s*-\s*20\d\d)?")
UPDATED = re.compile(
    r"(?:Last\s+)?[Uu]pdated:?\s*\d{1,2}/\d{1,2}/\d{2,4}|[Rr]evised:?\s*\d{1,2}/\d{1,2}/\d{2,4}"
)
# How tables are expected in each file: "match" = every table the finder sees is a table in the
# record; "none" = the finder sees no table with text; "skip" = frames around screenshots and the
# contents grid on the cover page.
TABLE_POLICY = {
    "Award_Year_2026_2027_Financial_Aid_Payment_Refund _Calendar.pdf": "match",
    "Fall_2026_Dropping_and_Withdrawing_from_Classes.pdf": "none",
    "Special_Circumstances_Flyer_2025_2026_2026_2027.pdf": "none",
    "cunyfirst_student_reference.pdf": "skip",
}
# Lines of a multi-column infographic interleave its panels, so lines cannot be compared one by one.
LINE_CHECK_SKIPPED = {"Special_Circumstances_Flyer_2025_2026_2026_2027.pdf"}


def squash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def normalize(text: str) -> str:
    for lig, plain in LIGATURES.items():
        text = text.replace(lig, plain)
    for bullet in BULLETS:
        text = text.replace(bullet, "")
    return text


def markdown_text(md: str) -> str:
    """Plain text of a section's markdown: no bold marks, list markers or table syntax."""
    out = []
    for line in md.split("\n"):
        if line.startswith("|"):
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
            if all(set(c) <= {"-"} and c for c in cells):
                continue  # the | --- | separator row
            out.append(" ".join(c.replace("\\|", "|") for c in cells))
        else:
            out.append(re.sub(r"^\s*- ", "", line))
    return "\n".join(out).replace("**", "")


def record_text(record: dict) -> str:
    """All printed text the record holds: sections, title, headings and excluded lines."""
    headings = {record["title"]} if record["title"] else set()
    parts = []
    for s in record["sections"]:
        if s["heading"]:
            headings.add(s["heading"])
        headings.update(h["heading"] for h in s["parents"])
        parts.append(markdown_text(s["markdown"]))
    parts += sorted(headings)
    parts += [e["text"] for e in record["excluded"]]
    return normalize("\n".join(parts))


def pdf_text_lines(path: Path) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [ln["text"] for page in pdf.pages for ln in page.extract_text_lines(strip=True)]


def pdf_chars(path: Path) -> Counter:
    with pdfplumber.open(path) as pdf:
        text = "".join(c["text"] for page in pdf.pages for c in page.chars)
    return Counter(squash(normalize(text)))


def title_area_text(path: Path) -> str:
    """Text in the top fifth of the first page (where a document prints its term or aid year)."""
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        top = page.crop(
            (page.bbox[0], page.bbox[1], page.bbox[2], page.bbox[1] + 0.2 * page.height)
        )
        return top.extract_text() or ""


def check_no_replacement_characters(record: dict) -> list[Finding]:
    text = json.dumps(record, ensure_ascii=False)
    n = text.count(REPLACEMENT)
    return (
        [Finding("replacement_chars", "fail", f"{n} replacement characters", record["source_file"])]
        if n
        else []
    )


def check_every_character_placed(record: dict, path: Path) -> list[Finding]:
    """Every character printed in the PDF is in the record (sections, title, excluded), no more."""
    produced = Counter(squash(record_text(record)))
    expected = pdf_chars(path)
    missing, extra = expected - produced, produced - expected
    found = []
    if missing:
        found.append(
            Finding(
                "chars_missing",
                "fail",
                f"in the PDF, not in the record: {dict(missing)}",
                record["source_file"],
            )
        )
    if extra:
        found.append(
            Finding(
                "chars_extra",
                "fail",
                f"in the record, not in the PDF: {dict(extra)}",
                record["source_file"],
            )
        )
    return found


def check_every_line_placed(record: dict, path: Path) -> list[Finding]:
    """Every line pdfplumber finds in the PDF appears, in order, in the record text."""
    if path.name in LINE_CHECK_SKIPPED:
        return []
    text = squash(record_text(record))
    found = []
    for line in pdf_text_lines(path):
        wanted = squash(normalize(line))
        if wanted and wanted not in text:
            found.append(
                Finding(
                    "line_not_placed",
                    "fail",
                    f"printed line not in the record: {line!r}",
                    record["source_file"],
                )
            )
    return found


def check_dates_and_terms(record: dict, path: Path) -> list[Finding]:
    """A term or aid year in the PDF's title, and any "Updated" date, are in the record.

    Nothing is invented. Terms in the body ("Summer 2026 refunds begin ...") are content, not the
    document's term."""
    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    title_area = title_area_text(path)
    found, name = [], record["source_file"]
    term = TERM.search(title_area)
    if term and record["term"] != term.group(0):
        found.append(
            Finding(
                "term",
                "fail",
                f"title prints {term.group(0)!r}, record has {record['term']!r}",
                name,
            )
        )
    if not term and record["term"]:
        found.append(
            Finding(
                "term", "fail", f"record has term {record['term']!r}, the title prints none", name
            )
        )
    aid = AID_YEAR.search(title_area)
    if aid and not record["aid_year"]:
        found.append(
            Finding("aid_year", "fail", f"title prints {aid.group(0)!r}, record has none", name)
        )
    if record["aid_year"] and not aid:
        found.append(
            Finding("aid_year", "fail", "record has an aid year, the title prints none", name)
        )
    if aid and record["aid_year"] and squash(record["aid_year"]) != squash(aid.group(0)):
        found.append(
            Finding(
                "aid_year",
                "fail",
                f"title prints {aid.group(0)!r}, record has {record['aid_year']!r}",
                name,
            )
        )
    printed = UPDATED.search(text)
    if printed and not record["pdf_last_updated"]:
        found.append(
            Finding(
                "pdf_last_updated",
                "fail",
                f"PDF prints {printed.group(0)!r}, record has none",
                name,
            )
        )
    if record["pdf_last_updated"] and not printed:
        found.append(
            Finding(
                "pdf_last_updated", "fail", "record has an update date, the PDF prints none", name
            )
        )
    for key in ("pdf_last_updated", "file_modified", "file_created"):
        if record[key] and not re.match(r"\d{4}-\d{2}-\d{2}", record[key]):
            found.append(
                Finding("dates", "fail", f"{key} is not an ISO date: {record[key]!r}", name)
            )
    return found


def record_tables(record: dict) -> list[list[list[str]]]:
    """The markdown tables of a record as rows of cell texts, in order."""
    tables = []
    for s in record["sections"]:
        for block in s["markdown"].split("\n\n"):
            if block.startswith("|"):
                rows = []
                for line in block.split("\n"):
                    cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
                    if all(set(c) <= {"-"} and c for c in cells):
                        continue
                    rows.append([c.replace("\\|", "|") for c in cells])
                tables.append(rows)
    return tables


def check_tables_complete(record: dict, path: Path) -> list[Finding]:
    """Every table the PDF has is in the record with all its cells and no cell added."""
    policy = TABLE_POLICY.get(path.name, "match")
    if policy == "skip":
        return []
    name = record["source_file"]
    regions = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for t in page.find_tables():
                chars = [
                    c["text"] for c in page.chars if in_box(c, t.bbox) and not c["text"].isspace()
                ]
                if chars:
                    regions.append(Counter(normalize("".join(chars))))
    tables = record_tables(record)
    if policy == "none":
        return (
            [
                Finding(
                    "tables",
                    "fail",
                    f"the PDF has {len(regions)} tables, the record expects none",
                    name,
                )
            ]
            if regions
            else []
        )
    found = []
    if len(regions) != len(tables):
        return [
            Finding(
                "tables",
                "fail",
                f"PDF has {len(regions)} tables with text, record has {len(tables)}",
                name,
            )
        ]
    for i, (region, rows) in enumerate(zip(regions, tables, strict=True), 1):
        widths = {len(r) for r in rows}
        if len(widths) != 1:
            found.append(
                Finding(
                    "table_shape",
                    "fail",
                    f"table {i} rows have different widths: {sorted(widths)}",
                    name,
                )
            )
        cells = Counter(squash("".join("".join(r) for r in rows)))
        if cells != region:
            found.append(
                Finding(
                    "table_cells",
                    "fail",
                    f"table {i}: missing {dict(region - cells)}, extra {dict(cells - region)}",
                    name,
                )
            )
    return found


def run_pdf_checks(record: dict, path: Path) -> list[Finding]:
    return [
        *check_no_replacement_characters(record),
        *check_every_character_placed(record, path),
        *check_every_line_placed(record, path),
        *check_dates_and_terms(record, path),
        *check_tables_complete(record, path),
    ]
