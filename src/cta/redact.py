"""Remove personal data from a question before it is stored (request_logs, eval logs)."""

import re

# Order matters: SSN and phone patterns run before the bare 8-digit EMPLID pattern.
_PATTERNS = [
    ("EMAIL", re.compile(r"[\w.+-]+\s?@\s?[\w-]+(?:\.[\w-]+)+")),
    ("SSN", re.compile(r"\b\d{3}[- ]\d{2}[- ]\d{4}\b")),
    ("PHONE", re.compile(r"(?<!\w)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")),
    ("ID", re.compile(r"(?<!\d)\d{8}(?!\d)")),
]


def redact(text: str) -> str:
    """Replace emails, SSN-like numbers, phone numbers and 8-digit CUNY EMPLIDs with [TAG]."""
    for tag, pattern in _PATTERNS:
        text = pattern.sub(f"[{tag}]", text)
    return text
