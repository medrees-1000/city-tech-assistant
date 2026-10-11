"""Result type shared by the data checks."""

from dataclasses import dataclass


@dataclass
class Finding:
    check: str
    severity: str  # "fail" or "warning"
    message: str
    course: str | None = None  # the course code, or the page URL for page checks
    accepted: str | None = None  # why the owner accepted this finding (it is still reported)
