"""The contact line after an abstention (Phase 3, step 4c). Plain code: the model never writes it.

Contact policy v2: a contact is added only when the office clearly applies, else none.
`office_for` returns the office of the first rule that applies:
  1. a calendar abstain -> the Registrar;
  2. a chain "no record" abstain -> the department of the code prefix (one of four), else none;
  3. exactly one of the four departments named in the question (alias or course prefix);
  4. a first-person account cue ("my gpa") from config/contacts.yaml (`account_only` words such as
     "login" are account questions too, but name no office).
Nothing else adds a contact (no chunk-source map, no fallback office).
`add_contact` appends "Contact <name>: <email>, <phone>." to an abstained answer, once.
"""

import re
from functools import lru_cache

import yaml

from cta.index.departments import detect_departments
from cta.settings import ROOT

CONFIG = ROOT / "config" / "contacts.yaml"


@lru_cache(maxsize=1)
def load_contacts() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def named_department(question: str) -> str | None:
    found = detect_departments(question)
    return next(iter(found)) if len(found) == 1 else None


def has_word(text: str, words: list[str]) -> bool:
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)


def account_cue(question: str, contacts: dict) -> bool:
    """Does the question hold an account word (one with an office, or one with no office)?"""
    text = question.lower()
    return has_word(text, contacts.get("account_only", [])) or any(
        has_word(text, words) for words in contacts["cues"].values()
    )


def cue_office(question: str, contacts: dict) -> str | None:
    text = question.lower()
    for office, words in contacts["cues"].items():
        if any(re.search(rf"\b{re.escape(w)}\b", text) for w in words):
            return office
    return None


def office_for(question: str, ans, contacts: dict | None = None) -> str | None:
    """The office that clearly applies, or None (then no contact is added)."""
    contacts = contacts or load_contacts()
    reason = ans.abstain_reason or ""
    if reason.startswith("calendar_"):
        return "registrar"
    if reason == "chain_no_record":
        return named_department(question)
    return named_department(question) or cue_office(question, contacts)


def contact_line(key: str, contacts: dict | None = None) -> str:
    entry = (contacts or load_contacts())["offices"][key]
    parts = []
    for e in entry["emails"]:
        parts.append(e if isinstance(e, str) else f"{e['address']} ({e['for']})")
    parts += entry["phones"]
    line = f"Contact {entry['name']}: {', '.join(parts)}."
    return f"{line} {entry['also']}" if entry.get("also") else line


def add_contact(ans, question: str, contacts: dict | None = None) -> str | None:
    """Append the line to an abstained answer unless it is already there. Returns the office key,
    or None when the answer is not an abstention or no office clearly applies (then nothing is
    touched)."""
    if not ans.abstained:
        return None
    contacts = contacts or load_contacts()
    key = office_for(question, ans, contacts)
    if key is None:
        return None
    line = contact_line(key, contacts)
    if line not in ans.text:
        ans.text = f"{ans.text} {line}"
    return key
