"""The contact line after an abstention (Phase 3, step 4c). Plain code: the model never writes it.

`office_for` picks the office by the first rule that applies:
  1. a calendar abstain -> the Registrar;
  2. a chain "no record" abstain -> the department of the code's prefix, else Advisement;
  3. exactly one of the four departments named in the question (alias or course prefix);
  4. a first-person account cue ("my gpa") from config/contacts.yaml;
  5. the owner of the best-ranked chunk (page/<office>/, dept/<dept>/, contact:<owner>,
     catalog course -> its department, pdf/<name> -> pdf_offices);
  6. the fallback (the Registrar).
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


def cue_office(question: str, contacts: dict) -> str | None:
    text = question.lower()
    for office, words in contacts["cues"].items():
        if any(re.search(rf"\b{re.escape(w)}\b", text) for w in words):
            return office
    return None


def chunk_office(chunk: dict, contacts: dict) -> str | None:
    """The office or department that owns a retrieved chunk, from its id."""
    offices, cid = contacts["offices"], chunk["id"]
    if cid.startswith("catalog:"):
        owner = chunk.get("department")
    elif cid.startswith("contact:"):
        owner = cid.removeprefix("contact:")
    elif cid.startswith("pdf/"):
        owner = contacts["pdf_offices"].get(cid.split("/")[1].split("#")[0])
    else:  # page/<owner>/<page>#n or dept/<owner>/<file>#n
        owner = cid.split("/")[1] if cid.count("/") >= 2 else None
    return owner if owner in offices else None


def office_for(question: str, ans, contacts: dict | None = None) -> str:
    contacts = contacts or load_contacts()
    reason = ans.abstain_reason or ""
    if reason.startswith("calendar_"):
        return "registrar"
    if reason == "chain_no_record":
        return named_department(question) or "advisement"
    return (
        named_department(question)
        or cue_office(question, contacts)
        or (chunk_office(ans.sources[0], contacts) if ans.sources else None)
        or contacts["fallback"]
    )


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
    or None when the answer is not an abstention (then nothing is touched)."""
    if not ans.abstained:
        return None
    contacts = contacts or load_contacts()
    key = office_for(question, ans, contacts)
    line = contact_line(key, contacts)
    if line not in ans.text:
        ans.text = f"{ans.text} {line}"
    return key
