"""Department PDFs (Coursedog catalog printouts) -> parts, programs, requirement groups, maps.

The PDFs are Prince-rendered "cards": page 1 is full width, every other page has two text columns
that are read left then right, and a card (a program, a degree map) flows on from one column or
page to
the next. Everything here works from character positions and font sizes, never from the text stream.

This module reads and splits. cta.parse.departments turns the parts into records.
"""

import re
from dataclasses import dataclass, field, replace

import pdfplumber

from cta.parse.pdf_docs import (
    BULLETS,
    PLine,
    Repairs,
    in_box,
    lines_from_chars,
)

GUTTER = 303.0
COLUMN_BASE = {"L": 30.0, "F": 30.0, "R": 306.6}  # left edge of the text in each column
FOOTER = re.compile(r"^\d+ / \d+$")
# The broken glyph U+2BD1 stands for a lost "ff" ligature. It is repaired only in these known words.
BROKEN_WORDS = {"O⯑ers": "Offers", "O⯑ce": "Office"}


@dataclass
class PTable:
    """A data table (not a frame or a requirement box), as rows of cell text."""

    page: int
    col: str
    top: float
    rows: list[list[str]]
    header: bool  # the first row is a header (printed bold)


@dataclass
class Stream:
    items: list = field(default_factory=list)  # PLine or PTable, in reading order
    footers: list[dict] = field(default_factory=list)
    repairs: Repairs = field(default_factory=Repairs)
    body_chars: list[str] = field(
        default_factory=list
    )  # every printed character (completeness check)


def two_column(page) -> bool:
    """A page is two-column when no character crosses or sits in the gutter between the columns."""
    for c in page.chars:
        if c["text"].isspace():
            continue
        mid_x = (c["x0"] + c["x1"]) / 2
        if c["x0"] < GUTTER < c["x1"] or 300.5 <= mid_x <= 305.5:
            return False
    return True


def data_tables(page) -> list:
    """Tables with two or more columns and three rows, narrower than a page (not frames)."""
    found = []
    for t in page.find_tables():
        rows = t.extract()
        ncols = max((len(r) for r in rows), default=0)
        if ncols >= 2 and len(rows) >= 3 and t.bbox[2] - t.bbox[0] < 400:
            found.append((t, rows))
    return found


def clean_cell(text: str | None) -> str:
    return " ".join((text or "").split())


def make_table(t, rows, page, page_no: int, col: str, repairs: Repairs) -> PTable:
    cells = [[clean_cell(c) for c in r] for r in rows]
    first = t.rows[0].cells
    bold_first = []
    for box in first:
        if box is None:
            continue
        chars = [c for c in page.chars if in_box(c, box) and not c["text"].isspace()]
        bold_first.append(bool(chars) and all("bold" in c["fontname"].lower() for c in chars))
    return PTable(page_no, col, t.bbox[1], cells, bool(bold_first) and all(bold_first))


def read_stream(path) -> Stream:
    """All lines and data tables of a PDF in reading order, plus page footers."""
    stream = Stream()
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            tables = [] if page_no == 1 else data_tables(page)
            boxes = [t.bbox for t, _ in tables]
            height = float(page.height)
            chars = [c for c in page.chars if not c["text"].isspace()]
            stream.body_chars += [c["text"] for c in chars]
            body = [c for c in chars if not any(in_box(c, b) for b in boxes)]
            footer = [c for c in body if c["top"] > 800]
            body = [c for c in body if c["top"] <= 800]
            for ln in lines_from_chars(footer, page_no, height, stream.repairs):
                if FOOTER.match(ln.plain):
                    stream.footers.append({"page": page_no, "text": ln.plain})
                else:
                    body_line = ln  # not a footer: keep it (unexpected text below the page body)
                    stream.items.append(body_line)
            if page_no == 1 or not two_column(page):
                groups = [("F", body)]
            else:
                groups = [
                    ("L", [c for c in body if (c["x0"] + c["x1"]) / 2 < GUTTER]),
                    ("R", [c for c in body if (c["x0"] + c["x1"]) / 2 >= GUTTER]),
                ]
            for col, cs in groups:
                lines = lines_from_chars(cs, page_no, height, stream.repairs)
                body_size = max(
                    {ln.size for ln in lines},
                    key=lambda z: sum(ln.size == z for ln in lines),
                    default=0,
                )
                margin = max((ln.x1 for ln in lines if ln.size == body_size), default=0.0)
                col_items = [(ln.top, replace(ln, margin=margin, col=col)) for ln in lines]
                for t, rows in tables:
                    mid_x = (t.bbox[0] + t.bbox[2]) / 2
                    if col == "F" or (col == "L") == (mid_x < GUTTER):
                        col_items.append(
                            (t.bbox[1], make_table(t, rows, page, page_no, col, stream.repairs))
                        )
                stream.items += [item for _, item in sorted(col_items, key=lambda x: x[0])]
    return stream


def repair_broken(text: str, repairs: list[dict], context: str) -> str:
    """Replace the broken glyph in the known words; anything else is left for the checks."""
    for broken, fixed in BROKEN_WORDS.items():
        if broken in text:
            repairs.append({"kind": "broken_glyph", "printed": broken, "repaired": fixed,
                            "count": text.count(broken), "where": context})  # fmt: skip
            text = text.replace(broken, fixed)
    return text


# ---- classification and splitting ------------------------------------------------------------

TERMINAL = (".", "!", "?", ":", ")", '"', "\u201d")
NUM = re.compile(r"^(\d{1,2}|[a-z])\.\s")
RULE_ID = re.compile(r"\b\d{6}\b")
LEGACY = re.compile(r"\b(MST|DPT) ?\d{4}")
Block = tuple[str, int, str]


def kind(item) -> str:
    if isinstance(item, PTable):
        return "table"
    s = item.size
    if s >= 14:
        return "dept"
    if 11.5 <= s <= 13:
        return "h12"
    if 9.9 <= s <= 10.4 and item.bold_all:
        return "title"
    if 9.2 <= s <= 9.7 and item.bold_all:
        return "h9"
    if 8.1 <= s <= 8.5:
        return "h8"
    return "body"


@dataclass
class Parts:
    dept_title: str
    overview: list
    programs: list  # [(title lines, items)]
    courses: list


def split_parts(items: list) -> Parts:
    """Overview (before "Programs"), programs (until "Courses") and the course cards after them."""
    dept_title = next((i.plain for i in items if kind(i) == "dept"), "")
    idx_programs = next(
        (n for n, i in enumerate(items) if kind(i) == "h12" and i.plain == "Programs"), None
    )
    idx_courses = next(
        (n for n, i in enumerate(items) if kind(i) == "h12" and i.plain == "Courses"), None
    )
    if idx_programs is None or idx_courses is None:
        raise ValueError("no Programs or Courses heading found")
    overview = items[:idx_programs]
    region = items[idx_programs + 1 : idx_courses]
    programs: list[tuple[list, list]] = []
    for item in region:
        if kind(item) == "title":
            if programs and not programs[-1][1] and programs[-1][0][-1].page == item.page \
                    and abs(item.top - programs[-1][0][-1].top) <= 1.6 * item.size:  # fmt: skip
                programs[-1][0].append(item)  # the title wraps onto a second line
            else:
                programs.append(([item], []))
        elif programs:
            programs[-1][1].append(item)
    return Parts(dept_title, overview, programs, items[idx_courses + 1 :])


def program_title(lines: list) -> str:
    return " ".join(ln.plain for ln in lines)


def split_by(items: list, wanted: tuple[str, ...]) -> dict[str, list]:
    """Group items under the h9 headings in `wanted` (General, Requirements, Degree Maps)."""
    out: dict[str, list] = {}
    current = None
    for item in items:
        if kind(item) == "h9" and item.plain in wanted:
            current = item.plain
            out[current] = []
        elif current is not None:
            out[current].append(item)
    return out


# ---- flow: lines -> paragraphs, nested lists, tables --------------------------------------


def table_md(t: PTable) -> str:
    from cta.parse.pdf_docs import table_markdown

    rows = t.rows
    if t.header:
        body = table_markdown(rows[1:]).splitlines()[2:]
        head = "| " + " | ".join(rows[0]) + " |"
        sep = "| " + " | ".join("---" for _ in rows[0]) + " |"
        return "\n".join([head, sep, *body])
    return table_markdown(rows)


def render_list(entries: list[tuple[float, str]]) -> str:
    """Bullets nested by indentation: the more indented an item, the deeper it is."""
    levels = sorted({round(x0) for x0, _ in entries})
    return "\n".join(f"{'  ' * levels.index(round(x0))}- {text}" for x0, text in entries)


def flow(items: list, repairs: Repairs, body_gap: float = 1.8) -> list[Block]:
    """Paragraphs, nested bullet or numbered lists and tables, in order (no headings here)."""
    from cta.parse.pdf_docs import continues, join_lines, strip_bullet

    blocks: list[Block] = []
    para: list[PLine] = []
    entries: list[tuple[float, list[PLine]]] = []  # list items: (x0, lines)
    prev: PLine | None = None

    def join(lines: list[PLine]) -> str:
        return join_lines([ln.text for ln in lines], [ln.plain for ln in lines], repairs)

    def flush() -> None:
        nonlocal para, entries
        if para:
            blocks.append(("p", 0, join(para)))
            para = []
        if entries:
            blocks.append(("list", 0, render_list([(x0, join(ls)) for x0, ls in entries])))
            entries = []

    for item in items:
        if isinstance(item, PTable):
            flush()
            blocks.append(("table", 0, table_md(item)))
            prev = None
            continue
        ln: PLine = item
        broke = prev is None or ln.page != prev.page or ln.top < prev.top - 1  # next column or page
        gap = float("inf") if broke else ln.top - prev.top
        base = COLUMN_BASE.get(ln.col, 30.0)  # indentation is measured from the column's left edge
        starts_item = ln.plain.startswith(BULLETS) or bool(NUM.match(ln.plain))
        near = prev is not None and gap <= body_gap * ln.size
        glued = (
            broke
            and prev is not None
            and not prev.plain.endswith(TERMINAL)
            and re.match(r"[a-z0-9]", ln.plain)
        )
        if starts_item:
            if para:
                flush()
            text = strip_bullet(ln.text) if ln.plain.startswith(BULLETS) else ln.text
            entries.append((ln.x0 - base, [replace(ln, text=text, plain=strip_bullet(ln.plain))]))
        elif entries and ln.x0 - base > entries[-1][0] + 1 and (near or glued):
            entries[-1][1].append(ln)  # wrapped (indented) line of a list item
        elif para and (near or glued) and (glued or continues(para[-1], ln)):
            para.append(ln)
        else:
            flush()
            para.append(ln)
        prev = ln
    flush()
    return blocks


# ---- programs ----------------------------------------------------------------------------------

CARD_KEYS = ("Notes", "Minimum Grade", "Minimum GPA", "Area", "Actual Credits", "Progress Credits",
             "Contact Hours", "Clinical", "Criticality")  # fmt: skip
SEMESTER_HEADER = "Year Semester Actual Credits Progress Credits"
TOTAL_HEADERS = (
    "Total General Education Credits Total Major Credits",
    "Total Minor Credits Total Elective Credits",
)
COURSE_CODE = re.compile(r"^([A-Z]{2,5}) ?(\d{3,4}[A-Z]{0,2})\b")


@dataclass
class Card:
    """One "Requirement Select" card of a degree map."""

    options: list[str]  # option texts, in order ("OR" is the separator between them)
    rule_notes: str  # the first Notes value as printed ("013081 - text, 032849 - text")
    notes: str  # the second Notes value (requirement note)
    fields: dict  # Minimum Grade ... Criticality, as printed
    page: int
    notes_count: int = 2


@dataclass
class Semester:
    printed: str  # the printed row, e.g. "Year 1 Fall 11 11"
    cards: list[Card] = field(default_factory=list)


@dataclass
class DegreeMap:
    name: str
    total_credits: str
    effective_year: str  # as printed, e.g. "2027 -"
    narrative: str
    semesters: list[Semester]
    page: int


@dataclass
class Group:
    """A requirement group: title, printed type, and its text as blocks."""

    title: str
    type_label: str
    blocks: list[Block]
    page: int


@dataclass
class ProgramTree:
    title: str
    general: list[Block]
    notes: list[Block]  # text before the first requirement group ("(No Requirement Levels)")
    groups: list[Group]
    maps: list[DegreeMap]
    stripped: list[dict]
    flags: list[str]
    has_requirements: bool = False
    has_maps_heading: bool = False
    has_general: bool = False


def key_of(line: PLine) -> str | None:
    for key in CARD_KEYS:
        if line.text.startswith(f"**{key}**"):
            return key
    return None


def key_value(line: PLine, key: str) -> str:
    return line.plain[len(key) :].strip()


def parse_card(lines: list[PLine], flags: list[str], where: str) -> Card:
    """A card: option lines (bullets and OR), then the Notes ... Criticality key lines."""
    options: list[str] = []
    cur: list[str] = []
    i = 0
    while i < len(lines) and key_of(lines[i]) is None:
        ln = lines[i]
        if ln.plain == "OR":
            if cur:
                options.append(" ".join(cur))
                cur = []
        elif ln.plain.startswith(BULLETS):
            if cur:
                options.append(" ".join(cur))
            cur = [ln.plain.lstrip("".join(BULLETS)).strip()]
        else:
            cur.append(ln.plain)
        i += 1
    if cur:
        options.append(" ".join(cur))
    values: list[tuple[str, str]] = []
    while i < len(lines):
        key = key_of(lines[i])
        if key is None:
            flags.append(f"{where}: line outside a key block: {lines[i].plain!r}")
            i += 1
            continue
        chunk = [key_value(lines[i], key)]
        i += 1
        while i < len(lines) and key_of(lines[i]) is None:
            chunk.append(lines[i].plain)
            i += 1
        values.append((key, " ".join(c for c in chunk if c).strip()))
    notes = [v for k, v in values if k == "Notes"]
    fields = {k: v for k, v in values if k != "Notes"}
    if len(notes) != 2:
        flags.append(f"{where}: {len(notes)} Notes entries (expected 2)")
    rule = notes[0] if notes else ""
    note = notes[1] if len(notes) > 1 else ""
    return Card(options, rule, note, fields, lines[0].page if lines else 0, len(notes))


def parse_maps(
    items: list, stripped: list[dict], flags: list[str], repairs: Repairs, where: str
) -> list[DegreeMap]:
    maps: list[DegreeMap] = []
    lines = [i for i in items if not isinstance(i, PTable)]
    idx = 0
    pending: dict = {}
    sem: Semester | None = None
    card_lines: list[PLine] = []
    mode = ""

    def finish_card() -> None:
        nonlocal card_lines
        if card_lines and sem is not None:
            sem.cards.append(parse_card(card_lines, flags, f"{where} card {len(sem.cards) + 1}"))
        card_lines = []

    def finish_map() -> None:
        nonlocal pending, sem
        finish_card()
        if pending:
            maps.append(
                DegreeMap(
                    pending.get("name", ""),
                    pending.get("total", ""),
                    pending.get("year", ""),
                    pending.get("narrative", ""),
                    pending.get("semesters", []),
                    pending.get("page", 0),
                )
            )
        pending = {}
        sem = None

    while idx < len(lines):
        ln = lines[idx]
        text = ln.plain
        if text == "Degree Map Name":
            finish_map()
            pending = {"semesters": [], "page": ln.page}
            idx += 1
            name = []
            while idx < len(lines) and lines[idx].plain != "Total Degree Map Credits":
                name.append(lines[idx].plain)
                idx += 1
            pending["name"] = " ".join(name)
            continue
        if text == "Total Degree Map Credits":
            pending["total"] = lines[idx + 1].plain if idx + 1 < len(lines) else ""
            idx += 2
            continue
        if text == "Degree Map Effective Catalog Year":
            pending["year"] = lines[idx + 1].plain if idx + 1 < len(lines) else ""
            idx += 2
            continue
        if text == "Degree Map Narrative":
            idx += 1
            nar = []
            while idx < len(lines) and lines[idx].plain not in (SEMESTER_HEADER, "Degree Map Name"):
                nar.append(lines[idx])
                idx += 1
            pending["narrative"] = " ".join(n.plain for n in nar)
            continue
        if text == SEMESTER_HEADER:
            finish_card()
            row = lines[idx + 1].plain if idx + 1 < len(lines) else ""
            sem = Semester(row)
            pending.setdefault("semesters", []).append(sem)
            idx += 2
            continue
        if text == "Requirement Select":
            finish_card()
            card_lines = []
            idx += 1
            mode = "card"
            continue
        if text in TOTAL_HEADERS:
            finish_card()
            values = lines[idx + 1].plain if idx + 1 < len(lines) else ""
            stripped.append({"type": "total_credits", "text": f"{text} {values}", "page": ln.page,
                             "zero": set(values.split()) <= {"0"}})  # fmt: skip
            idx += 2
            continue
        if mode == "card" and sem is not None:
            card_lines.append(ln)
        else:
            flags.append(f"{where}: text outside a degree map card: {text!r} (p{ln.page})")
        idx += 1
    finish_map()
    return maps


def parse_program(title_lines: list, items: list, repairs: Repairs) -> ProgramTree:
    title = program_title(title_lines)
    stripped: list[dict] = []
    flags: list[str] = []
    sections = split_by(items, ("General", "Requirements", "Degree Maps"))
    general = general_blocks(sections.get("General", []), repairs)
    notes, groups = requirement_groups(sections.get("Requirements", []), repairs)
    maps = parse_maps(sections.get("Degree Maps", []), stripped, flags, repairs, title)
    return ProgramTree(
        title, general, notes, groups, maps, stripped, flags,
        "Requirements" in sections, "Degree Maps" in sections, "General" in sections,
    )  # fmt: skip


def general_blocks(items: list, repairs: Repairs) -> list[Block]:
    """The General section: sub-headings (size 8.3) at level 3, text between them as flow."""
    blocks: list[Block] = []
    body: list = []
    for item in items:
        if kind(item) == "h8":
            blocks += flow(body, repairs)
            body = []
            blocks.append(("h", 3, item.plain))
        else:
            body.append(item)
    blocks += flow(body, repairs)
    return blocks


def requirement_groups(items: list, repairs: Repairs) -> tuple[list[Block], list[Group]]:
    """Requirement groups. A group title is a bold line followed by the bold line "Type"."""
    starts = []
    for n, item in enumerate(items[:-1]):
        nxt = items[n + 1]
        if isinstance(item, PTable) or isinstance(nxt, PTable):
            continue
        if item.bold_all and kind(item) == "body" and nxt.plain == "Type" and nxt.bold_all:
            starts.append(n)
    head_end = starts[0] if starts else len(items)
    notes: list[Block] = []
    lead: list = []
    for item in items[:head_end]:
        if kind(item) == "h8":
            notes += flow(lead, repairs)
            lead = []
            notes.append(("h", 3, item.plain))
        else:
            lead.append(item)
    notes += flow(lead, repairs)
    groups: list[Group] = []
    for k, n in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(items)
        title_line = items[n]
        type_line = items[n + 2] if n + 2 < end else None
        body_start = n + 3 if type_line is not None else n + 2
        groups.append(Group(title_line.plain, type_line.plain if type_line is not None else "",
                            flow(items[body_start:end], repairs), title_line.page))  # fmt: skip
    return notes, groups
