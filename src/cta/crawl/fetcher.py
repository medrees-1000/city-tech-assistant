"""The one polite fetcher: rate limit, robots.txt, same-host redirects, raw store, fetch log."""

import json as jsonlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.robotparser import RobotFileParser

import httpx

from cta.crawl.robots import describe, parse_robots
from cta.crawl.store import LogEntry, RawStore, sha256_hex, utc_now
from cta.crawl.urls import host_of, looks_like_login, normalize_url, resolve_redirect

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
