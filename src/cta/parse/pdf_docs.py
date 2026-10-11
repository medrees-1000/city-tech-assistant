"""The four smaller PDFs (refund calendar, dropping and withdrawing, special circumstances flyer,
CUNYfirst guide) -> one record each in data/processed/pdfs/<slug>.json.

Records have the shape of the web-page records: title, sections
[{heading, level, parents, markdown}], index, note, and so on. Nothing is dropped silently:
every printed line is either in a section or in `excluded` with the reason (page numbers,
document footers, screenshot annotations).

Run: uv run python -m cta.parse.pdf_docs
"""

import json
import re
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path

import pdfplumber

from cta.parse.html import to_sections
from cta.settings import ROOT

LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}
BULLETS = ("•", "", "▪", "", "·", "●", "◦")
END_PUNCT = (".", "!", "?", ",", ";")  # a bold line ending like this is a sentence, not a heading
TERMINAL = (".", "!", "?", ":", ")", '"', "”")
LINE_TOLERANCE = 2.5
GAP_FACTOR = 0.15  # a gap wider than this fraction of the font size is a space between words


@dataclass
class PLine:
    text: str  # with **bold** markup
    plain: str  # without markup
    page: int
    top: float
    bottom: float
    x0: float
    x1: float
    size: float
    bold_all: bool
    page_height: float = 792.0
    first_word_width: float = 0.0
    margin: float = 0.0  # right edge of the text on this page (set after the page is read)
    col: str = ""  # column the line was read from (departments PDFs): L, R or F (full width)


@dataclass
class Repairs:
    items: list[dict] = field(default_factory=list)

    def ligature(self, char: str) -> str:
        self.items.append({"kind": "ligature", "char": char, "replaced_with": LIGATURES[char]})
        return LIGATURES[char]


# ---- lines from characters ----------------------------------------------------------------


def is_bold(fontname: str) -> bool:
    return "bold" in fontname.lower()


ORDINALS = {"st", "nd", "rd", "th"}


def in_box(c: dict, box: tuple[float, float, float, float]) -> bool:
    """True if the center of the character is inside the box (x0, top, x1, bottom)."""
    return box[0] <= (c["x0"] + c["x1"]) / 2 <= box[2] and box[1] <= mid(c) <= box[3]


def mid(c: dict) -> float:
    return (c["top"] + c["bottom"]) / 2


def is_superscript(c: dict, line_size: float, line_mid: float) -> bool:
    """A smaller character that sits higher than the rest of the line."""
    return c["size"] <= 0.8 * line_size and mid(c) < line_mid - 0.1 * line_size


def words_of(
    chars: list[dict], repairs: Repairs, line_size: float = 0.0, line_mid: float = 0.0
) -> list[dict]:
    """Words (split at gaps) with their text, bold flag and extent.

    A superscript ordinal ("21st", "5th") is joined to its number; any other superscript is written
    as ^text (a footnote mark), so it cannot glue onto the word before it."""
    chars = sorted(chars, key=lambda c: c["x0"])
    words: list[list[dict]] = []
    prev = None
    for c in chars:
        if prev is None or c["x0"] - prev["x1"] > GAP_FACTOR * c["size"]:
            words.append([])
        words[-1].append(c)
        prev = c
    out = []
    for w in words:
        bold = sum(is_bold(c["fontname"]) for c in w) * 2 > len(w)
        text = word_text(w, repairs, line_size, line_mid)
        out.append({"text": text, "bold": bold, "x0": w[0]["x0"], "x1": w[-1]["x1"]})
    return out


def sup_text(run: list[str]) -> str:
    text = "".join(run)
    return text if text in ORDINALS or not text else f"^{text}"


def word_text(w: list[dict], repairs: Repairs, line_size: float, line_mid: float) -> str:
    pieces: list[str] = []
    run: list[str] = []
    for c in w:
        ch = repairs.ligature(c["text"]) if c["text"] in LIGATURES else c["text"]
        if line_size and is_superscript(c, line_size, line_mid):
            run.append(ch)
        else:
            pieces.append(sup_text(run))
            run = []
            pieces.append(ch)
    pieces.append(sup_text(run))
    return "".join(pieces)


def merge_bold_runs(text: str) -> str:
    text = re.sub(r"\*\* \*\*", " ", text)
    return text.replace("****", "")


def lines_from_chars(
    chars: list[dict], page_no: int, page_height: float, repairs: Repairs
) -> list[PLine]:
    """Group characters into printed lines (same baseline), top to bottom."""
    chars = [c for c in chars if not c["text"].isspace()]
    groups: list[list[dict]] = []
    for c in sorted(chars, key=lambda c: (mid(c), c["x0"])):
        if groups:
            ref = groups[-1]
            ref_mid = sum(
                mid(x) for x in ref if x["size"] >= 0.85 * max(y["size"] for y in ref)
            ) / sum(1 for x in ref if x["size"] >= 0.85 * max(y["size"] for y in ref))
            if abs(mid(c) - ref_mid) <= 0.45 * max(c["size"], max(x["size"] for x in ref)):
                ref.append(c)
                continue
        groups.append([c])
    lines = []
    for g in groups:
        top_size = max(c["size"] for c in g)
        main = [c for c in g if c["size"] >= 0.85 * top_size]
        words = words_of(g, repairs, top_size, sum(mid(c) for c in main) / len(main))
        parts, run = [], []
        for w in words:
            if w["bold"]:
                run.append(w["text"])
            else:
                if run:
                    parts.append("**" + " ".join(run) + "**")
                    run = []
                parts.append(w["text"])
        if run:
            parts.append("**" + " ".join(run) + "**")
        sizes = sorted(round(c["size"], 1) for c in g)
        lines.append(PLine(
            text=" ".join(parts), plain=" ".join(w["text"] for w in words), page=page_no,
            top=min(c["top"] for c in g), bottom=max(c["bottom"] for c in g),
            x0=min(c["x0"] for c in g), x1=max(c["x1"] for c in g),
            size=sizes[len(sizes) // 2], bold_all=all(is_bold(c["fontname"]) for c in g),
            page_height=page_height, first_word_width=words[0]["x1"] - words[0]["x0"],
        ))  # fmt: skip
    return sorted(lines, key=lambda ln: (ln.top, ln.x0))


# ---- blocks: headings, paragraphs, lists, tables -----------------------------------------


Block = tuple[str, int, str]


def join_lines(parts: list[str], plains: list[str], repairs: Repairs) -> str:
    """Join printed lines. A line ending in a hyphen followed by a letter is joined without a space
    ("three-" + "quarter-time"); every such join is listed in the record."""
    text = parts[0]
    for prev_plain, nxt, nxt_plain in zip(plains, parts[1:], plains[1:], strict=False):
        if re.search(r"[A-Za-z]-$", prev_plain) and re.match(r"[A-Za-z]", nxt_plain):
            repairs.items.append({"kind": "hyphen_join", "text": prev_plain[-12:] + nxt_plain[:12]})
            text += nxt
        else:
            text += " " + nxt
    return merge_bold_runs(text)


def table_markdown(rows: list[list[str]]) -> str:
    """GFM table with a blank header (these tables print no header row)."""
    rows = [[" ".join(c.split()).replace("|", "\\|") for c in r] for r in rows]
    width = max(len(r) for r in rows)
    fmt = lambda cells: "| " + " | ".join(cells + [""] * (width - len(cells))) + " |"  # noqa: E731
    return "\n".join([fmt([""] * width), fmt(["---"] * width), *[fmt(r) for r in rows]])


def trim_empty_edges(rows: list[list[str | None]]) -> list[list[str]]:
    """Drop all-empty rows and columns at the edges (table finder artifacts); keep the rest."""
    rows = [[(c or "").strip() for c in r] for r in rows]
    while rows and not any(rows[0]):
        rows.pop(0)
    while rows and not any(rows[-1]):
        rows.pop()
    if not rows:
        return rows
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    keep = [i for i in range(width) if any(r[i] for r in rows)]
    return [[r[i] for i in range(keep[0], keep[-1] + 1)] for r in rows]


@dataclass
class FlowConfig:
    exclude: object = None  # (PLine) -> reason or None
    heading_min_size: float = 0.0
    body_gap: float = 1.8  # lines closer than this many font sizes can belong to one paragraph
    heading_gap: float = 1.5  # a heading has at least this many font sizes of space above it
    heading_join: float = 1.6  # a bold line this close below a heading line is part of the heading
    notes: bool = False  # excluded lines also record the heading they sit under (kept as notes)


def flow_blocks(
    items: list[tuple[str, object]], config: FlowConfig, repairs: Repairs
) -> tuple[list[Block], list[dict]]:
    """items: ("line", PLine) or ("table", markdown), in page order, top to bottom."""
    blocks: list[Block] = []
    excluded: list[dict] = []
    prev: PLine | None = None
    page_starts: set[int] = set()  # indexes in blocks where a new page begins
    cur_page = None
    para: list[PLine] = []
    item_lines: list[PLine] = []  # lines of the list item being built
    bullet_x = 0.0

    def flush_para() -> None:
        nonlocal para
        if para:
            blocks.append(
                ("p", 0, join_lines([p.text for p in para], [p.plain for p in para], repairs))
            )
            para = []

    def flush_item() -> None:
        nonlocal item_lines
        if item_lines:
            text = join_lines([p.text for p in item_lines], [p.plain for p in item_lines], repairs)
            if blocks and blocks[-1][0] == "list" and blocks[-1][1] == 1:
                blocks[-1] = ("list", 1, blocks[-1][2] + "\n- " + text)
            else:
                blocks.append(("list", 1, "- " + text))
            item_lines = []

    heading: list[PLine] = []

    def flush_heading() -> None:
        nonlocal heading
        if heading:
            text = " ".join(h.plain for h in heading)
            level = 1 if not any(b[0] == "h" for b in blocks) else 2
            blocks.append(("h", level, text))
            heading = []

    def close_all() -> None:
        flush_para()
        flush_item()
        flush_heading()
        # a list that is finished must not absorb the next list item of another list
        if blocks and blocks[-1][0] == "list" and blocks[-1][1] == 1:
            blocks[-1] = ("list", 0, blocks[-1][2])

    for kind, item in items:
        if kind == "table":
            close_all()
            blocks.append(("table", 0, item))
            prev = None
            continue
        line: PLine = item
        reason = config.exclude(line) if config.exclude else None
        if reason:
            entry = {"page": line.page, "text": line.plain, "reason": reason}
            if config.notes:
                under = " ".join(h.plain for h in heading) if heading else None
                entry["heading"] = under or next(
                    (b[2] for b in reversed(blocks) if b[0] == "h"), None
                )
            excluded.append(entry)
            continue
        new_page = line.page != cur_page
        cur_page = line.page
        if new_page:
            page_starts.add(len(blocks) + (1 if (para or item_lines or heading) else 0))
        gap = float("inf") if (prev is None or new_page) else line.top - prev.top
        starts_bullet = line.plain.startswith(BULLETS)
        # heading: bold, no sentence punctuation, space above (or the continuation of a heading)
        if (
            heading
            and line.bold_all
            and gap <= config.heading_join * line.size
            and not starts_bullet
        ):
            heading.append(line)
            prev = line
            continue
        space_above = gap >= config.heading_gap * line.size
        # a bold label ending in ":" is a heading only with space above it ("Example:" is not)
        is_heading_line = (
            line.bold_all and not starts_bullet and not line.plain.endswith(END_PUNCT)
            and line.size >= config.heading_min_size
            and (space_above or (not blocks and not para and not heading))
            and (not line.plain.endswith(":") or space_above)
        )  # fmt: skip
        if is_heading_line:
            close_all()
            heading.append(line)
        elif starts_bullet:
            flush_para()
            flush_heading()
            flush_item()
            bullet_x = line.x0
            item_lines.append(
                replace(line, text=strip_bullet(line.text), plain=strip_bullet(line.plain))
            )
        elif item_lines and line.x0 > bullet_x + 1 and gap <= config.body_gap * line.size:
            item_lines.append(line)  # wrapped line of a list item (indented)
        elif para and gap <= config.body_gap * line.size and continues(para[-1], line):
            para.append(line)
        else:
            close_all()
            para.append(line)
        prev = line
    close_all()
    return merge_across_pages(blocks, page_starts), excluded


def strip_bullet(text: str) -> str:
    for b in BULLETS:
        text = text.removeprefix(b).lstrip()
    return text.replace("** **", " ") if text.startswith("** ") else text


def continues(prev: PLine, line: PLine) -> bool:
    """Does `line` continue the paragraph that `prev` ends?

    Yes if it starts with a lowercase letter or digit, or if its first word would not have fitted on
    `prev` (the text wrapped). A bold label ending in ":" (such as "Example:") always starts a new
    paragraph. Otherwise `prev` ended early on purpose: a new paragraph."""
    if line.bold_all and line.plain.endswith(":"):
        return False
    if re.match(r"[a-z0-9]", line.plain):
        return True
    fits = prev.x1 + 0.25 * prev.size + line.first_word_width <= line.margin - 0.5
    return not fits


def merge_across_pages(blocks: list[Block], page_starts: set[int]) -> list[Block]:
    """A list that continues on the next page is one list; a paragraph continues only if it has no
    final punctuation and the next one starts with a lowercase letter or digit."""
    out: list[Block] = []
    for i, b in enumerate(blocks):
        if out and i in page_starts:
            last = out[-1]
            if last[0] == "list" and b[0] == "list":
                out[-1] = ("list", 0, last[2] + "\n" + b[2])
                continue
            if (
                last[0] == "p"
                and b[0] == "p"
                and not last[2].endswith(TERMINAL)
                and re.match(r"[a-z0-9]", b[2])
            ):
                out[-1] = ("p", 0, last[2] + " " + b[2])
                continue
        out.append(("list", 0, b[2]) if b[0] == "list" else b)
    return out


# ---- metadata and printed dates --------------------------------------------------------


def pdf_date(raw: str | None) -> str | None:
    """PDF metadata date ("D:20260727092220-04'00'") -> ISO text. A missing zone is not invented."""
    if not raw:
        return None
    m = re.match(r"D:(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?(Z|[+-]\d{2}'?\d{2}'?)?", raw)
    if not m:
        return None
    y, mo, d, h, mi, s, tz = m.groups()
    text = f"{y}-{mo}-{d}T{h or '00'}:{mi or '00'}:{s or '00'}"
    if tz == "Z":
        text += "+00:00"
    elif tz:
        text += f"{tz[:3]}:{tz[-3:-1] if tz.endswith(chr(39)) else tz[-2:]}"
    return text


def printed_update(text: str) -> tuple[str | None, str | None]:
    """(raw, ISO date) for a printed "Updated 06/08/2026" or "Last updated: 9/15/26" line."""
    m = re.search(r"(?:Last\s+)?[Uu]pdated:?\s*(\d{1,2})/(\d{1,2})/(\d{2,4})", text)
    if not m:
        return None, None
    month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    year = year + 2000 if year < 100 else year
    return m.group(0), datetime(year, month, day).date().isoformat()


def base_record(path: Path, pdf, meta: dict) -> dict:
    md = pdf.metadata
    return {
        "title": None,
        "source_file": meta["source_file"],
        "doc_type": meta["doc_type"],
        "scope": meta["scope"],
        "department": None,  # these PDFs belong to a central office or to CUNY, not a department
        "term": meta.get("term"),
        "aid_year": meta.get("aid_year"),
        "pdf_last_updated": None,
        "pdf_last_updated_raw": None,
        "file_modified": pdf_date(md.get("ModDate")),
        "file_created": pdf_date(md.get("CreationDate")),
        "metadata_title": md.get("Title"),
        "page_count": len(pdf.pages),
        "text_source": "text layer",
        "status": "collected",
        "index": True,
        "index_reason": None,
        "note": meta.get("note"),
        "sections": [],
        "excluded": [],
        "repairs": [],
    }


def finish(record: dict, blocks: list[Block], excluded: list[dict], repairs: Repairs) -> dict:
    heading = next((b[2] for b in blocks if b[0] == "h"), None)
    record["title"] = record["title"] or heading
    record["sections"] = to_sections(blocks)
    record["excluded"] = excluded
    counts: dict[tuple, int] = {}
    for item in repairs.items:
        key = tuple(sorted(item.items()))
        counts[key] = counts.get(key, 0) + 1
    record["repairs"] = [{**dict(k), "count": n} for k, n in counts.items()]
    return record


def is_page_number(line: PLine) -> bool:
    return line.plain.isdigit() and line.top > line.page_height * 0.88


# ---- the four documents ----------------------------------------------------------------


def page_items(page, page_no: int, repairs: Repairs, tables: bool) -> list[tuple[str, object]]:
    """Lines and tables of a page in reading order. Lines inside a table are not repeated."""
    items: list[tuple[float, str, object]] = []
    boxes = []
    if tables:
        for t in page.find_tables():
            rows = trim_empty_edges(t.extract())
            if rows:
                boxes.append(t.bbox)
                items.append((t.bbox[1], "table", table_markdown(rows)))
    chars = [c for c in page.chars if not any(in_box(c, b) for b in boxes)]
    page_lines = lines_from_chars(chars, page_no, float(page.height), repairs)
    body_size = max(
        {ln.size for ln in page_lines},
        key=lambda z: sum(ln.size == z for ln in page_lines),
        default=0,
    )
    margin = max((ln.x1 for ln in page_lines if ln.size == body_size), default=0.0)
    for ln in page_lines:
        ln.margin = margin
        items.append((ln.top, "line", ln))
    return [(k, v) for _, k, v in sorted(items, key=lambda t: t[0])]


def parse_flow_pdf(path: Path, meta: dict, config: FlowConfig, tables: bool) -> dict:
    repairs = Repairs()
    with pdfplumber.open(path) as pdf:
        record = base_record(path, pdf, meta)
        items: list[tuple[str, object]] = []
        for page_no, page in enumerate(pdf.pages, 1):
            items += page_items(page, page_no, repairs, tables)
    blocks, excluded = flow_blocks(items, config, repairs)
    for ex in excluded:
        raw, iso = printed_update(ex["text"])
        if iso:
            record["pdf_last_updated_raw"], record["pdf_last_updated"] = raw, iso
    return finish(record, blocks, excluded, repairs)


def refund_calendar_exclude(line: PLine) -> str | None:
    if is_page_number(line):
        return "page number"
    if line.size <= 8.5 and line.top > line.page_height * 0.6:
        return "document footer (printed update date and document name)"
    return None


def parse_refund_calendar(path: Path) -> dict:
    meta = {
        "source_file": f"data/pdfs/{path.name}",
        "doc_type": "aid",
        "scope": "city_tech",
        "aid_year": "2026-2027",
    }
    return parse_flow_pdf(path, meta, FlowConfig(exclude=refund_calendar_exclude), tables=True)


def parse_dropping_withdrawing(path: Path) -> dict:
    meta = {
        "source_file": f"data/pdfs/{path.name}",
        "doc_type": "policy",
        "scope": "city_tech",
        "term": "Fall 2026",
    }
    cfg = FlowConfig(exclude=lambda ln: "page number" if is_page_number(ln) else None)
    return parse_flow_pdf(path, meta, cfg, tables=False)


# -- CUNYfirst guide: written steps only --


SCREENSHOT_LABEL = "Screenshot notes"


def cunyfirst_exclude(line: PLine) -> str | None:
    if line.size <= 8.0:
        return "screenshot annotation (7 pt callout text laid over a screenshot)"
    return None


def with_screenshot_notes(body: list[Block], notes: list[dict]) -> list[Block]:
    """Put each callout line, in page order, in a "Screenshot notes" list at the end of the section
    (the heading it sat under). One list item per printed line: wrapped callouts are not joined."""
    by_heading: dict[str | None, list[str]] = {}
    for n in notes:
        by_heading.setdefault(n["heading"], []).append(n["text"])
    out: list[Block] = []
    current: str | None = None

    def close() -> None:
        texts = by_heading.pop(current, [])
        if texts:
            out.append(("p", 0, f"**{SCREENSHOT_LABEL}**"))
            out.append(("list", 0, "\n".join(f"- {t}" for t in texts)))

    for b in body:
        if b[0] == "h":
            close()
            current = b[2]
        out.append(b)
    close()
    if by_heading:
        raise ValueError(f"screenshot notes under unknown headings: {sorted(map(str, by_heading))}")
    return out


def parse_cunyfirst(path: Path) -> dict:
    note = (
        "A CUNY-wide guide, not City Tech. Per the owner, its examples show Hunter and LaGuardia "
        "and the 2022-23 aid year; that is inside the screenshots (images), which this record "
        "does not contain. The 7 pt callout text that is laid over the screenshots is kept: it "
        "is in each section under 'Screenshot notes', in page order, one item per printed line. "
        "It is text laid over screenshots, not part of the written steps."
    )
    meta = {
        "source_file": f"data/pdfs/{path.name}",
        "doc_type": "howto",
        "scope": "cuny",
        "note": note,
    }
    repairs = Repairs()
    with pdfplumber.open(path) as pdf:
        record = base_record(path, pdf, meta)
        items: list[tuple[str, object]] = []
        for page_no, page in enumerate(pdf.pages, 1):
            items += page_items(page, page_no, repairs, tables=False)
    cover = [v for k, v in items if k == "line" and v.page == 1]
    rest = [(k, v) for k, v in items if not (k == "line" and v.page == 1)]
    blocks: list[Block] = []
    title_lines = [ln for ln in cover if ln.size >= 18]
    subtitle = [ln for ln in cover if 10.5 <= ln.size < 12]
    topics: list[list[PLine]] = []
    for ln in (x for x in cover if x.size == 12.0):  # the contents list: wrapped lines are one item
        if topics and ln.top - topics[-1][-1].top <= 1.3 * ln.size:
            topics[-1].append(ln)
        else:
            topics.append([ln])
    blocks.append(("h", 1, " ".join(ln.plain for ln in title_lines)))
    blocks.append(("p", 0, " ".join(ln.plain for ln in subtitle)))
    blocks.append(("list", 0, "\n".join("- " + " ".join(ln.plain for ln in t) for t in topics)))
    cfg = FlowConfig(exclude=cunyfirst_exclude, heading_min_size=15.0, notes=True)
    body, notes = flow_blocks(rest, cfg, repairs)
    body = with_screenshot_notes(body, notes)
    # flow_blocks makes the first heading level 1; here the title is already level 1
    fixed = [("h", 2, b[2]) if b[0] == "h" else b for b in body]
    record["title"] = blocks[0][2]
    return finish(record, blocks + fixed, [], repairs)


# -- the flyer: an infographic read panel by panel from its text layer --

FLYER_PANELS = [
    # name, (x0, top, x1, bottom), number of heading lines at the top of the panel. The order is the
    # reading order of the infographic: intro, the three steps, then the contact box (top right).
    ("title", (0, 60, 560, 135), 2),
    ("intro", (100, 185, 560, 410), 0),
    ("step1", (590, 185, 880, 415), 2),
    ("step2", (320, 435, 760, 690), 2),
    ("step3", (30, 435, 320, 690), 3),
    ("contact", (600, 20, 900, 135), 1),
]


def flyer_panel_lines(page, box, repairs: Repairs) -> list[PLine]:
    chars = [c for c in page.chars if box[0] <= (c["x0"] + c["x1"]) / 2 < box[2]
             and box[1] <= (c["top"] + c["bottom"]) / 2 < box[3]]  # fmt: skip
    return lines_from_chars(chars, 1, float(page.height), repairs)


def parse_flyer(path: Path) -> dict:
    note = (
        "Infographic: the text is read from the PDF text layer panel by panel (the reading order "
        "of the stream is not the visual order). It was not transcribed from an image; the "
        "rendered page was compared with it by eye. Fonts are all bold-weight Montserrat, so "
        "bold is not kept."
    )
    meta = {"source_file": f"data/pdfs/{path.name}", "doc_type": "aid", "scope": "city_tech",
            "aid_year": "2025-2026 & 2026-2027", "note": note}  # fmt: skip
    repairs = Repairs()
    blocks: list[Block] = []
    with pdfplumber.open(path) as pdf:
        record = base_record(path, pdf, meta)
        page = pdf.pages[0]
        for name, box, n_heading in FLYER_PANELS:
            lines = flyer_panel_lines(page, box, repairs)
            head, body = lines[:n_heading], lines[n_heading:]
            if name == "title":
                record["title"] = " ".join(ln.plain for ln in head)
                continue
            if head:
                blocks.append(("h", 2, " ".join(ln.plain for ln in head)))
            if name == "contact":  # one printed line each: role, name, phone, email
                blocks.append(("p", 0, "\n".join(ln.plain for ln in body)))
            else:
                blocks += flyer_body(body, repairs)
    return finish(record, blocks, [], repairs)


def flyer_body(lines: list[PLine], repairs: Repairs) -> list[Block]:
    """Paragraphs and bullet items of one panel (every line is part of the flow: no gaps)."""
    blocks: list[Block] = []
    para: list[PLine] = []
    items: list[list[PLine]] = []

    def flush() -> None:
        nonlocal para, items
        if para:
            blocks.append(
                ("p", 0, join_lines([p.plain for p in para], [p.plain for p in para], repairs))
            )
            para = []
        if items:
            texts = [
                join_lines([p.plain for p in it], [p.plain for p in it], repairs) for it in items
            ]
            blocks.append(("list", 0, "\n".join("- " + t for t in texts)))
            items = []

    for ln in lines:
        if ln.plain.startswith(BULLETS):
            if para:
                flush()
            items.append([replace(ln, text=strip_bullet(ln.plain), plain=strip_bullet(ln.plain))])
        elif items:
            items[-1].append(ln)
        else:
            para.append(ln)
    flush()
    return blocks


# ---- build ---------------------------------------------------------------------------------

REFUND_PDF = "Award_Year_2026_2027_Financial_Aid_Payment_Refund _Calendar.pdf"
DOCUMENTS = [
    ("financial-aid-refund-calendar-2026-2027", REFUND_PDF, parse_refund_calendar),
    ("dropping-withdrawing-fall-2026", "Fall_2026_Dropping_and_Withdrawing_from_Classes.pdf",
     parse_dropping_withdrawing),
    ("special-circumstances-flyer", "Special_Circumstances_Flyer_2025_2026_2026_2027.pdf",
     parse_flyer),
    ("cunyfirst-student-reference", "cunyfirst_student_reference.pdf", parse_cunyfirst),
]  # fmt: skip


def build_all(pdf_dir: Path) -> dict[str, dict]:
    return {slug: parse(pdf_dir / name) for slug, name, parse in DOCUMENTS}


def render_markdown(record: dict) -> str:
    lines = [f"<!-- {record['source_file']} | {record['doc_type']} | scope: {record['scope']} -->"]
    shown: list[str] = []
    for s in record["sections"]:
        for h in [*s["parents"], {"level": s["level"], "heading": s["heading"]}]:
            if h["heading"] and h["heading"] not in shown:
                lines.append(f"{'#' * max(h['level'], 1)} {h['heading']}")
                shown.append(h["heading"])
        lines.append(s["markdown"])
    return "\n\n".join(lines) + "\n"


def main() -> int:
    from cta.validate.pdfs import run_pdf_checks

    out = ROOT / "data" / "processed" / "pdfs"
    out.mkdir(parents=True, exist_ok=True)
    failures = 0
    for slug, name, parse in DOCUMENTS:
        path = ROOT / "data" / "pdfs" / name
        record = parse(path)
        (out / f"{slug}.json").write_text(
            json.dumps(record, indent=1, ensure_ascii=False) + "\n", "utf-8"
        )
        findings = run_pdf_checks(record, path)
        failures += sum(f.severity == "fail" for f in findings)
        counts = f"{len(record['sections'])} sections, {len(record['excluded'])} excluded lines"
        print(f"{slug}: {counts}, {len(findings)} findings")
        for f in findings:
            print(f"   [{f.severity.upper()}] {f.check}: {f.message}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
