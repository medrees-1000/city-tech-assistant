"""One city tech HTML page -> clean record.

Only two regions of a page are read: the main content (`div.c-layout-sidebar-content`) and the
contact panels in the sidebar. The header (mega-menu, alert banner), breadcrumbs, sidebar link
list and footer are never visited, so nothing has to be "stripped" from them.
"""

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup, NavigableString, Tag
from bs4.element import PreformattedString

MAIN = "div.c-layout-sidebar-content"
PANELS = "div.c-layout-sidebar-menu div.panel"

PLACEHOLDER = re.compile(r"\{\{.*?\}\}")
SPACED_EMAIL = re.compile(r"([\w.+-]+)\s+(@[\w-]+(?:\.[\w-]+)*\.(?:edu|org|com|gov))", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"\b\d{3}[-.]\d{3}[-.]\d{4}\b")
ROOM = re.compile(r"\([A-Z]{1,3}-\d+\)")  # e.g. Namm Hall 1000 (N-1000)

BREAK = "\x00"  # stands for <br> until whitespace is collapsed
HEADINGS = ["h1", "h2", "h3", "h4", "h5", "h6"]
SKIP = {"script", "style", "noscript", "iframe", "form", "svg", "img", "input", "select"}
INLINE = {"a", "span", "strong", "b", "em", "i", "u", "font", "small", "big", "sup", "sub", "abbr",
          "label", "mark", "cite", "code", "time"}  # fmt: skip
LINE_BREAKERS = {"p", "div", "li", "ul", "ol", "tr", "td", "th", "table", "section"}


@dataclass
class Ctx:
    """Per-page state shared while walking the tree."""

    base_url: str
    email_repairs: list[dict] = field(default_factory=list)
    placeholders_removed: int = 0


def absolute(href: str, base: str) -> str:
    url = urljoin(base, href.strip())
    parts = urlsplit(url)
    if parts.scheme == "http" and (parts.hostname or "").endswith("citytech.cuny.edu"):
        url = url.replace("http://", "https://", 1)
    return url


def repair_email(raw: str, ctx: Ctx) -> str:
    fixed = re.sub(r"\s+", "", raw)
    if fixed != raw.strip():
        ctx.email_repairs.append({"raw": raw.strip(), "fixed": fixed})
    return fixed


def clean(text: str, ctx: Ctx, breaks: str = " ") -> str:
    """Collapse whitespace, drop {{...}} placeholders, repair spaced emails."""
    ctx.placeholders_removed += len(PLACEHOLDER.findall(text))
    text = PLACEHOLDER.sub(" ", text)
    text = re.sub(r"[ \t\r\n\xa0]+", " ", text)

    def fix(m: re.Match) -> str:
        return repair_email(m.group(0), ctx)

    text = SPACED_EMAIL.sub(fix, text)
    text = text.strip(BREAK + " ")
    text = re.sub(r"(?: ?\x00 ?)+", breaks, text)
    return re.sub(r" {2,}", " ", text).strip(" \n")


def inline(node: Tag, ctx: Ctx) -> str:
    return "".join(inline_node(ch, ctx) for ch in node.children)


def inline_node(n, ctx: Ctx) -> str:
    if isinstance(n, PreformattedString):  # comments, doctype, CDATA
        return ""
    if isinstance(n, NavigableString):
        return str(n)
    if n.name in SKIP:
        return ""
    if n.name == "br":
        return BREAK
    if n.name == "a":
        return link_markdown(n, ctx)
    text = inline(n, ctx)
    if n.name == "sup":  # footnote markers must not glue onto the word: "Psychology^1"
        text = text.strip()
        return f"^{text}" if len(text) <= 1 else f"^({text})" if text else ""
    return f"{BREAK}{text}{BREAK}" if n.name in LINE_BREAKERS else text


def link_markdown(a: Tag, ctx: Ctx) -> str:
    href = (a.get("href") or "").strip()
    if href.lower().startswith("mailto:"):
        return repair_email(unquote(href[7:]).split("?")[0], ctx)
    text = clean(inline(a, ctx), ctx)
    if not href or href.startswith("#") or href.lower().startswith(("javascript:", "tel:")):
        return text
    return f"[{text}]({absolute(href, ctx.base_url)})" if text else ""


Block = tuple[str, int, str]  # (kind, heading level, text)


def blocks(nodes: Iterable, ctx: Ctx) -> list[Block]:
    out: list[Block] = []
    pending: list[str] = []

    def flush() -> None:
        text = clean("".join(pending), ctx, breaks="\n")
        pending.clear()
        if text:
            out.append(("p", 0, text))

    for ch in nodes:
        if isinstance(ch, PreformattedString):
            continue
        if isinstance(ch, NavigableString):
            pending.append(str(ch))
            continue
        if ch.name in SKIP:
            continue
        if ch.name in INLINE or ch.name == "br":
            pending.append(inline_node(ch, ctx))
            continue
        flush()
        if ch.name in HEADINGS or (ch.name == "p" and "barTitle" in (ch.get("class") or [])):
            # <p class="barTitle"> is a styled section label (52 on the real pages): level 2
            text = clean(inline(ch, ctx), ctx)
            if text:
                out.append(("h", int(ch.name[1]) if ch.name in HEADINGS else 2, text))
        elif ch.name in ("ul", "ol"):
            out.extend(list_blocks(ch, ctx))
        elif ch.name == "table":
            if ch.find(HEADINGS):  # a table used for layout (e.g. FAQ accordions): keep its content
                out.extend(blocks(ch.children, ctx))
            else:
                md = table_markdown(ch, ctx)
                if md:
                    out.append(("table", 0, md))
        else:  # p, div, section, td, ...
            out.extend(blocks(ch.children, ctx))
    flush()
    return out


def list_blocks(lst: Tag, ctx: Ctx) -> list[Block]:
    """A list as markdown. Elements that sit directly inside the <ul>/<ol> but are not <li>
    (a <p> or a <table>, which real pages do) are kept as ordinary blocks, in order."""
    out: list[Block] = []
    run: list[Tag] = []

    def flush_run() -> None:
        lines = list_lines(lst, ctx, items=run)
        if lines:
            out.append(("list", 0, "\n".join(lines)))
        run.clear()

    for ch in lst.children:
        if isinstance(ch, Tag) and ch.name == "li":
            run.append(ch)
        elif isinstance(ch, NavigableString) and not ch.strip():
            continue  # whitespace between <li> tags must not split the list
        else:
            flush_run()
            out.extend(blocks([ch], ctx))
    flush_run()
    return out


def list_lines(lst: Tag, ctx: Ctx, depth: int = 0, items: list[Tag] | None = None) -> list[str]:
    lines = []
    for i, li in enumerate(lst.find_all("li", recursive=False) if items is None else items, 1):
        nested = [c for c in li.children if isinstance(c, Tag) and c.name in ("ul", "ol")]
        parts = [inline_node(c, ctx) for c in li.children if c not in nested]
        text = clean("".join(parts), ctx)
        if text:
            marker = f"{i}." if lst.name == "ol" else "-"
            lines.append(f"{'  ' * depth}{marker} {text}")
        for n in nested:
            lines.extend(list_lines(n, ctx, depth + 1))
    return lines


def table_rows(node: Tag) -> Iterator[list[Tag]]:
    """Cells of each row, in order. Cells that sit outside a <tr> (broken markup on the real
    pages) are grouped into a row of their own instead of being dropped."""
    orphans: list[Tag] = []
    for ch in node.children:
        if not isinstance(ch, Tag):
            continue
        if ch.name in ("th", "td"):
            orphans.append(ch)
            continue
        if orphans:
            yield orphans
            orphans = []
        if ch.name in ("tr", "thead", "tbody", "tfoot"):  # a <tr> may even contain another <tr>
            yield from table_rows(ch)
    if orphans:
        yield orphans


def table_markdown(table: Tag, ctx: Ctx) -> str:
    """GFM table. A first row of only <th> is the header. Other <th> cells are row labels (bold)."""
    rows: list[list[tuple[str, str]]] = []
    for cells in table_rows(table):
        row: list[tuple[str, str]] = []
        for c in cells:
            text = clean(inline(c, ctx), ctx, breaks="<br>").replace("|", "\\|")
            span = int(c.get("colspan", 1)) if str(c.get("colspan", 1)).isdigit() else 1
            row.append((c.name, text))
            row.extend([(c.name, "")] * (span - 1))
        if row:
            rows.append(row)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    header_row = rows[0] if all(kind == "th" for kind, _ in rows[0]) else None
    body = rows[1:] if header_row else rows
    header = [t for _, t in header_row] if header_row else [""] * width

    def fmt(cells: list[str]) -> str:
        return "| " + " | ".join(cells + [""] * (width - len(cells))) + " |"

    lines = [fmt(header), fmt(["---"] * width)]
    for r in body:
        lines.append(fmt([f"**{t}**" if k == "th" and t else t for k, t in r]))
    return "\n".join(lines)


def to_sections(found: list[Block]) -> list[dict]:
    sections: list[dict] = []
    cur: dict = {"heading": None, "level": 0, "parts": []}

    def push() -> None:
        if cur["heading"] is not None or cur["parts"]:
            sections.append({"heading": cur["heading"], "level": cur["level"],
                             "markdown": "\n\n".join(cur["parts"])})  # fmt: skip

    for kind, level, text in found:
        if kind == "h":
            push()
            cur = {"heading": text, "level": level, "parts": []}
        else:
            cur["parts"].append(text)
    push()
    return sections


def contact_block(soup: BeautifulSoup, ctx: Ctx) -> dict:
    """Keep the "CONTACT US" panel and any panel with HOURS in its heading; drop promo panels."""
    panels = []
    for panel in soup.select(PANELS):
        head = panel.select_one(".panel-heading")
        heading = clean(head.get_text(" "), ctx) if head else ""
        if heading.lower() != "contact us" and "hours" not in heading.lower():
            continue
        body = panel.select_one(".panel-body") or panel
        md = "\n\n".join(text for _, _, text in blocks(body.children, ctx))
        panels.append({"heading": heading, "markdown": md})
    text = "\n".join(p["markdown"] for p in panels)
    return {
        "panels": panels,
        "emails": sorted(set(EMAIL.findall(text))),
        "phones": sorted(set(PHONE.findall(text))),
    }


def chair_block(main: Tag, ctx: Ctx) -> dict | None:
    """Name, role, room, phone and email of the chair on a chairperson.aspx page."""
    link = main.select_one("a[href^='mailto:']")
    box = link.find_parent("div").parent if link and link.find_parent("div") else None
    if box is None:
        return None
    strong, em = box.find("strong"), box.find("em")
    text = clean(inline(box, ctx), ctx)
    room = next(
        (clean(d.get_text(" "), ctx) for d in box.find_all("div") if ROOM.search(d.get_text())),
        None,
    )
    phone = PHONE.search(text)
    faculty = box.select_one("a[href*='/faculty/']")
    return {
        "name": clean(strong.get_text(" "), ctx) if strong else None,
        "role": clean(em.get_text(" "), ctx) if em else None,
        "room": room,
        "phone": phone.group(0) if phone else None,
        "email": repair_email(unquote(link["href"][7:]).split("?")[0], Ctx(ctx.base_url)),
        "faculty_page": absolute(faculty["href"], ctx.base_url) if faculty else None,
    }  # fmt: skip


def pdf_links(main: Tag, base: str) -> list[dict]:
    seen, found = set(), []
    for a in main.find_all("a", href=True):
        href = a["href"].strip()
        if urlsplit(href).path.lower().endswith(".pdf"):
            url = absolute(href, base)
            if url not in seen:
                seen.add(url)
                found.append({"url": url, "text": " ".join(a.get_text(" ").split())})
    return found


def not_collected(meta: dict, reason: str, title: str | None = None) -> dict:
    return {**meta, "title": title, "status": "not_collected", "reason": reason, "sections": [],
            "contact": {"panels": [], "emails": [], "phones": []}, "chair": None,
            "pdf_links": [], "email_repairs": []}  # fmt: skip


def parse_page(html: bytes, meta: dict) -> dict:
    """meta: source_url, final_url, fetched_at, content_hash, http_status, kind, owner."""
    soup = BeautifulSoup(html, "html.parser")  # decoding happens here, in memory only
    ctx = Ctx(base_url=meta["final_url"] or meta["source_url"])
    title = clean(soup.title.get_text(" "), ctx) if soup.title else None
    main = soup.select_one(MAIN)
    if main is None:
        return not_collected(meta, "main content selector not found", title)
    raw_text = main.get_text(" ", strip=True)
    if not raw_text:
        return not_collected(meta, "main content empty in raw HTML", title)
    found = blocks(main.children, ctx)
    sections = to_sections(found)
    if not sections:
        reason = "only template placeholders" if ctx.placeholders_removed else "main content empty"
        return not_collected(meta, reason, title)
    if urlsplit(meta["source_url"]).path.endswith("chairperson.aspx"):
        chair = chair_block(main, ctx)
    else:
        chair = None
    return {
        **meta,
        "title": title,
        "status": "collected",
        "reason": "",
        "sections": sections,
        "contact": contact_block(soup, ctx),
        "chair": chair,
        "pdf_links": pdf_links(main, ctx.base_url),
        "email_repairs": [
            dict(t) for t in dict.fromkeys(tuple(r.items()) for r in ctx.email_repairs)
        ],
    }


def render_markdown(record: dict) -> str:
    """The cleaned page as one markdown document (for reading and review)."""
    lines = [f"<!-- {record['source_url']} | status: {record['status']} -->"]
    for s in record["sections"]:
        if s["heading"]:
            lines.append(f"{'#' * max(s['level'], 1)} {s['heading']}")
        if s["markdown"]:
            lines.append(s["markdown"])
    for p in record["contact"]["panels"]:
        lines += [f"**{p['heading']}**", p["markdown"]]
    return "\n\n".join(lines) + "\n"
