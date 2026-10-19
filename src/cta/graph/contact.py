"""The contact line after an abstention (Phase 3, step 4c). Plain code: the model never writes it.

Contact policy v2: a contact is added only when the office clearly applies, else none.
`offices_for` returns the offices of the first rule that applies:
  1. a calendar abstain -> the Registrar;
  2. a chain "no record" abstain -> the department of the code prefix (one of four), else none;
  3. exactly one of the four departments named in the question (alias or course prefix);
  4. a first-person account cue ("my gpa") from config/contacts.yaml (`account_only` words such as
     "login" are account questions too, but name no office);
  5. only when none of those applies: topic words (`topic_cues` in the same file), at most two
     offices in the order of `topic_priority`.
Nothing else adds a contact (no chunk-source map, no fallback office).
`add_contact` appends "Contact <name>: <email>, <phone>." to an abstained answer, once per office.
It only adds text to the end of an abstention: it never changes the ABSTAIN prefix, whether the
answer abstained, or which question is refused.
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


def personal_account_cue(question: str, contacts: dict) -> bool:
    """Is this abstention shown as a personal-account refusal? An `account_only` word always counts;
    so does an office cue that names account data by itself (my gpa, my balance ...); a possessive
    plus an office noun ("my financial aid", "my tuition") counts only together with an account
    signal ("status", "did my", "why is my" ...). `cue_office` still chooses the card."""
    text = question.lower().replace("\u2019", "'")
    if has_word(text, contacts.get("account_only", [])):
        return True
    nouns = contacts.get("noun_cues", [])
    data_cues = [w for words in contacts["cues"].values() for w in words if w not in nouns]
    if has_word(text, data_cues):
        return True
    return has_word(text, nouns) and has_word(text, contacts.get("account_signals", []))


def cue_office(question: str, contacts: dict) -> str | None:
    text = question.lower()
    for office, words in contacts["cues"].items():
        if any(re.search(rf"\b{re.escape(w)}\b", text) for w in words):
            return office
    return None


def topic_offices(question: str, contacts: dict) -> list[str]:
    """Offices whose topic words appear in the question: at most two, in `topic_priority` order."""
    text = question.lower()
    for phrase in contacts.get("topic_ignore", []):
        text = text.replace(phrase.lower(), " ")
    hits = [
        office
        for office in contacts.get("topic_priority", [])
        if has_word(text, [w.lower() for w in contacts.get("topic_cues", {}).get(office, [])])
    ]
    return hits[:2]


def offices_for(question: str, ans, contacts: dict | None = None) -> list[str]:
    """The offices that clearly apply (the main one first), or [] (then no contact is added)."""
    contacts = contacts or load_contacts()
    reason = ans.abstain_reason or ""
    if reason.startswith("calendar_"):
        return ["registrar"]
    if reason == "chain_no_record":
        dept = named_department(question)
        return [dept] if dept else []
    if reason == "chain_outside_departments":
        return []  # the course is in none of the four departments: no office applies
    first = named_department(question) or cue_office(question, contacts)
    return [first] if first else topic_offices(question, contacts)


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
    keys = offices_for(question, ans, contacts)
    if not keys:
        return None
    # the main office last: the page strips that last line into its card and keeps any other line
    for key in reversed(keys):
        line = contact_line(key, contacts)
        if line not in ans.text:
            ans.text = f"{ans.text} {line}"
    return keys[0]
