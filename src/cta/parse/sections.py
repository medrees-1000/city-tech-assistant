"""Helpers that turn a page record's sections into text units (used later by chunking)."""

import re

TABLE_SEPARATOR = re.compile(r"^\|(?: *:?-{3,}:? *\|)+ *$", re.M)  # the | --- | --- | line


def has_table(markdown: str) -> bool:
    return bool(TABLE_SEPARATOR.search(markdown))


def merge_tables_into_parents(sections: list[dict]) -> list[dict]:
    """A table stays with the intro text above it ("see the following table:").

    A section that contains a table is merged into its parent section (the text under the heading
    above it), after the parent's text, with its own heading kept. A table whose parent has no text
    of its own stays a unit of its own. Other sections are unchanged. Order is kept."""
    units: list[dict] = []
    for s in sections:
        parent = s["parents"][-1] if s["parents"] else None
        target = None
        if parent and has_table(s["markdown"]):
            target = next(
                (u for u in reversed(units)
                 if u["heading"] == parent["heading"] and u["level"] == parent["level"]),
                None,
            )  # fmt: skip
        if target is None:
            units.append({**s, "merged": []})
            continue
        title = f"{'#' * max(s['level'], 1)} {s['heading']}" if s["heading"] else ""
        target["markdown"] += "\n\n" + "\n\n".join(x for x in (title, s["markdown"]) if x)
        target["merged"].append(s["heading"])
    return units
