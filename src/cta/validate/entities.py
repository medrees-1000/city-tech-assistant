"""HTML entities ("&rsquo;", "&amp;", "&#8217;") left in processed text. Any one is a failure:
the parse or clean step should have decoded it (the standard library's html.unescape)."""

import json
import re
from pathlib import Path

from cta.validate.findings import Finding

ENTITY = re.compile(r"&(?:#\d+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]{1,31});")


def entities_in(value: object) -> list[str]:
    """Every entity found in the strings of a JSON value (nested dicts and lists)."""
    if isinstance(value, str):
        return ENTITY.findall(value)
    if isinstance(value, dict):
        return [e for v in value.values() for e in entities_in(v)]
    if isinstance(value, list):
        return [e for v in value for e in entities_in(v)]
    return []


def check_entities(processed: Path) -> tuple[int, list[Finding]]:
    """(number of JSON records scanned, one failure per record that still has an entity)."""
    paths = sorted(processed.glob("**/*.json"))
    findings = []
    for path in paths:
        found = entities_in(json.loads(path.read_text(encoding="utf-8")))
        if found:
            shown = ", ".join(sorted(set(found)))
            name = str(path.relative_to(processed))
            findings.append(Finding("html_entity", "fail", f"still has {shown}", name))
    return len(paths), findings
