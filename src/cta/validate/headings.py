"""No markdown link markup in section headings or heading paths (docs/data-validation.md)."""

from cta.validate.findings import Finding


def check_heading_markup(record: dict) -> list[Finding]:
    """Fail for every section whose heading, or a parent heading, still contains "](" ."""
    name = record.get("source_url") or record.get("source_file") or "?"
    found = []
    for n, s in enumerate(record["sections"], 1):
        names = [s["heading"] or "", *[p["heading"] or "" for p in s["parents"]]]
        bad = [h for h in names if "](" in h]
        if bad:
            message = f"section {n}: link markup left in {bad[0]!r}"
            found.append(Finding("heading_markup", "fail", message, name))
    return found


def run_heading_checks(records: list[dict]) -> list[Finding]:
    return [f for r in records for f in check_heading_markup(r)]
