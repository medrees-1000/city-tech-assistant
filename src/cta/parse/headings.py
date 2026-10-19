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

