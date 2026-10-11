"""Calendar PDFs -> event rows.

The PDFs are Excel exports: one bordered table with the columns DATES, DAYS and EVENT. The text
stream is not in reading order, so everything here works from character positions: the thin
rectangles are the cell borders, and each character belongs to the cell that holds its center.

Nothing is guessed: a line that cannot be parsed is returned in `unparsed`, a date is never
changed to make a weekday match, and bold is read from the font name (null when a line mixes
bold and regular text).
"""

import calendar
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pdfplumber

MONTHS = {name: i for i, name in enumerate(calendar.month_name) if name}
WEEKDAYS = {name: i for i, name in enumerate(calendar.day_name)}  # Monday = 0
MONTH = "|".join(MONTHS)
DAY = "|".join(WEEKDAYS)

DATE_ONE = re.compile(rf"^({MONTH}) (\d{{1,2}})(?:\s*-\s*(\d{{1,2}}))?(?:,\s*(\d{{4}}))?$")
DATE_CROSS = re.compile(rf"^({MONTH}) (\d{{1,2}})\s*-\s*({MONTH}) (\d{{1,2}})(?:,\s*(\d{{4}}))?$")
DAY_ONE = re.compile(rf"^({DAY})(?:\s*-\s*({DAY}))?$")
LAST_UPDATED = re.compile(r"Last updated:\s*(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{2,4})")
TITLE = re.compile(r"^(FALL|WINTER|SPRING|SUMMER) (\d{4}) ACADEMIC CALENDAR", re.I)

# "applies_to" is filled only when the text names who the event is for, in one of these forms.
APPLIES_TO = [
    re.compile(
        r"\bregistration\b.*?\bbegins for (.+?)\.(?: Registration by appointment only\.)?$", re.I
    ),
    re.compile(r"\((students [^)]*)\)"),
]


@dataclass
class Line:
    text: str
    page: int
    top: float
    x1: float
    first_word_width: float
    bold: list[bool]  # one flag per non-space character


@dataclass
class Row:
    page: int
    y0: float
    y1: float
    dates: list[Line] = field(default_factory=list)
    days: list[Line] = field(default_factory=list)
    events: list[Line] = field(default_factory=list)


@dataclass
class Extraction:
    pdf: str
    title: str | None
    term: str | None
    last_updated_raw: str | None
    rows: list[Row]
    excluded: list[str]  # text outside the table body (title, header, footnotes)
    body_chars: list[str]  # every character inside the table outline (completeness check)
    header_chars: list[str]  # the part of those that is the header row (DATES, DAYS, Last updated)
    edge: float  # right edge of the event column


def is_bold(fontname: str) -> bool:
    return "bold" in fontname.lower()


def geometry(page) -> tuple[list[float], list[float]]:
    """(column x positions, row border y positions) from the thin rectangles."""
    xs = sorted(
        {
            round(r["x0"])
            for r in page.rects
            if r["x1"] - r["x0"] <= 2 and r["bottom"] - r["top"] > 100
        }
    )
    ys = sorted(
        {
            round(r["top"])
            for r in page.rects
            if r["bottom"] - r["top"] <= 2 and r["x1"] - r["x0"] > 300
        }
    )
    return xs, ys


def in_box(c: dict, box: tuple[float, float, float, float]) -> bool:
    """True if the center of the character is inside the box (x0, top, x1, bottom)."""
    return (
        box[0] <= (c["x0"] + c["x1"]) / 2 < box[2]
        and box[1] <= (c["top"] + c["bottom"]) / 2 < box[3]
    )


def lines_of(chars: list[dict], page_no: int) -> list[Line]:
    """Group characters into printed lines (same baseline), left to right."""
    groups: list[list[dict]] = []
    for c in sorted(chars, key=lambda c: (c["top"], c["x0"])):
        if groups and abs(groups[-1][0]["top"] - c["top"]) <= 2:
            groups[-1].append(c)
        else:
            groups.append([c])
    out = []
    for g in groups:
        g.sort(key=lambda c: c["x0"])
        text, prev, first_word_end = "", None, None
        for c in g:
            if c["text"].isspace():
                continue
            if prev is not None and c["x0"] - prev["x1"] > 1.0:
                text += " "
                first_word_end = first_word_end or prev["x1"]
            text += c["text"]
            prev = c
        first_word_end = first_word_end or g[-1]["x1"]
        out.append(Line(
            text=text, page=page_no, top=g[0]["top"], x1=max(c["x1"] for c in g),
            first_word_width=first_word_end - g[0]["x0"],
            bold=[is_bold(c["fontname"]) for c in g if not c["text"].isspace()],
        ))  # fmt: skip
    return out


def extract_pdf(path: Path) -> Extraction:
    rows: list[Row] = []
    excluded: list[str] = []
    body_chars: list[str] = []
    header_chars: list[str] = []
    title = last_updated = None
    edge = 0.0
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            xs, ys = geometry(page)
            edge = xs[-1]
            body = (xs[0], ys[0], xs[-1], ys[-1])
            # Everything inside the table's outline, found without using the rows or cells:
            body_chars += [
                c["text"] for c in page.chars if in_box(c, body) and not c["text"].isspace()
            ]
            outside = [c for c in page.chars if not in_box(c, body)]
            for line in lines_of(outside, page_no):
                excluded.append(line.text)
                if title is None and TITLE.match(line.text):
                    title = line.text
            cols = list(zip(xs[:-1], xs[1:], strict=True))
            for r0, r1 in zip(ys[:-1], ys[1:], strict=True):
                cells = []
                for x0, x1 in cols:
                    cs = [c for c in page.chars if in_box(c, (x0, r0, x1, r1))]
                    cells.append(lines_of(cs, page_no))
                header = " ".join(ln.text for c in cells[:2] for ln in c)
                if header.strip() == "DATES DAYS":  # the header row also holds "Last updated"
                    header_chars += [ch for c in cells for ln in c for ch in ln.text if ch != " "]
                    for ln in cells[2]:
                        if m := LAST_UPDATED.search(ln.text):
                            last_updated = m.group(0)
                    continue
                rows.append(Row(page_no, r0, r1, cells[0], cells[1], cells[2]))
    term = None
    if title and (m := TITLE.match(title)):
        term = f"{m.group(1).title()} {m.group(2)}"
    return Extraction(
        str(path), title, term, last_updated, rows, excluded, body_chars, header_chars, edge
    )


def joined_lines(lines: list[Line], edge: float) -> list[list[Line]]:
    """Group a cell's printed lines into events.

    A line continues the one above it when it starts with a lowercase letter or digit, or when its
    first word would not have fitted on the line above. Every such join is noted on the event."""
    groups: list[list[Line]] = []
    for line in lines:
        if groups:
            prev = groups[-1][-1]
            fits = prev.x1 + 2.5 + line.first_word_width <= edge - 1
            if line.text[:1].islower() or line.text[:1].isdigit() or not fits:
                groups[-1].append(line)
                continue
        groups.append([line])
    return groups


def parse_last_updated(raw: str | None) -> str | None:
    m = LAST_UPDATED.search(raw or "")
    if not m:
        return None
    month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return date(year + 2000 if year < 100 else year, month, day).isoformat()


def parse_date_text(text: str) -> dict | None:
    """Printed date -> parts, or None if it cannot be parsed. "TBA" is kept as a TBA marker."""
    if text.strip().upper() == "TBA":
        return {"tba": True}
    if m := DATE_CROSS.match(text):
        m1, d1, m2, d2, y = m.groups()
        return {
            "m1": MONTHS[m1],
            "d1": int(d1),
            "m2": MONTHS[m2],
            "d2": int(d2),
            "year": y and int(y),
        }
    if m := DATE_ONE.match(text):
        mo, d1, d2, y = m.groups()
        return {"m1": MONTHS[mo], "d1": int(d1), "m2": MONTHS[mo], "d2": int(d2) if d2 else None,
                "year": y and int(y)}  # fmt: skip
    return None


def start_year(term: str, first_month: int) -> int:
    """Calendar year of a term's first row. Winter 2027 starts in December 2026, so a Winter table
    whose first row is in November or December begins in the year before the term year."""
    name, year = term.split()
    return int(year) - 1 if name == "Winter" and first_month >= 11 else int(year)


def resolve_dates(parts: dict, term_year: int) -> tuple[date, date | None]:
    """(start, end) for parsed parts in a given calendar year. end is None for a single day."""
    start = date(term_year, parts["m1"], parts["d1"])
    if parts["d2"] is None:
        return start, None
    end_year = term_year + (1 if parts["m2"] < parts["m1"] else 0)
    return start, date(end_year, parts["m2"], parts["d2"])


def weekday_check(date_start: str | None, date_end: str | None, weekday_raw: str) -> str:
    """ "ok", "n/a" (TBA) or "MISMATCH ...": the printed day(s) against the resolved date(s)."""
    if date_start is None:
        return "n/a"
    m = DAY_ONE.match(weekday_raw)
    if not m:
        return f"MISMATCH: unreadable day {weekday_raw!r}"
    printed = [m.group(1)] + ([m.group(2)] if m.group(2) else [])
    actual = [calendar.day_name[date.fromisoformat(date_start).weekday()]]
    if date_end:
        actual.append(calendar.day_name[date.fromisoformat(date_end).weekday()])
    if len(printed) != len(actual):
        return f"MISMATCH: printed {weekday_raw!r}, dates are {'-'.join(actual)}"
    if printed != actual:
        return f"MISMATCH: printed {'-'.join(printed)}, date is {'-'.join(actual)}"
    return "ok"


def applies_to(text: str) -> str | None:
    for pattern in APPLIES_TO:
        if m := pattern.search(text):
            return m.group(1).strip()
    return None


def bold_of(lines: list[Line]) -> bool | None:
    flags = {b for ln in lines for b in ln.bold}
    return flags.pop() if len(flags) == 1 else None


def build_events(ex: Extraction, source_pdf: str) -> tuple[list[dict], list[dict]]:
    """(events, unparsed). `unparsed` lists every row that could not be turned into events."""
    term = ex.term
    events: list[dict] = []
    unparsed: list[dict] = []
    year = None
    prev_month = None
    slug = term.lower().replace(" ", "-")
    updated = parse_last_updated(ex.last_updated_raw)
    for row in ex.rows:
        where = f"page {row.page}, y {row.y0:.0f}-{row.y1:.0f}"
        if not (row.dates or row.days or row.events):
            continue
        if len(row.dates) != 1 or len(row.days) != 1 or not row.events:
            counts = f"{len(row.dates)} date, {len(row.days)} day, {len(row.events)} event lines"
            texts = [ln.text for ln in row.dates + row.days + row.events]
            unparsed.append({"where": where, "why": counts, "text": texts})
            continue
        date_raw, weekday_raw = row.dates[0].text, row.days[0].text
        parts = parse_date_text(date_raw)
        if parts is None:
            unparsed.append({"where": where, "why": "date could not be parsed", "text": [date_raw]})
            continue
        date_start = date_end = None
        notes_date: list[str] = []
        if not parts.get("tba"):
            if year is None:
                year = start_year(term, parts["m1"])
            elif parts["m1"] < prev_month:
                year += 1  # the table is in date order: December is followed by January
            prev_month = parts["m1"]
            if parts["year"] is not None and parts["year"] != year:
                notes_date.append(f"PDF prints year {parts['year']}, table position gives {year}")
            start, end = resolve_dates(parts, parts["year"] or year)
            date_start, date_end = start.isoformat(), end.isoformat() if end else None
        for group in joined_lines(row.events, ex.edge):
            text = " ".join(ln.text for ln in group)
            notes = list(notes_date)
            if len(group) > 1:
                notes.append(f"printed on {len(group)} lines; joined as wrapped text")
            bold = bold_of(group)
            if bold is None:
                notes.append("line mixes bold and regular text")
            events.append({
                "id": f"{slug}-{len(events) + 1:03d}",
                "term": term,
                "event": text,
                "date_start": date_start,
                "date_end": date_end,
                "date_raw": date_raw,
                "weekday_raw": weekday_raw,
                "applies_to": applies_to(text),
                "bold": bold,
                "source_pdf": source_pdf,
                "source_page": group[0].page,
                "pdf_last_updated": updated,
                "verified": False,
                "notes": "; ".join(notes) or None,
            })  # fmt: skip
    return events, unparsed
