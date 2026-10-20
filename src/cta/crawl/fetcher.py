"""The one polite fetcher: rate limit, robots.txt, same-host redirects, raw store, fetch log.

The robots.txt policy, the URL and login rules and the raw store with its fetch log live here too
(they were crawl/robots.py, urls.py and store.py).
"""

import hashlib
import json
import json as jsonlib
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx

# ---- robots.txt handling: one parsed policy per host. (was robots.py) ----

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


# ---- URL normalization and the host/login rules shared by the crawler. (was urls.py) ----

LOGIN_WORDS = ("login", "logout", "signin", "sso", "cas/")


def normalize_url(url: str) -> str:
    """Return an https URL with a lowercase host, default port and no fragment."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"not an http(s) URL: {url!r}")
    netloc = parts.hostname.lower()
    if parts.port and parts.port not in (80, 443):
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit(("https", netloc, parts.path or "/", parts.query, ""))


def resolve_redirect(current_url: str, location: str) -> str:
    """Resolve a Location header (possibly relative) against the current URL and normalize it."""
    return normalize_url(urljoin(current_url, location))


def host_of(url: str) -> str:
    return urlsplit(url).hostname or ""


def looks_like_login(url: str) -> bool:
    path = urlsplit(url).path.lower()
    return any(word in path for word in LOGIN_WORDS)


# ---- Raw store under data/raw/ and the append-only fetch log. (was store.py) ----

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class LogEntry:
    """One row per HTTP request attempt (redirect hops, robots.txt and blocked URLs included)."""

    timestamp: str
    method: str
    url: str
    status: int | None
    content_hash: str | None
    bytes: int
    saved_as: str | None
    note: str = ""


class RawStore:
    def __init__(self, root: Path):
        self.root = root
        self.log_path = root / "fetch_log.jsonl"

    def save(self, method: str, url: str, body: bytes, content_type: str, req_body: bytes) -> str:
        """Write the response untouched; return its path relative to the store root."""
        parts = urlsplit(url)
        slug = re.sub(r"[^A-Za-z0-9]+", "-", f"{parts.path}-{parts.query}").strip("-")[:80]
        key = sha256_hex(f"{method} {url}".encode() + req_body)[:10]
        ext = _extension(content_type)
        rel = Path(parts.hostname or "unknown") / f"{slug or 'index'}-{key}.{ext}"
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return str(rel)

    def log(self, entry: LogEntry) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

    def read_log(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line]


def _extension(content_type: str) -> str:
    ct = content_type.lower()
    if "json" in ct:
        return "json"
    if "html" in ct:
        return "html"
    if "pdf" in ct:
        return "pdf"
    if "xml" in ct:
        return "xml"
    return "txt" if ct.startswith("text/") else "bin"


REDIRECT_CODES = {301, 302, 303, 307, 308}


class FetchBlocked(Exception):
    """The fetcher refused to request a URL (host not allowed, login link, robots, bad redirect)."""


@dataclass
class FetchResult:
    url: str  # normalized URL that was requested
    final_url: str  # URL of the last response after same-host redirects
    status: int
    content: bytes
    content_type: str
    content_hash: str
    saved_as: str | None


class Fetcher:
    def __init__(
        self,
        client: httpx.Client,
        store: RawStore,
        user_agent: str,
        allowed_hosts: set[str],
        min_interval: float = 1.0,
        max_redirects: int = 5,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.client = client
        self.store = store
        self.user_agent = user_agent
        self.allowed_hosts = allowed_hosts
        self.min_interval = min_interval
        self.max_redirects = max_redirects
        self._clock = clock
        self._sleep = sleep
        self._last_request: float | None = None
        self._robots: dict[str, RobotFileParser] = {}

    def fetch(
        self,
        url: str,
        *,
        method: str = "GET",
        json: object | None = None,
        headers: dict[str, str] | None = None,
    ) -> FetchResult:
        """Fetch a URL, following same-host redirects. Raises FetchBlocked if a rule forbids it."""
        start = normalize_url(url)
        current = start
        for _ in range(self.max_redirects + 1):
            self._check_allowed(current, method)
            resp, saved = self._request(current, method, json, headers)
            if resp.status_code not in REDIRECT_CODES:
                return self._result(start, current, resp, saved)
            location = resp.headers.get("location")
            if not location:
                raise FetchBlocked(f"redirect without Location from {current}")
            target = resolve_redirect(current, location)
            if host_of(target) != host_of(start):
                self._log_blocked(method, target, "redirect to another host")
                raise FetchBlocked(f"redirect from {current} leaves host: {target}")
            current = target
        raise FetchBlocked(f"too many redirects starting at {start}")

    def _check_allowed(self, url: str, method: str) -> None:
        host = host_of(url)
        if host not in self.allowed_hosts:
            self._log_blocked(method, url, "host not in sources.yaml")
            raise FetchBlocked(f"host not allowed: {host}")
        if looks_like_login(url):
            self._log_blocked(method, url, "login link")
            raise FetchBlocked(f"login link: {url}")
        if not self._robots_for(host).can_fetch(self.user_agent, url):
            self._log_blocked(method, url, "disallowed by robots.txt")
            raise FetchBlocked(f"robots.txt disallows {url}")

    def _robots_for(self, host: str) -> RobotFileParser:
        if host not in self._robots:
            url = f"https://{host}/robots.txt"
            resp, _ = self._request(url, "GET", None, None)
            if resp.status_code in REDIRECT_CODES:
                # Treat a redirecting robots.txt as unreadable rather than guessing.
                resp = httpx.Response(503)
            rp = parse_robots(resp.status_code, resp.text if resp.status_code == 200 else "")
            self._robots[host] = rp
            self.store.log(
                LogEntry(
                    utc_now(),
                    "GET",
                    url,
                    resp.status_code,
                    sha256_hex(resp.content),
                    len(resp.content),
                    None,
                    f"robots.txt check: {describe(rp)}",
                )
            )
        return self._robots[host]

    def _request(self, url, method, json, headers) -> tuple[httpx.Response, str | None]:
        self._wait()
        merged = {"User-Agent": self.user_agent, **(headers or {})}
        try:
            resp = self.client.request(method, url, json=json, headers=merged)
        except httpx.HTTPError as exc:
            self.store.log(LogEntry(utc_now(), method, url, None, None, 0, None, f"error: {exc}"))
            raise
        self.client.cookies.clear()  # never keep or send cookies
        if url.endswith("/robots.txt"):
            return resp, None  # robots rows are logged by _robots_for
        note = (
            f"redirect to {resp.headers.get('location')}"
            if resp.status_code in REDIRECT_CODES
            else ""
        )
        saved = None
        if resp.status_code == 200:
            saved = self._save(method, url, json, resp)
        self.store.log(
            LogEntry(
                utc_now(),
                method,
                url,
                resp.status_code,
                sha256_hex(resp.content),
                len(resp.content),
                saved,
                note,
            )
        )
        return resp, saved

    def _save(self, method, url, json, resp) -> str:
        req_body = jsonlib.dumps(json, sort_keys=True).encode() if json is not None else b""
        ctype = resp.headers.get("content-type", "")
        return self.store.save(method, url, resp.content, ctype, req_body)

    def _result(self, start, final, resp, saved) -> FetchResult:
        return FetchResult(
            url=start,
            final_url=final,
            status=resp.status_code,
            content=resp.content,
            content_type=resp.headers.get("content-type", ""),
            content_hash=sha256_hex(resp.content),
            saved_as=saved,
        )

    def _wait(self) -> None:
        if self._last_request is not None:
            delay = self._last_request + self.min_interval - self._clock()
            if delay > 0:
                self._sleep(delay)
        self._last_request = self._clock()

    def _log_blocked(self, method: str, url: str, reason: str) -> None:
        self.store.log(LogEntry(utc_now(), method, url, None, None, 0, None, f"blocked: {reason}"))
