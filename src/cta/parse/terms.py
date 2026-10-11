"""Term tags on sections: explicit term names only.

A term is a season name (Summer I, Summer II, Summer, Fall, Winter, Spring) followed by a 4-digit
year, as in "Fall 2026" or "Summer Session I 2026" (written "Summer I 2026"). Terms are read only
from a section's heading path (its parents' headings and its own heading) and from the header row
of its tables. Body text and dates are never used. A heading with a season and no year gets no
term, except through the one documented rule for the refund calendar PDF (docs/decisions.md).
"""

import re

SEASON = r"(?:Summer\s+(?:Session\s+)?I{1,2}\b|Summer(?:\s+Session)?|Fall|Winter|Spring)"
TERM = re.compile(rf"\b({SEASON})\s+(20\d\d)\b", re.I)
TERM_FORM = re.compile(r"^(Summer I|Summer II|Summer|Fall|Winter|Spring) \d{4}$")  # a stored term
BARE_SEASON = re.compile(rf"\b({SEASON})\b(?!\s+(?:Session\s+)?(?:I{{1,2}}\s+)?20\d\d)", re.I)


def season_name(raw: str) -> str:
    """ "summer session ii" -> "Summer II", "FALL" -> "Fall"."""
    words = raw.split()
    roman = next((w.upper() for w in words if re.fullmatch(r"I{1,2}", w, re.I)), "")
    return f"{words[0].capitalize()} {roman}".strip()


def terms_in(text: str) -> list[str]:
    """Explicit terms named in the text, in order, without repeats."""
    found: list[str] = []
    for m in TERM.finditer(text):
        term = f"{season_name(m[1])} {m[2]}"
        if term not in found:
            found.append(term)
    return found


def seasons_without_year(text: str) -> list[str]:
    """Season names in the text that have no year after them ("Fall and Spring" -> Fall, Spring)."""
    found: list[str] = []
    for m in BARE_SEASON.finditer(text):
        name = " ".join(m[1].split()).title()
        if name not in found:
            found.append(name)
    return found


def heading_path(section: dict) -> str:
    names = [p["heading"] for p in section["parents"] if p["heading"]]
    return " > ".join([*names, section["heading"] or ""])


def table_header_text(markdown: str) -> str:
    """The header row of each markdown table of the section (the table title row, if any)."""
    rows = []
    for block in markdown.split("\n\n"):
        if block.startswith("|"):
            rows.append(block.split("\n")[0].replace("|", " "))
    return " ".join(rows)


def table_text(markdown: str) -> str:
    """Every cell of every table of the section (used to report what a refund page covers)."""
    lines = [ln for b in markdown.split("\n\n") if b.startswith("|") for ln in b.split("\n")]
    return " ".join(ln.replace("|", " ").replace("<br>", " ") for ln in lines)


def section_terms(section: dict) -> list[str]:
    return terms_in(f"{heading_path(section)} {table_header_text(section['markdown'])}")


def set_terms(section: dict, terms: list[str], source: str | None = None) -> None:
    """terms is the list; term is the single value when there is exactly one, else null."""
    section["terms"] = terms
    section["term"] = terms[0] if len(terms) == 1 else None
    if source:
        section["terms_source"] = source


def tag_terms(record: dict) -> dict:
    """Set `terms` and `term` on every section of a record (explicit names only)."""
    for s in record["sections"]:
        set_terms(s, section_terms(s))
    return record


REFUND_SCHEDULE = "Refund Schedule"
RULE_SOURCE = "season in the heading, year from the refund schedule heading"


def resolve_refund_seasons(record: dict) -> dict:
    """Refund calendar PDF: the heading "Summer 2026, Fall 2026, and Spring 2027 Refund Schedule"
    names three terms. A heading that starts with a season and no year ("Fall Refund Date: ...")
    gets the one term of that season named there. Other documents are not touched."""
    schedule = next(
        (s for s in record["sections"] if REFUND_SCHEDULE in (s["heading"] or "")), None
    )
    if schedule is None:
        return record
    by_season: dict[str, list[str]] = {}
    for t in terms_in(schedule["heading"]):
        by_season.setdefault(t.split()[0], []).append(t)
    for s in record["sections"]:
        first = (s["heading"] or "").split(" ", 1)[0].capitalize()
        if not s["terms"] and len(by_season.get(first, [])) == 1 and not terms_in(s["heading"]):
            set_terms(s, list(by_season[first]), RULE_SOURCE)
    return record


def covered_terms(record: dict) -> dict:
    """What a refund page names in its headings and tables: terms with a year, and seasons that
    have no year (those are not terms)."""
    text = " ".join(f"{heading_path(s)} {table_text(s['markdown'])}" for s in record["sections"])
    return {"covered_terms": terms_in(text), "seasons_without_year": seasons_without_year(text)}
