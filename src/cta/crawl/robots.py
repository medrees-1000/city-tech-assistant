"""robots.txt handling: one parsed policy per host."""

from urllib.robotparser import RobotFileParser


def parse_robots(status: int, text: str) -> RobotFileParser:
    """Build a policy from a robots.txt response.

    200 -> parse the rules. 404 (and other 4xx except 401/403) -> no rules, everything allowed.
    401/403 and 5xx -> the file exists but cannot be read, so assume everything is disallowed.
    """
    rp = RobotFileParser()
    if status == 200:
        rp.parse(text.splitlines())
        rp.modified()  # can_fetch() refuses until a check time is recorded
    elif status in (401, 403) or status >= 500:
        rp.disallow_all = True
    else:
        rp.allow_all = True
    return rp


def describe(rp: RobotFileParser) -> str:
    if rp.disallow_all:
        return "robots unreadable: disallow all"
    if rp.allow_all:
        return "no robots rules: allow all"
    return "robots rules parsed"
