"""One city tech HTML page -> clean record.

Only two regions of a page are read: the main content (`div.c-layout-sidebar-content`) and the
contact panels in the sidebar. The header (mega-menu, alert banner), breadcrumbs, sidebar link
list and footer are never visited, so nothing has to be "stripped" from them."""

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, NavigableString, Tag
from bs4.element import PreformattedString

# ---- heading cleanup: no markdown link markup in headings or heading paths (was headings.py) ----
#
# A heading that was a link, "[Data Science/BS](https://.../programs/DSCI-BS)", becomes the visible
# text "Data Science/BS"; the URL is kept in the section's `heading_url`.

LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]*)\)")


def clean_heading(text: str | None) -> tuple[str | None, str | None]:
    """(heading without link markup, the URL of its first link or None)."""
    if text is None:
        return None, None
    found = LINK.search(text)
    return (LINK.sub(r"\1", text), found[2] if found else None)


MAIN = "div.c-layout-sidebar-content"
PANELS = "div.c-layout-sidebar-menu div.panel"

PLACEHOLDER = re.compile(r"\{\{.*?\}\}")
SPACED_EMAIL = re.compile(r"([\w.+-]+)\s+(@[\w-]+(?:\.[\w-]+)*\.(?:edu|org|com|gov))", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"\b\d{3}[-.]\d{3}[-.]\d{4}\b")
PHONE_LINE = re.compile(
    r"^\s*(?:Office\s+)?Phone:", re.IGNORECASE
)  # "Phone: ..." / "Office Phone: ..."
FAX_LINE = re.compile(r"^\s*Fax:", re.IGNORECASE)
AI_AGENT_LINE = re.compile(
    r"\bAI agent\b", re.IGNORECASE
)  # "Call or chat 24/7 with our AI agent: ..."
ROOM = re.compile(r"\([A-Z]{1,3}-\d+\)")  # e.g. Namm Hall 1000 (N-1000)

MAX_QUERY = 100  # a longer query string is dropped from a link (tracking or meeting parameters)
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
    stripped_urls: list[dict] = field(default_factory=list)  # links whose long query was dropped
    tab_labels: dict[str, str] = field(default_factory=dict)  # pane id -> tab title
    tab_level: int = 2  # heading level used for tab titles
    last_level: int = 1  # level of the most recent heading


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


def is_login_url(url: str) -> bool:
    """Single sign-on host, or "login" in the path or fragment: never keep these links."""
    parts = urlsplit(url)
    return (
        (parts.hostname or "").lower() == "ssologin.cuny.edu"
        or "login" in parts.path.lower()
        or "login" in parts.fragment.lower()
    )


def strip_long_query(url: str) -> tuple[str, int]:
    """(url without its query string if the query is over MAX_QUERY characters, query length)."""
    parts = urlsplit(url)
    if len(parts.query) > MAX_QUERY:
        return urlunsplit(parts._replace(query="")), len(parts.query)
    return url, len(parts.query)


def link_markdown(a: Tag, ctx: Ctx) -> str:
    href = (a.get("href") or "").strip()
    if href.lower().startswith("mailto:"):
        return repair_email(unquote(href[7:]).split("?")[0], ctx)
    text = clean(inline(a, ctx), ctx)
    if not href or href.startswith("#") or href.lower().startswith(("javascript:", "tel:")):
        return text
    url = absolute(href, ctx.base_url)
    if is_login_url(url):
        return text  # keep the link text, drop the login link
    url, query_length = strip_long_query(url)
    if query_length > MAX_QUERY:
        ctx.stripped_urls.append({"url": url, "query_length": query_length})
    return f"[{text}]({url})" if text else ""


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
        classes = ch.get("class") or []
        if ch.name == "ul" and "nav-tabs" in classes:
            # the tab titles become headings above their panes, so the list itself is dropped
            ctx.tab_level = ctx.last_level + 1
            for a in ch.find_all("a", href=True):
                if a["href"].startswith("#"):
                    ctx.tab_labels[a["href"][1:]] = clean(inline(a, ctx), ctx)
        elif "tab-pane" in classes and ctx.tab_labels.get(ch.get("id", "")):
            out.append(("h", ctx.tab_level, ctx.tab_labels[ch["id"]]))
            out.extend(blocks(ch.children, ctx))
        elif ch.name in HEADINGS or (ch.name == "p" and "barTitle" in classes):
            # <p class="barTitle"> is a styled section label (52 on the real pages): level 2.
            # On some pages it is never closed, so the paragraphs after it are nested inside it:
            # only its leading inline text is the heading, the rest is ordinary content.
            head, rest = split_heading(ch)
            text = clean("".join(inline_node(n, ctx) for n in head), ctx)
            if text:
                level = int(ch.name[1]) if ch.name in HEADINGS else 2
                ctx.last_level = level
                out.append(("h", level, text))
            out.extend(blocks(rest, ctx))
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


def split_heading(el: Tag) -> tuple[list, list]:
    """(leading inline nodes, everything from the first block-level child on)."""
    head: list = []
    children = list(el.children)
    for i, c in enumerate(children):
        inline_child = isinstance(c, NavigableString) or c.name in INLINE or c.name == "br"
        if not inline_child:
            return head, children[i:]
        head.append(c)
    return head, []


def list_blocks(lst: Tag, ctx: Ctx) -> list[Block]:
    """A list as markdown. Elements that sit directly inside the <ul>/<ol> but are not <li> or a
    nested list (a <p> or a <table>, which real pages do) are kept as ordinary blocks, in order."""
    out: list[Block] = []
    run: list[Tag] = []

    def flush_run() -> None:
        lines = list_lines(lst, ctx, children=run)
        if lines:
            out.append(("list", 0, "\n".join(lines)))
        run.clear()

    for ch in lst.children:
        if isinstance(ch, Tag) and ch.name in ("li", "ul", "ol"):
            run.append(ch)
        elif isinstance(ch, NavigableString) and not ch.strip():
            continue  # whitespace between <li> tags must not split the list
        else:
            flush_run()
            out.extend(blocks([ch], ctx))
    flush_run()
    return out


def list_lines(lst: Tag, ctx: Ctx, depth: int = 0, children: list[Tag] | None = None) -> list[str]:
    """Markdown lines of a list. A <ul> placed directly inside a <ul> (invalid HTML that real pages
    use) is treated as the children of the item before it, so its items stay indented."""
    lines = []
    count = 0
    for ch in lst.children if children is None else children:
        if not isinstance(ch, Tag):
            continue
        if ch.name in ("ul", "ol"):
            lines.extend(list_lines(ch, ctx, depth + 1))
        elif ch.name == "li":
            count += 1
            nested = [c for c in ch.children if isinstance(c, Tag) and c.name in ("ul", "ol")]
            parts = [inline_node(c, ctx) for c in ch.children if c not in nested]
            text = clean("".join(parts), ctx)
            if text:
                marker = f"{count}." if lst.name == "ol" else "-"
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


def is_bold_only(cell: Tag, ctx: Ctx) -> bool:
    strong = cell.find(["strong", "b"])
    return bool(strong) and clean(cell.get_text(" "), ctx) == clean(strong.get_text(" "), ctx)


def table_markdown(table: Tag, ctx: Ctx) -> str:
    """GFM table. A first row of only <th> is the header. Other <th> cells are row labels (bold)."""
    rows: list[list[tuple[str, str]]] = []
    bold_rows: list[bool] = []  # row is made only of bold cells (a header drawn with <strong>)
    for cells in table_rows(table):
        row: list[tuple[str, str]] = []
        for c in cells:
            text = clean(inline(c, ctx), ctx, breaks="<br>").replace("|", "\\|")
            span = int(c.get("colspan", 1)) if str(c.get("colspan", 1)).isdigit() else 1
            row.append((c.name, text))
            row.extend([(c.name, "")] * (span - 1))
        if row:
            rows.append(row)
            bold_rows.append(all(is_bold_only(c, ctx) for c in cells if c.get_text(strip=True)))
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    all_th = all(kind == "th" for kind, _ in rows[0])
    header_row = rows[0] if all_th or (bold_rows[0] and any(t for _, t in rows[0])) else None
    body = rows[1:] if header_row else rows
    header = [t for _, t in header_row] if header_row else [""] * width

    def fmt(cells: list[str]) -> str:
        return "| " + " | ".join(cells + [""] * (width - len(cells))) + " |"

    lines = [fmt(header), fmt(["---"] * width)]
    for r in body:
        lines.append(fmt([f"**{t}**" if k == "th" and t else t for k, t in r]))
    return "\n".join(lines)


def to_sections(found: list[Block]) -> list[dict]:
    """Split blocks by heading. Sections with no text are dropped; `parents` keeps the headings
    above a section (for example the FAQ category above a question).

    Headings are stored without link markup; if a heading was a link its URL is `heading_url`."""
    sections: list[dict] = []
    stack: list[dict] = []  # open headings, outermost first
    cur: dict | None = None

    def push() -> None:
        if cur and cur["parts"]:
            sections.append({"heading": cur["heading"], "level": cur["level"],
                             "parents": cur["parents"], "heading_url": cur["url"],
                             "markdown": "\n\n".join(cur["parts"])})  # fmt: skip

    for kind, level, raw in found:
        if kind == "h":
            push()
            text, url = clean_heading(raw)
            while stack and stack[-1]["level"] >= level:
                stack.pop()
            cur = {
                "heading": text,
                "level": level,
                "parents": [dict(h) for h in stack],
                "url": url,
                "parts": [],
            }
            stack.append({"level": level, "heading": text})
        else:
            if cur is None:
                cur = {"heading": None, "level": 0, "parents": [], "url": None, "parts": []}
            cur["parts"].append(raw)
    push()
    return sections


def numbers_on_lines(text: str, label: re.Pattern) -> list[str]:
    """The phone numbers printed on the lines of `text` that match `label`."""
    return sorted(
        {n for line in text.splitlines() if label.search(line) for n in PHONE.findall(line)}
    )


def contact_block(soup: BeautifulSoup, ctx: Ctx) -> dict:
    """Keep the "CONTACT US" panel and any panel with HOURS in its heading; drop promo panels."""
    panels = []
    for panel in soup.select(PANELS):
        if panel.find_parent(class_="panel"):
            continue  # nested panels are already part of their parent's body
        head = panel.select_one(".panel-heading")
        if head:
            heading = clean(head.get_text(" "), ctx)
        else:  # some panels have no heading element: the title is the first line of text
            heading = clean(next(panel.stripped_strings, ""), ctx)
        if heading.lower() != "contact us" and "hours" not in heading.lower():
            continue
        body = panel.select_one(".panel-body") or panel
        found = blocks(body.children, ctx)
        if found and found[0][2] == heading:  # the title was inside the body: do not repeat it
            found = found[1:]
        md = "\n\n".join(text for _, _, text in found)
        panels.append({"heading": heading, "markdown": md})
    text = "\n".join(p["markdown"] for p in panels)
    return {
        "embed": False,  # the per-owner contact record is used instead; chunking skips this
        "panels": panels,
        "emails": sorted(set(EMAIL.findall(text))),
        # Only a number on a "Phone:" or "Office Phone:" line is a phone. The fax and the 24/7
        # AI-agent number keep their own fields; the panel text keeps their labels.
        "phones": numbers_on_lines(text, PHONE_LINE),
        "fax": numbers_on_lines(text, FAX_LINE),
        "ai_agent_line": numbers_on_lines(text, AI_AGENT_LINE),
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
            url = strip_long_query(absolute(href, base))[0]
            if url not in seen and not is_login_url(url):
                seen.add(url)
                found.append({"url": url, "text": " ".join(a.get_text(" ").split())})
    return found


def not_collected(meta: dict, reason: str, title: str | None = None) -> dict:
    return {**meta, "title": title, "status": "not_collected", "reason": reason,
            "index": False, "index_reason": f"not collected: {reason}", "doc_type": None,
            "note": None, "stripped_urls": [], "sections": [],
            "contact": {"embed": False, "panels": [], "emails": [], "phones": [], "fax": [],
                        "ai_agent_line": []}, "chair": None,
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
        "index": True,
        "index_reason": None,
        "doc_type": None,
        "note": None,
        "stripped_urls": ctx.stripped_urls,
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
    shown: list[str] = []  # headings already printed, so a parent heading appears once
    for s in record["sections"]:
        for h in [*s.get("parents", []), {"level": s["level"], "heading": s["heading"]}]:
            if h["heading"] and h["heading"] not in shown:
                lines.append(f"{'#' * max(h['level'], 1)} {h['heading']}")
                shown.append(h["heading"])
        lines.append(s["markdown"])
    for p in record["contact"]["panels"]:
        lines += [f"**{p['heading']}**", p["markdown"]]
    return "\n\n".join(lines) + "\n"
