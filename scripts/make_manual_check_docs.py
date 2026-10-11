"""Write docs/manual-check-programs.md and docs/manual-check-contacts.md (blank result columns).

Run: uv run python scripts/make_manual_check_docs.py
Both files are built from data/processed; the owner fills the Result column by hand.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OPEN_ITEMS = {
    "Cybersecurity - BS - Bachelor of Science": "credit mismatch: degree maps total 114 - 118 "
    "but the requirements print 'Earn at least 120-124 credits'",
    "Applied Mathematics - BS - Bachelor of Science": "credit mismatch: degree map totals 117 - 119 "
    "but the requirements print 'Earn at least 120 credits'",
    "Computer Science -": "the minor's title is printed incomplete ('Computer Science -'); "
    "it has no degree map and no credit total",
}


def raw_hours_by_owner() -> dict[str, bool]:
    """Does the raw HTML of any page of the owner have an hours panel? (same check as validation)"""
    from cta.validate.pages import load_raw, raw_hours

    manifest = json.loads((PROCESSED / "pages_manifest.json").read_text(encoding="utf-8"))
    owner_of = {e["url"]: e["owner"] for e in manifest}
    found: dict[str, bool] = {e["owner"]: False for e in manifest}
    for url, html in load_raw(manifest, ROOT / "data" / "raw").items():
        found[owner_of[url]] = found[owner_of[url]] or bool(raw_hours(html))
    return found


def hours_text(entries: list[dict]) -> str:
    """The stored hours as printed, on one line per entry (table rows become 'Day time')."""
    out = []
    for h in entries:
        rows = []
        for line in h["markdown"].split("\n"):
            if line.startswith("|"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                if any(cells) and not all(set(c) <= {"-"} for c in cells):
                    rows.append(" ".join(cells))
            elif line.strip():
                rows.append(line.strip())
        out.append(f"{h['heading']}: " + "; ".join(rows))
    return "<br>".join(out)


def cell_hours(text: str) -> str:
    """A table cell; text marked "@@" keeps its <br> line breaks."""
    if text.startswith("@@"):
        return text[2:].replace("|", "\\|")
    return cell(text)


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def required_courses(record: dict) -> list[str]:
    """The list items of the "Required Courses in the Major" (or Minor) requirement group."""
    items: list[str] = []
    for s in record["sections"]:
        if s["heading"] and s["heading"].startswith("Required Courses in the"):
            items += [
                re.sub(r"^\s*- ", "", line).replace("**", "")
                for line in s["markdown"].split("\n")
                if re.match(r"^\s*- ", line)
            ]
    return items


def program_row(record: dict) -> str:
    prog = record["program"]
    maps = "<br>".join(
        f"{m['label']}: {m['total_credits']}" for m in prog["degree_maps"]
    ) or "no degree map"
    earn = [
        x for x in prog["credit_totals"]["overall_requirement_lines"] if x.startswith("Earn at least")
    ]
    courses = "<br>".join(cell(c) for c in required_courses(record)) or "none listed"
    name = f"{record['department']}: {record['title']}"
    return f"| {cell(name)} | {maps} | {cell('; '.join(earn)) or 'not printed'} | {courses} |  |"


def programs_doc() -> str:
    records = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((PROCESSED / "departments").glob("*/program-*.json"))
    ]
    header = [
        "| Program | Degree map credit total | 'Earn at least' | Required courses | Result |",
        "|---|---|---|---|---|",
    ]
    lines = [
        "# Manual check: programs",
        "",
        "Compare each row with the live catalog program page: the credit total, the 'Earn at least'",
        "figure and the required course list. Write the outcome in the Result column.",
        "Built by `scripts/make_manual_check_docs.py` from `data/processed/departments`.",
        "",
        "## Open items (check these first)",
        "",
        *header,
    ]
    open_rows, rest = [], []
    for r in records:
        (open_rows if r["title"] in OPEN_ITEMS else rest).append(r)
    open_rows.sort(key=lambda r: list(OPEN_ITEMS).index(r["title"]))
    for r in open_rows:
        lines.append(program_row(r))
    lines += ["", "What is open:", ""]
    lines += [f"- **{t}**: {why}." for t, why in OPEN_ITEMS.items()]
    lines += ["", "## All other programs", "", *header]
    lines += [program_row(r) for r in rest]
    return "\n".join(lines) + "\n"


def contacts_doc() -> str:
    lines = [
        "# Manual check: contacts",
        "",
        "Compare each row with the live page it came from (phone, email, room). Write the outcome in",
        "the Result column. Office and department contacts come from `data/processed/contacts`; every",
        "page of an owner shows the same block (the records say `consistent: true`). Chairs come from",
        "the `chairperson.aspx` page records.",
        "",
        "## Office and department contact blocks",
        "",
        "| Owner | Kind | Room / address | Phone | Email | Hours | Source URL (first of N pages) "
        "| Result |",
        "|---|---|---|---|---|---|---|---|",
    ]
    printed = raw_hours_by_owner()
    for path in sorted((PROCESSED / "contacts").glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        panel = next((p for p in c["panels"] if p["heading"] == "CONTACT US"), c["panels"][0])
        place = " / ".join(
            x
            for x in panel["markdown"].split("\n\n")[0].split("\n")
            if x and "@" not in x and ":" not in x
        )
        n = len(c["source_pages"])
        row = [
            c["owner"],
            c["kind"],
            place or "-",
            ", ".join(c["phones"]) or "-",
            ", ".join(c["emails"]) or "-",
            "@@" + (hours_text(c["hours"]) if c["hours"] else
                    "NOT STORED (printed on the page)" if printed.get(c["owner"]) else "none printed"),
            f"{c['source_pages'][0]} ({n} pages)",
            "",
        ]
        lines.append("| " + " | ".join(cell_hours(x) for x in row) + " |")
    lines += [
        "",
        "## Department chairs (chairperson.aspx)",
        "",
        "| Department | Name | Role | Room | Phone | Email | Hours | Source URL | Result |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for path in sorted((PROCESSED / "pages").glob("*-NYT/chairperson.json")):
        r = json.loads(path.read_text(encoding="utf-8"))
        ch = r["chair"] or {}
        hours = (
            "department hours, see the department row above (none for the chair)"
            if printed.get(r["owner"])
            else "none printed"
        )
        row = [r["owner"], ch.get("name"), ch.get("role"), ch.get("room"), ch.get("phone"),
               ch.get("email"), hours, r["final_url"], ""]  # fmt: skip
        lines.append("| " + " | ".join(cell(str(x or "-")) if x != "" else "" for x in row) + " |")
    lines += [
        "",
        "Look at when checking: the financial aid page's PHONE HOURS table prints Tuesday as "
        "'9:00 PM - 5:00 PM' (probably AM; left as printed). The EET and financial aid blocks also list a fax number (it is in the Phone column).",
        "",
        "Note: the PDF 'Chair' blocks are not listed here. They are department office contacts, "
        "are not indexed, and match the department root page blocks (see `docs/validation-log.md`).",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    (ROOT / "docs" / "manual-check-programs.md").write_text(programs_doc(), encoding="utf-8")
    (ROOT / "docs" / "manual-check-contacts.md").write_text(contacts_doc(), encoding="utf-8")


if __name__ == "__main__":
    main()
