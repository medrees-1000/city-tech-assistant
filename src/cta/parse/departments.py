"""Department PDFs -> records in data/processed/departments/<dept>/ (overview + one per program).

Run: uv run python -m cta.parse.departments
Everything printed is either kept (sections, degree maps), listed as stripped (with its
reason), listed as a repair, or counted (course cards, page footers).
cta.validate.departments proves it.
"""

import json
import re
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from cta.parse.dept_pdf import (
    COURSE_CODE,
    LEGACY,
    RULE_ID,
    TERMINAL,
    Block,
    DegreeMap,
    PLine,
    ProgramTree,
    PTable,
    Stream,
    flow,
    kind,
    parse_program,
    program_title,
    read_stream,
    repair_broken,
    split_parts,
)
from cta.parse.html import to_sections
from cta.parse.pdf_docs import Repairs, table_markdown
from cta.parse.terms import tag_terms
from cta.settings import ROOT

DEPARTMENTS = {
    "CST-NYT": "CST-NYT-2026-09-10-19-16-13.pdf",
    "DENT-NYT": "DENT-NYT-2026-09-10-19-16-25.pdf",
    "EET-NYT": "EET-NYT-2026-09-10-19-16-28.pdf",
    "MATH-NYT": "MATH-NYT-2026-09-10-19-16-47.pdf",
}
WEB_TERM_LABEL = "2026 Fall Term"
WEB_TERM_SOURCE = "CLAUDE.md (the owner's reading of the web page); no collected page prints it"
SHORTHAND = re.compile(r"PRE_|^[A-Z]+(?:_[A-Z0-9]+)+$")
TRUNCATED = re.compile(
    r"\b(?:Prerequisites?|Corequisites?|Pre/?co-?requisites?|PRE|CO|PRE/CO)\b\s*:\s*[A-Z]{2,5}$"
)  # a rule that stops right after the subject of a course code ("Prerequisite: CST")
RULE_SPLIT = re.compile(r"(?:^|,\s*)(\d{6})\s*-\s*")
CODE_IN_LIST = re.compile(r"\b([A-Z]{2,5}) ?(\d{3,4}[A-Z]{0,2})\s+-\s")
SENTENCE = re.compile(r"(?<=[.!?])\s+")
MIN_PROSE_WORDS = (
    8  # shorter repeated lines ("AND", "English Composition") are structure, not rule text
)
ADVISORY = re.compile(r"^Advisory Commission")


def file_date(name: str) -> str | None:
    """The date in the file name: CST-NYT-2026-09-10-19-16-13.pdf -> 2026-09-10T19:16:13."""
    m = re.search(r"-(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})\.pdf$", name)
    return f"{m[1]}-{m[2]}-{m[3]}T{m[4]}:{m[5]}:{m[6]}" if m else None


def slugify(title: str) -> str:
    parts = [p.strip() for p in title.split(" - ") if p.strip()]
    base = " ".join(parts[:2]) if len(parts) >= 2 else (parts[0] if parts else title)
    return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")


def norm(text: str) -> str:
    return re.sub(r"\W+", " ", text).lower().strip()


# ---- the chair block and the web comparison ------------------------------------------------------

TITLES = re.compile(r"^(Professor|Prof\.?|Dr\.?|Mr\.?|Ms\.?|Mrs\.?)\s+", re.I)


def parse_chair(lines: list[PLine]) -> dict:
    """The chair block as printed: name, office and phone lines (no email is printed)."""
    texts = [ln.plain for ln in lines]
    phone = next((t for t in texts if t.lower().startswith("phone")), None)
    others = [t for t in texts if t is not phone]
    return {
        "lines": texts,
        "name": others[0] if others else None,
        "office": others[1] if len(others) > 1 else None,
        "phone": phone.split(":", 1)[1].strip() if phone and ":" in phone else phone,
        "email": None,
    }


def room_code(text: str | None) -> str | None:
    m = re.search(r"\b([A-Z]{1,3})-?(\d{3,4})\b", text or "")
    return f"{m[1]}-{m[2]}" if m else None


def load_root_contact(processed: Path, dept: str) -> dict | None:
    """The CONTACT US block of the department root page (data/processed/contacts/<dept>.json)."""
    path = processed / "contacts" / f"{dept}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    panel = next((p for p in data["panels"] if p["heading"] == "CONTACT US"), None)
    if panel is None:
        return None
    text = panel["markdown"]
    phone = re.search(r"Phone:\s*([\d-]+)", text)
    email = re.search(r"Email:\s*(\S+)", text)
    return {
        "room": room_code(text),
        "phone": phone[1] if phone else None,
        "email": email[1] if email else None,
        "source_page": data["source_pages"][0],
        "printed": text,
    }


def compare_contact(pdf: dict, root: dict | None) -> dict | None:
    """The PDF "Chair" block against the CONTACT US block of the department root page."""
    if root is None:
        return None
    pairs = [
        ("office", room_code(pdf["office"]), root["room"]),
        ("phone", re.sub(r"\D", "", pdf["phone"] or ""), re.sub(r"\D", "", root["phone"] or "")),
        ("email", (pdf["email"] or "").lower(), (root["email"] or "").lower()),
    ]
    rows = []
    for name, a, b in pairs:
        shown = {"office": pdf["office"], "phone": pdf["phone"], "email": pdf["email"]}[name]
        result = "not printed in the PDF" if not a else "match" if a == b else "MISMATCH"
        rows.append(
            {
                "field": name,
                "pdf": shown,
                "root_page": root["room" if name == "office" else name],
                "result": result,
            }
        )
    return {
        "source": root["source_page"],
        "rows": rows,
        "matches": all(r["result"] in ("match", "not printed in the PDF") for r in rows),
    }


def compare_chair(pdf: dict, web: dict | None) -> tuple[dict, list[dict]]:
    """(chair to use, comparison rows). The web page wins; every difference is a row."""
    rows = []
    if web is None:
        return {
            "source": "pdf (no chairperson.aspx record)",
            **{k: pdf[k] for k in ("name", "office", "phone", "email")},
        }, []
    checks = [
        ("name", pdf["name"], web.get("name"), lambda v: norm(TITLES.sub("", v or ""))),
        ("office", pdf["office"], web.get("room"), room_code),
        ("phone", pdf["phone"], web.get("phone"), lambda v: re.sub(r"\D", "", v or "")),
        ("email", pdf["email"], web.get("email"), lambda v: (v or "").lower()),
    ]
    for field_name, a, b, key in checks:
        if a is None:
            result = "not printed in the PDF"
        elif key(a) == key(b):
            result = "match"
        else:
            result = "MISMATCH (web wins)"
        rows.append({"field": field_name, "pdf": a, "web": b, "result": result})
    chair = {
        "name": web.get("name"),
        "office": web.get("room"),
        "phone": web.get("phone"),
        "email": web.get("email"),
        "role": web.get("role"),
        "source": "chairperson.aspx (web wins)",
    }
    return chair, rows


# ---- rule notes ------------------------------------------------------------------------------


def parse_rule_notes(text: str) -> list[dict]:
    """ "013081 - CUNY proficiency in English, 032849 - ENG 1101 Corequisite" -> [{id, printed}]."""
    text = text.strip()
    if text in ("", "-"):
        return []
    parts = RULE_SPLIT.split(text)
    items: list[dict] = []
    if parts[0].strip():
        items.append(
            {"id": None, "printed": parts[0].strip()}
        )  # text with no rule ID in front of it
    for i in range(1, len(parts), 2):
        items.append({"id": parts[i], "printed": parts[i + 1].strip().rstrip(",").strip()})
    return items


def resolve_notes(
    card_notes: str, resolve: Callable[[str], str | None], flags: list[str], where: str
) -> list[dict]:
    out = []
    for item in parse_rule_notes(card_notes):
        entry = {**item, "resolved": None, "status": "no rule id"}
        if item["id"]:
            text = resolve(item["id"])
            entry["resolved"] = text
            if text is None:
                entry["status"] = "unresolved"
                flags.append(f"{where}: rule {item['id']} did not resolve")
            elif norm(text) == norm(item["printed"]):
                entry["status"] = "match"
            else:
                entry["status"] = "differs"
                flags.append(
                    f"{where}: rule {item['id']} printed {item['printed']!r}, "
                    f"rule lookup says {text!r}"
                )
        shown = entry["resolved"] or item["printed"]
        if SHORTHAND.search(shown):
            entry["shorthand"] = True
            flags.append(f"{where}: shorthand left as printed: {shown!r}")
        if TRUNCATED.search(item["printed"]):
            entry["truncated"] = True
            flags.append(f"{where}: text looks truncated: {item['printed']!r}")
        out.append(entry)
    return out


def collect_rule_ids(trees: list[ProgramTree]) -> set[str]:
    ids: set[str] = set()
    for tree in trees:
        for m in tree.maps:
            for sem in m.semesters:
                for card in sem.cards:
                    ids.update(RULE_ID.findall(card.rule_notes))
    return ids


# ---- stripping ---------------------------------------------------------------------------------


def sentences(text: str) -> list[str]:
    return [s for s in SENTENCE.split(text.replace("**", "")) if s.strip()]


def fully_bold(text: str) -> bool:
    """A paragraph that is all bold is a directive or label ("Complete ALL of ...")."""
    return text.startswith("**") and text.endswith("**") and text.count("**") == 2


def boilerplate_sentences(trees: dict[str, list[ProgramTree]]) -> set[str]:
    """Prose sentences of requirement groups that appear in two or more departments.

    These are the generic General Education rule texts (double duty, flexible core, ...).
    Bold directives and sentences found in only one department are program-specific and are kept."""
    seen: dict[str, set[str]] = {}
    for dept, progs in trees.items():
        for tree in progs:
            for g in tree.groups:
                for k, _, text in g.blocks:
                    if k == "p" and not fully_bold(text):
                        for s in sentences(text):
                            seen.setdefault(norm(s), set()).add(dept)
    return {s for s, who in seen.items() if len(who) >= 2 and len(s.split()) >= MIN_PROSE_WORDS}


LABEL_SMALL_WORDS = {"and", "or", "of", "the", "in", "for", "to", "a"}


def is_label(block: Block) -> bool:
    """A bare label: a short plain paragraph in Title Case with no final punctuation
    ("Writing Intensive", "Required Common Core")."""
    kind_, _, text = block
    words = text.split()
    return (
        kind_ == "p"
        and "\n" not in text
        and 0 < len(words) <= 6
        and not fully_bold(text)
        and not text.endswith(TERMINAL)
        and all(w[0].isupper() or w.lower() in LABEL_SMALL_WORDS for w in words if w[0].isalpha())
    )


def strip_boilerplate(
    blocks: list[Block], generic: set[str], where: str, stripped: list[dict]
) -> list[Block]:
    """Remove generic rule text. A label whose text under it was all removed is removed as well."""
    kept: list[Block | None] = []
    dropped_all: list[bool] = []
    for k, lv, text in blocks:
        if k != "p" or fully_bold(text):
            kept.append((k, lv, text))
            dropped_all.append(False)
            continue
        keep, drop = [], []
        for s in sentences(text):
            (drop if norm(s) in generic else keep).append(s)
        if drop:
            stripped.append({"type": "rule_dump_text", "text": " ".join(drop), "where": where})
        kept.append((k, lv, " ".join(keep) if drop else text) if keep else None)
        dropped_all.append(not keep)
    for i, block in enumerate(blocks):
        if kept[i] is None or not is_label(block):
            continue
        j = i + 1
        while j < len(blocks) and dropped_all[j]:
            j += 1
        ends_label = j == len(blocks) or blocks[j][0] == "h" or is_label(blocks[j])
        if j > i + 1 and ends_label:
            reason = "all the text under it was stripped as generic rule text"
            stripped.append(
                {"type": "empty_label", "text": block[2], "where": where, "reason": reason}
            )
            kept[i] = None
    return [b for b in kept if b is not None]


def strip_inactive(items: list, stripped: list[dict], where: str) -> list:
    """Remove "(Inactive)" courses: the bullet ending in "(Inactive)" with its wrapped lines."""
    out = list(items)
    i = 0
    while i < len(out):
        ln = out[i]
        if not isinstance(ln, PTable) and "(Inactive)" in ln.plain:
            start = i
            if ln.plain.strip() == "(Inactive)" or not ln.plain.startswith("•"):
                while start > 0 and not (
                    not isinstance(out[start], PTable) and out[start].plain.startswith("•")
                ):
                    start -= 1
            removed = [x for x in out[start : i + 1] if not isinstance(x, PTable)]
            context = (
                out[start - 1].plain if start > 0 and not isinstance(out[start - 1], PTable) else ""
            )
            stripped.append({"type": "inactive_course", "text": " ".join(x.plain for x in removed),
                             "page": ln.page, "where": where, "after": context})  # fmt: skip
            del out[start : i + 1]
            i = start
            continue
        i += 1
    return out


# ---- the rendering of program parts -------------------------------------------------------


def blocks_markdown(blocks: list[Block]) -> list[Block]:
    return blocks


MAP_HEADER = [
    "Requirement",
    "Rule notes",
    "Notes",
    "Minimum Grade",
    "Minimum GPA",
    "Area",
    "Actual Credits",
    "Progress Credits",
    "Contact Hours",
    "Clinical",
    "Criticality",
]


SEMESTER_ROW = re.compile(
    r"^(?P<lead>.*?)\s+(?P<actual>\d+(?: - \d+)?)\s+(?P<progress>\d+(?: - \d+)?)$"
)


def semester_label(printed: str) -> str:
    """ "Year 1 Fall 11 11" -> "Year 1 Fall (11 credits)". The PDF header over the row is
    "Year Semester Actual Credits Progress Credits", so the two numbers are actual and progress
    credits. One number is shown when they are equal, both are labelled when they differ."""
    m = SEMESTER_ROW.match(printed)
    if not m:
        return printed
    actual, progress = m["actual"], m["progress"]
    if actual == progress:
        return f"{m['lead']} ({actual} credits)"
    return f"{m['lead']} ({actual} actual credits, {progress} progress credits)"


def map_labels(maps: list[DegreeMap]) -> list[str]:
    """The map name; maps that share a name get the PDF page they start on (the PDF prints no
    track or year to tell them apart)."""
    names = Counter(m.name for m in maps)
    return [f"{m.name} (PDF page {m.page})" if names[m.name] > 1 else m.name for m in maps]


def map_blocks(
    maps: list[DegreeMap], rules: dict[tuple, list], tracks_note: dict[int, str], labels: list[str]
) -> tuple[list[Block], dict[tuple[str, str], list[str]]]:
    """Blocks of the degree maps, and the rule IDs of each semester table, keyed by the map and
    semester headings. The rule notes cells hold only the resolved text; the IDs go on the
    section."""
    blocks: list[Block] = []
    rule_ids: dict[tuple[str, str], list[str]] = {}
    for n, m in enumerate(maps):
        map_heading = f"Degree map: {labels[n]}"
        blocks.append(("h", 3, map_heading))
        info = (
            f"Total degree map credits: {m.total_credits}. "
            f"Effective catalog year (as printed): {m.effective_year}."
        )
        blocks.append(("p", 0, info))
        if tracks_note.get(n):
            blocks.append(("p", 0, tracks_note[n]))
        if m.narrative:
            blocks.append(("p", 0, m.narrative))
        for s_i, sem in enumerate(m.semesters):
            sem_heading = semester_label(sem.printed)
            blocks.append(("h", 4, sem_heading))
            ids: list[str] = []
            rows = [MAP_HEADER]
            for c_i, card in enumerate(sem.cards):
                notes = rules.get((n, s_i, c_i), [])
                ids += [x["id"] for x in notes if x["id"] and x["id"] not in ids]
                shown = "; ".join(x["resolved"] or x["printed"] for x in notes)
                f = card.fields
                values = [f.get(key, "-") for key in MAP_HEADER[3:]]
                rows.append([" OR ".join(card.options), shown or "-", card.notes or "-", *values])
            rule_ids[(map_heading, sem_heading)] = ids
            body = table_markdown(rows[1:]).splitlines()[2:] if len(rows) > 1 else []
            head = MAP_HEADER
            md = "\n".join(
                [
                    "| " + " | ".join(head) + " |",
                    "| " + " | ".join("---" for _ in head) + " |",
                    *body,
                ]
            )
            blocks.append(("table", 0, md))
    return blocks, rule_ids


# ---- table fixes: promote a header, drop constant columns -----------------------------------

CONSTANT_VALUES = ("-", "No")


def table_cells(line: str) -> list[str]:
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def table_line(cells: list[str]) -> str:
    return "| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |"


def fix_table(md: str) -> tuple[str, dict]:
    """Promote the first data row to the header when the header is empty and that row is clearly
    a header (all upper case, like "ITEM | COST"). Drop every column (except the first) whose
    cells are all "-" or "No". A column with any other value is never dropped."""
    lines = md.split("\n")
    head, rows = table_cells(lines[0]), [table_cells(ln) for ln in lines[2:]]
    done: dict = {"promoted": None, "dropped": []}
    if not any(head) and rows and all(c and c.isupper() for c in rows[0]):
        head, rows = rows[0], rows[1:]
        done["promoted"] = head
    keep = [0] + [
        i
        for i in range(1, len(head))
        if not rows or not all(r[i] in CONSTANT_VALUES for r in rows if len(r) > i)
    ]
    done["dropped"] = [head[i] or f"column {i + 1}" for i in range(len(head)) if i not in keep]
    if done["promoted"] is None and not done["dropped"]:
        return md, done
    head = [head[i] for i in keep]
    rows = [[r[i] for i in keep if i < len(r)] for r in rows]
    out = [table_line(head), "| " + " | ".join("---" for _ in head) + " |"]
    return "\n".join(out + [table_line(r) for r in rows]), done


def fix_tables(blocks: list[Block]) -> tuple[list[Block], list[dict]]:
    """fix_table on every table block; returns the new blocks and the repairs to record."""
    out: list[Block] = []
    repairs: list[dict] = []
    stack: dict[int, str] = {}
    for kind_, level, text in blocks:
        if kind_ == "h":
            stack = {k: v for k, v in stack.items() if k < level}
            stack[level] = text
        if kind_ != "table":
            out.append((kind_, level, text))
            continue
        where = " / ".join(stack[k] for k in sorted(stack))
        md, done = fix_table(text)
        if done["promoted"]:
            repairs.append({"kind": "table_header_promoted", "where": where,
                            "header": done["promoted"]})  # fmt: skip
        if done["dropped"]:
            repairs.append({"kind": "dropped_columns", "where": where, "columns": done["dropped"],
                            "rule": "every cell is '-' or 'No'"})  # fmt: skip
        out.append((kind_, level, md))
    return out, repairs


WRAPPER_HEADING = "Simple Requirements"
NO_LEVELS = "(No Requirement Levels)"


def drop_wrapper_sections(sections: list[dict], where: str) -> tuple[list[dict], list[dict]]:
    """Drop the "Simple Requirements" section when its only content is "(No Requirement Levels)".
    Its child sections stay, and their heading path still shows the wrapper heading."""
    out: list[dict] = []
    dropped: list[dict] = []
    for s in sections:
        only = s["markdown"].replace("**", "").strip()
        if s["heading"] == WRAPPER_HEADING and only == NO_LEVELS:
            dropped.append(
                {"type": "wrapper_section", "text": NO_LEVELS, "heading": WRAPPER_HEADING,
                 "where": where}
            )  # fmt: skip
        else:
            out.append(s)
    if dropped and not any(p["heading"] == WRAPPER_HEADING for s in out for p in s["parents"]):
        dropped[0]["text"] = f"{WRAPPER_HEADING} {NO_LEVELS}"  # no child keeps the heading
    return out, dropped


def map_signature(m: DegreeMap) -> tuple:
    def card_key(c) -> tuple:
        return (tuple(c.options), c.rule_notes, c.notes, tuple(sorted(c.fields.items())))

    semesters = tuple((s.printed, tuple(card_key(c) for c in s.cards)) for s in m.semesters)
    return (m.total_credits, m.effective_year, m.narrative, semesters)


def dedupe_maps(maps: list[DegreeMap]) -> tuple[list[DegreeMap], dict[int, list[DegreeMap]]]:
    """One copy of each distinct map. Maps whose content is identical (only the name may differ)
    are repeats per track: the first is kept and the others are listed under it."""
    kept: list[DegreeMap] = []
    repeats: dict[int, list[DegreeMap]] = {}
    index: dict[tuple, int] = {}
    for m in maps:
        sig = map_signature(m)
        if sig in index:
            repeats[index[sig]].append(m)
        else:
            index[sig] = len(kept)
            repeats[len(kept)] = []
            kept.append(m)
    return kept, repeats


def tracks_text(kept: DegreeMap, others: list[DegreeMap]) -> str | None:
    if not others:
        return None
    names = [kept.name] + [o.name for o in others]
    if len(set(names)) == 1:
        return (
            f"This degree map is printed {len(names)} times in the PDF with identical content "
            "and the same name; no track names are printed. One copy is kept."
        )
    return (
        "This degree map is printed once per track with identical content. Applies to: "
        + "; ".join(names)
        + "."
    )


CREDIT_LINE = re.compile(r"^(?:Earn|Complete)\b.*\bcredits?\b", re.I)


def credit_totals(tree: ProgramTree) -> dict:
    """The credit totals printed for a program: each degree map's total, and the credit lines of the
    requirement groups ("Earn at least 120 credits", ...)."""
    lines: list[str] = []
    for g in tree.groups:
        for _, _, text in g.blocks:
            for line in text.split("\n"):
                plain = line.replace("**", "").strip()
                if CREDIT_LINE.match(plain) and plain not in lines:
                    lines.append(plain)
    return {
        "degree_maps": [{"name": m.name, "total_credits": m.total_credits} for m in tree.maps],
        "overall_requirement_lines": lines,
    }


def credit_flags(tree: ProgramTree) -> list[str]:
    """A degree map whose whole credit range is below the program's "Earn at least" number."""
    earn = []
    for line in credit_totals(tree)["overall_requirement_lines"]:
        if line.lower().startswith("earn at least"):
            earn += [int(n) for n in re.findall(r"\d+", line)]
    flags = []
    for m in tree.maps:
        nums = [int(n) for n in re.findall(r"\d+", m.total_credits)]
        if earn and nums and max(nums) < min(earn):
            flags.append(
                f"credit totals disagree: degree map {m.name!r} totals {m.total_credits!r}, "
                "the requirements say 'Earn at least "
                f"{'-'.join(map(str, sorted(set(earn))))} credits'"
            )
    return flags


def codes_in_tree(tree: ProgramTree) -> dict[str, set[str]]:
    """Course codes a program lists: group bullets and the options of degree map cards."""
    where: dict[str, set[str]] = {}
    for g in tree.groups:
        for k, _, text in g.blocks:
            if k != "list":
                continue
            for line in text.split("\n"):
                for subj, num in CODE_IN_LIST.findall(line.replace("**", "")):
                    where.setdefault(f"{subj} {num}", set()).add("requirements")
    for m in tree.maps:
        for sem in m.semesters:
            for card in sem.cards:
                for opt in card.options:
                    mm = COURSE_CODE.match(opt)
                    if mm:
                        where.setdefault(f"{mm[1]} {mm[2]}", set()).add("degree map")
    return where


def legacy_lines(tree: ProgramTree) -> list[dict]:
    """Every program line that mentions an MST or DPT code (kept, flagged: the catalog wins)."""
    found = []
    for g in tree.groups:
        for _, _, text in g.blocks:
            for line in text.split("\n"):
                if LEGACY.search(line):
                    found.append(
                        {
                            "where": f"requirements: {g.title}",
                            "text": line.replace("**", "").strip(),
                        }
                    )
    for m in tree.maps:
        for sem in m.semesters:
            for card in sem.cards:
                for opt in card.options:
                    if LEGACY.search(opt):
                        found.append({"where": f"degree map {m.name}: {sem.printed}", "text": opt})
    for _, _, text in tree.general:
        for line in text.split("\n"):
            if LEGACY.search(line):
                found.append({"where": "general", "text": line.replace("**", "").strip()})
    return found


# ---- overview, course cards and records ------------------------------------------------------


def map_printed(m: DegreeMap) -> str:
    """The printed text of a degree map, rebuilt from the parse tree (for the check)."""
    from cta.parse.dept_pdf import CARD_KEYS, SEMESTER_HEADER

    parts = ["Degree Map Name", m.name, "Total Degree Map Credits", m.total_credits,
             "Degree Map Effective Catalog Year", m.effective_year]  # fmt: skip
    if m.narrative:
        parts += ["Degree Map Narrative", m.narrative]
    for sem in m.semesters:
        parts += [SEMESTER_HEADER, sem.printed]
        for c in sem.cards:
            parts += ["Requirement Select", *c.options, *["OR"] * max(len(c.options) - 1, 0)]
            parts += ["Notes", c.rule_notes] + (["Notes", c.notes] if c.notes_count > 1 else [])
            for key in CARD_KEYS[1:]:
                if key in c.fields:
                    parts += [key, c.fields[key]]
    return "\n".join(parts)


def overview_blocks(
    items: list, repairs: Repairs, stripped: list[dict], flags: list[str]
) -> tuple[list[Block], dict]:
    """Overview sections. The chair block is kept; Advisory Commission sections are stripped."""
    blocks: list[Block] = []
    chair: dict = {}
    sections: list[tuple[str, list]] = []
    for item in items:
        if kind(item) == "dept":
            continue
        if kind(item) == "h12":
            sections.append((item.plain, []))
        elif sections:
            sections[-1][1].append(item)
        else:
            flags.append(f"overview: text before the first heading: {getattr(item, 'plain', '')!r}")
    for title, body in sections:
        if ADVISORY.match(title):
            stripped.append(
                {
                    "type": "advisory_commission",
                    "text": " ".join([title] + [b.plain for b in body]),
                    "lines": len(body) + 1,
                    "page": body[0].page if body else 0,
                }
            )
            continue
        if title == "Chair":
            chair = parse_chair([b for b in body if not isinstance(b, PTable)])
            blocks.append(("h", 2, title))
            blocks.append(("p", 0, "\n".join(chair["lines"])))
            continue
        blocks.append(("h", 2, title))
        blocks += flow(body, repairs)
    return blocks, chair


def course_region(items: list) -> tuple[list[dict], Counter]:
    """Course cards after the "Courses" heading: titles, and a count of every printed character."""
    cards: list[dict] = []
    chars: Counter = Counter("Courses")  # the heading itself
    for item in items:
        if isinstance(item, PTable):
            for row in item.rows:
                chars.update("".join(row).replace(" ", ""))
            continue
        chars.update(item.plain.replace(" ", ""))
        if kind(item) == "title":
            wraps = (
                cards
                and cards[-1]["page"] == item.page
                and abs(item.top - cards[-1]["top"]) <= 1.6 * item.size
                and not re.search(r"\(\d+(?:\.\d+)? cr\)$", cards[-1]["title"])
            )
            if wraps:
                cards[-1]["title"] += " " + item.plain
                cards[-1]["top"] = item.top
            else:
                cards.append({"title": item.plain, "page": item.page, "top": item.top})
    return [{"title": c["title"], "page": c["page"]} for c in cards], chars


def blank_programs_page(items: list, parts_overview_end: int) -> bool:
    return False


class Parsed:
    """One department PDF after reading and splitting (before records are built)."""

    def __init__(self, dept: str, path: Path):
        self.dept, self.path = dept, path
        self.stream: Stream = read_stream(path)
        self.parts = split_parts(self.stream.items)
        self.trees: list[ProgramTree] = []
        self.stray: list[dict] = []
        for title_lines, items in self.parts.programs:
            inactive: list[dict] = []
            items = strip_inactive(items, inactive, program_title(title_lines))
            tree = parse_program(title_lines, items, self.stream.repairs)
            tree.stripped.extend(inactive)
            if (
                not tree.has_requirements
                and not tree.maps
                and not any(k == "p" and len(t) > 60 for k, _, t in tree.general)
            ):
                general = "General " if tree.has_general else ""
                text = f"{tree.title} {general}" + " ".join(t for _, _, t in tree.general)
                self.stray.append({"title": tree.title, "text": text, "page": title_lines[0].page})
                continue
            self.trees.append(tree)


def programs_page_is_blank(parsed: Parsed) -> bool:
    """The "Programs" heading stands alone on its page (nothing else printed on it)."""
    heading = next(
        (
            i
            for i in parsed.stream.items
            if not isinstance(i, PTable) and kind(i) == "h12" and i.plain == "Programs"
        ),
        None,
    )
    if heading is None:
        return False
    others = [
        i
        for i in parsed.stream.items
        if not isinstance(i, PTable) and i.page == heading.page and i is not heading
    ]
    return not others


def dropped_headings(blocks: list[Block], sections: list[dict]) -> list[str]:
    """Headings with no section of their own that are not above one (empty sections are dropped)."""
    present = {s["heading"] for s in sections} | {
        h["heading"] for s in sections for h in s["parents"]
    }
    return [text for kind_, _, text in blocks if kind_ == "h" and text not in present]


def repair_strings(obj, repairs: list[dict], where: str):
    """Apply the known broken-glyph repairs to every string in a record, recording each one."""
    if isinstance(obj, str):
        return repair_broken(obj, repairs, where)
    if isinstance(obj, list):
        return [repair_strings(x, repairs, where) for x in obj]
    if isinstance(obj, dict):
        return {k: repair_strings(v, repairs, where) for k, v in obj.items()}
    return obj


def base_fields(parsed: Parsed, doc_type: str) -> dict:
    name = parsed.path.name
    labels = sorted({m.effective_year for t in parsed.trees for m in t.maps if m.effective_year})
    return {
        "department": parsed.dept,
        "department_name": parsed.parts.dept_title.removesuffix(" Department"),
        "doc_type": doc_type,
        "scope": "department",
        "source_file": f"data/pdfs/{name}",
        "file_name": name,
        "file_date": file_date(name),
        "term": None,  # never invented: the two labels below are stored as printed
        "term_label_pdf": labels,
        "last_updated": None,  # the department PDFs print no update date; file_date is the date
        "term_label_web": WEB_TERM_LABEL,
        "term_label_web_source": WEB_TERM_SOURCE,
        "page_count": len(parsed.stream.footers),
        "status": "collected",
        "index": True,
        "index_reason": None,
        "note": None,
    }


def hegis_cip(blocks: list[Block]) -> dict:
    for i, (k, _, text) in enumerate(blocks):
        if k == "h" and text.startswith("HEGIS Code") and i + 1 < len(blocks):
            nums = blocks[i + 1][2].split()
            if len(nums) == 2:
                return {"hegis": nums[0], "cip": nums[1]}
    return {"hegis": None, "cip": None}


def build_overview(
    parsed: Parsed, chair_web: dict | None, root_contact: dict | None = None
) -> dict:
    stripped: list[dict] = []
    flags: list[str] = []
    blocks, chair_pdf = overview_blocks(
        parsed.parts.overview, parsed.stream.repairs, stripped, flags
    )
    kind_of_heading = (
        "blank_programs_page" if programs_page_is_blank(parsed) else "programs_heading"
    )
    stripped.append({"type": kind_of_heading, "text": "Programs", "page": 0})
    for s in parsed.stray:
        stripped.append(
            {"type": "stray_program", "text": s["text"], "page": s["page"], "title": s["title"]}
        )
    cards, card_chars = course_region(parsed.parts.courses)
    chair, comparison = compare_chair(chair_pdf, chair_web)
    contact = compare_contact(chair_pdf, root_contact)
    blocks, table_repairs = fix_tables(blocks)
    chair_pdf["embed"] = (
        False  # a department-office contact, not the chair; the web page is the source
    )
    record = {
        **base_fields(parsed, "department"),
        "title": parsed.parts.dept_title,
        "chair": chair,
        "chair_pdf": chair_pdf,
        "chair_comparison": comparison,
        "contact_pdf_vs_root": contact,
        "sections": (sections := to_sections([("h", 1, parsed.parts.dept_title), *blocks])),
        "dropped_empty_headings": dropped_headings(
            [("h", 1, parsed.parts.dept_title), *blocks], sections
        ),
        "stripped": stripped,
        "course_cards": cards,
        "course_card_chars": dict(card_chars),
        "page_footers": parsed.stream.footers,
        "flags": flags,
        "repairs": table_repairs,
    }
    for s in sections:
        if s["heading"] == "Chair":
            s["embed"] = False  # the web page is the only contact source
    differs = [i["field"] for i in comparison if i["result"].startswith("MISMATCH")]
    if differs and contact is not None and contact["matches"]:
        flags.append(
            "source mismatch, not a data error: the PDF 'Chair' block differs from "
            f"chairperson.aspx in {', '.join(differs)}, but matches the root page contact block "
            "(it is the department office contact); not indexed"
        )
    elif differs:
        flags.append(
            f"PDF 'Chair' block differs from chairperson.aspx in {', '.join(differs)}"
            + (" and from the root page contact block" if contact else " (no root contact block)")
        )
    return record


def build_program(
    parsed: Parsed, tree: ProgramTree, generic: set[str], resolve: Callable[[str], str | None]
) -> dict:
    stripped = list(tree.stripped)
    flags = list(tree.flags)
    where = tree.title
    for entry in stripped:
        if entry["type"] == "total_credits" and not entry.get("zero"):
            flags.append(
                f"{where}: a 'Total ... Credits' line with non-zero values: {entry['text']!r}"
            )
    groups = []
    for g in tree.groups:
        blocks = strip_boilerplate(g.blocks, generic, f"{where} / {g.title}", stripped)
        groups.append((g, blocks))
    notes = tree.notes
    kept_maps, repeats = dedupe_maps(tree.maps)
    for n, others in repeats.items():
        for o in others:
            stripped.append(
                {
                    "type": "repeated_degree_map",
                    "text": map_printed(o),
                    "name": o.name,
                    "same_as": kept_maps[n].name,
                }
            )
    rules: dict[tuple, list] = {}
    for n, m in enumerate(kept_maps):
        for s_i, sem in enumerate(m.semesters):
            for c_i, card in enumerate(sem.cards):
                rules[(n, s_i, c_i)] = resolve_notes(
                    card.rule_notes,
                    resolve,
                    flags,
                    f"{where} / {m.name} / {sem.printed} / card {c_i + 1}",
                )
    tracks = {n: tracks_text(kept_maps[n], repeats[n]) for n in range(len(kept_maps))}
    flags += credit_flags(tree)
    if len([p for p in tree.title.split(" - ") if p.strip()]) < 3:
        flags.append(f"{where}: the program title is printed incomplete: {tree.title!r}")
    names = Counter(m.name for m in kept_maps)
    flags += [
        f"{where}: {n} different degree maps have the same name {name!r}; the PDF prints no "
        "track or year to tell them apart, so each is labelled with its PDF page"
        for name, n in names.items()
        if n > 1
    ]
    blocks: list[Block] = [("h", 1, tree.title)]
    if tree.has_general:
        blocks += [("h", 2, "General"), *tree.general]
    if tree.has_requirements:
        blocks.append(("h", 2, "Requirements"))
        blocks += notes
        for g, gblocks in groups:
            blocks += [("h", 4, g.title), ("p", 0, f"**Type** {g.type_label}"), *gblocks]
    if tree.has_maps_heading:
        blocks.append(("h", 2, "Degree Maps"))
    labels = map_labels(kept_maps)
    map_part, rule_ids = map_blocks(
        kept_maps, rules, {k: v for k, v in tracks.items() if v}, labels
    )
    blocks += map_part
    blocks, table_repairs = fix_tables(blocks)
    sections, wrappers = drop_wrapper_sections(to_sections(blocks), where)
    stripped += wrappers
    for s in sections:
        if s["heading"] == "Degree Maps" or any(
            p["heading"] == "Degree Maps" for p in s["parents"]
        ):
            s["generated"] = True  # built from the degree map data, not printed text
        parent = s["parents"][-1]["heading"] if s["parents"] else None
        if (parent, s["heading"]) in rule_ids:
            s["rule_ids"] = rule_ids[(parent, s["heading"])]
    codes = codes_in_tree(tree)
    parts = [p.strip() for p in tree.title.split(" - ")]
    maps_out = []
    for n, m in enumerate(kept_maps):
        d = asdict(m)
        d["label"] = labels[n]
        d["tracks"] = [m.name] + [o.name for o in repeats[n]]
        d["repeats_dropped"] = len(repeats[n])
        d["printed"] = map_printed(m)
        for s_i, sem in enumerate(d["semesters"]):
            for c_i, card in enumerate(sem["cards"]):
                card["rules"] = rules[(n, s_i, c_i)]
        maps_out.append(d)
    return {
        **base_fields(parsed, "program"),
        "title": tree.title,
        "program": {
            "slug": slugify(tree.title),
            "name": parts[0] if parts else tree.title,
            "award_code": parts[1] if len(parts) > 1 else None,
            "award": parts[2] if len(parts) > 2 else None,
            "title_complete": len(parts) >= 3,
            **hegis_cip(tree.general),
            "credit_totals": credit_totals(tree),
            "courses": {c: sorted(w) for c, w in sorted(codes.items())},
            "legacy_lines": legacy_lines(tree),
            "degree_maps": maps_out,
        },
        "sections": sections,
        "dropped_empty_headings": dropped_headings(blocks, sections),
        "stripped": stripped,
        "flags": flags,
        "repairs": table_repairs,
    }


def finalize(record: dict, ligatures: list[dict]) -> dict:
    """Apply the broken-glyph repairs to every string and list all repairs on the record."""
    repairs: list[dict] = []
    out = repair_strings(record, repairs, record.get("title", ""))
    out["repairs"] = [*record.get("repairs", []), *repairs, *ligatures]
    tag_terms(out)
    return out


# ---- build all, link courses, write -----------------------------------------------------------


def load_web_chair(processed: Path, dept: str) -> dict | None:
    path = processed / "pages" / dept / "chairperson.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("chair")


def ligature_repairs(parsed: Parsed) -> list[dict]:
    counts: Counter = Counter()
    for item in parsed.stream.repairs.items:
        counts[(item["kind"], item["char"], item["replaced_with"])] += 1
    return [
        {"kind": k, "char": c, "replaced_with": r, "count": n} for (k, c, r), n in counts.items()
    ]


def build_all(
    pdf_dir: Path,
    processed: Path,
    resolve: Callable[[str], str | None],
    only: list[str] | None = None,
):
    """(records by department, parsed by department). Records: overview first, then the programs."""
    parsed = {
        d: Parsed(d, pdf_dir / name) for d, name in DEPARTMENTS.items() if only is None or d in only
    }
    generic = boilerplate_sentences({d: p.trees for d, p in parsed.items()})
    records: dict[str, list[dict]] = {}
    for dept, p in parsed.items():
        ligs = ligature_repairs(p)
        root = load_root_contact(processed, dept)
        out = [finalize(build_overview(p, load_web_chair(processed, dept), root), ligs)]
        for tree in p.trees:
            out.append(finalize(build_program(p, tree, generic, resolve), []))
        records[dept] = out
    return records, parsed, generic


def record_name(record: dict) -> str:
    return (
        "overview.json"
        if record["doc_type"] == "department"
        else f"program-{record['program']['slug']}.json"
    )


def write_records(records: dict[str, list[dict]], out_dir: Path) -> None:
    for dept, recs in records.items():
        folder = out_dir / dept
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("*.json"):
            old.unlink()
        for rec in recs:
            (folder / record_name(rec)).write_text(
                json.dumps(rec, indent=1, ensure_ascii=False) + "\n", "utf-8"
            )


def link_courses(records: dict[str, list[dict]], processed: Path, all_codes: set[str]) -> dict:
    """Fill `programs` on every course record; report program courses missing from the catalog."""
    listed: dict[str, list[dict]] = {}
    for dept, recs in records.items():
        for rec in recs:
            if rec["doc_type"] != "program":
                continue
            for code, where in rec["program"]["courses"].items():
                entry = {
                    "department": dept,
                    "program": rec["title"],
                    "slug": rec["program"]["slug"],
                }
                listed.setdefault(code, []).append({**entry, "in": where})
    paths = sorted((processed / "courses").rglob("*.json"))
    have: set[str] = set()
    for path in paths:
        course = json.loads(path.read_text(encoding="utf-8"))
        have.add(course["code"])
        course["programs"] = listed.get(course["code"], [])
        path.write_text(json.dumps(course, indent=1, ensure_ascii=False), encoding="utf-8")
    missing = {c: v for c, v in listed.items() if c not in all_codes}
    return {
        "courses_updated": len(paths),
        "courses_with_programs": sum(
            1 for p in paths if json.loads(p.read_text("utf-8"))["programs"]
        ),
        "program_codes": len(listed),
        "codes_not_in_catalog": missing,
        "codes_in_catalog_without_record": sorted(
            c for c in listed if c in all_codes and c not in have
        ),
    }


def main() -> int:
    import httpx

    from cta.crawl.catalog import RuleResolver
    from cta.crawl.fetcher import Fetcher
    from cta.crawl.store import RawStore
    from cta.parse.dept_pdf import RULE_ID  # noqa: F401
    from cta.settings import build_user_agent, load_sources
    from cta.validate.departments import run_department_checks

    processed = ROOT / "data" / "processed"
    pdf_dir = ROOT / "data" / "pdfs"
    cache_path = processed / "rules_cache.json"
    first = {d: Parsed(d, pdf_dir / n) for d, n in DEPARTMENTS.items()}
    ids = collect_rule_ids([t for p in first.values() for t in p.trees])
    cache = json.loads(cache_path.read_text("utf-8")) if cache_path.exists() else {}
    missing = sorted(i for i in ids if i not in cache)
    print(f"{len(ids)} distinct rule IDs in the PDFs, {len(missing)} not in the rule cache")
    sources = load_sources()
    fetcher = Fetcher(
        httpx.Client(timeout=30),
        RawStore(ROOT / "data" / "raw"),
        build_user_agent(sources),
        set(sources["allowed_hosts"]),
        min_interval=sources["crawl"]["min_interval_seconds"],
    )
    resolver = RuleResolver(fetcher, sources["catalog_api"], cache_path)
    try:
        for rid in missing:
            resolver.resolve(rid)
    finally:
        resolver.save()
    print(f"{resolver.calls} rule lookups made")
    resolve = lambda i: (resolver.cache.get(i) or {}).get("text")  # noqa: E731
    records, parsed, generic = build_all(pdf_dir, processed, resolve)
    write_records(records, processed / "departments")
    summary = json.loads((processed / "catalog_run.json").read_text("utf-8"))
    report = link_courses(records, processed, set(summary["all_codes"]))
    (processed / "departments" / "course_links.json").write_text(
        json.dumps(report, indent=1), encoding="utf-8"
    )
    failures = 0
    for dept, recs in records.items():
        findings = run_department_checks(recs, parsed[dept], generic)
        failures += sum(f.severity == "fail" for f in findings)
        print(dept, {"records": len(recs)}, f"{len(findings)} findings")
        for f in findings:
            print(f"   [{f.severity.upper()}] {f.check}: {f.message}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
