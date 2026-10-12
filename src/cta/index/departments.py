"""Which department does a question name? (Phase 3, step 2a; the filter is in cta.index.search.)

Two signals, both from config/departments.yaml: an alias in the text (whole word, case-insensitive:
"Computer Systems Technology", "CST", "ETET") and a course code ("EET 3672" or "EET3672") whose
prefix belongs to a department. No network, no database.
"""

import re
from functools import lru_cache
from pathlib import Path

import yaml

from cta.settings import ROOT

CONFIG = ROOT / "config" / "departments.yaml"
COURSE_CODE = re.compile(r"\b([A-Za-z]{2,5})\s?(\d{3,4}[A-Za-z]{0,2})\b")


@lru_cache(maxsize=1)
def load_departments(path: Path = CONFIG) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["departments"]


def alias_pattern(alias: str) -> re.Pattern:
    """Whole-word, case-insensitive (every alias starts and ends with a letter or digit)."""
    return re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE)


def detect_departments(question: str, departments: dict | None = None) -> set[str]:
    """Department ids named by an alias or by the prefix of a course code in the question."""
    departments = departments or load_departments()
    found: set[str] = set()
    for dept_id, info in departments.items():
        if any(alias_pattern(a).search(question) for a in info["aliases"]):
            found.add(dept_id)
    by_prefix = {
        p.upper(): dept_id for dept_id, info in departments.items() for p in info["prefixes"]
    }
    for match in COURSE_CODE.finditer(question):
        dept_id = by_prefix.get(match.group(1).upper())
        if dept_id:
            found.add(dept_id)
    return found


def allowed_sql() -> str:
    """SQL condition (one %s parameter: the detected ids) that keeps a chunk: any chunk whose
    scope is not 'department', or whose department is among the detected ids."""
    return "(scope <> 'department' OR department = ANY(%s))"
