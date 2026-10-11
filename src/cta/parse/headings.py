"""Heading cleanup: no markdown link markup in headings or heading paths.

A heading that was a link, "[Data Science/BS](https://.../programs/DSCI-BS)", becomes the visible
text "Data Science/BS"; the URL is kept in the section's `heading_url`.
"""

import re

LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]*)\)")


def clean_heading(text: str | None) -> tuple[str | None, str | None]:
    """(heading without link markup, the URL of its first link or None)."""
    if text is None:
        return None, None
    found = LINK.search(text)
    return (LINK.sub(r"\1", text), found[2] if found else None)


def link_disagreement(text: str, url: str) -> str | None:
    """A hint that a heading's link text and its URL are not about the same thing, else None.

    For a catalog program link ("Data Science/BS" -> .../programs/DSCI-BS) the award after the
    slash must start the last part of the slug (BTech -> BT, BS -> BS). For other links, at least
    one word of the text must appear in the URL. Only a hint: the owner decides."""
    if "/programs/" in url and "/" in text:
        award = text.rsplit("/", 1)[1].lower()
        slug = url.rstrip("/").rsplit("-", 1)[-1].lower()
        if not (award.startswith(slug) or slug.startswith(award)):
            return f"award {award!r} does not match the catalog slug part {slug!r}"
        return None
    words = [w.lower() for w in re.findall(r"[A-Za-z]{4,}", text)]
    if words and not any(w in url.lower() for w in words):
        return "no word of the link text appears in the URL"
    return None
