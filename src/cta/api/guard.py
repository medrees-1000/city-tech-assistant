"""Cost and abuse guards of the API (Phase 4 step 7, Stage 1; docs/decisions.md).

Plain code, API layer only. In the order they run inside POST /ask: the per-visitor rate limit
(`stage1`), then the regex safety screen (app.py), then the kill switch and the daily and monthly
spend caps (`cap_reason`). The timeouts are applied in app.py.

Privacy: the visitor's network address is read in ONE place (`Guard.visitor_key`) and goes straight
into a keyed hash (HMAC-SHA256). The key is CTA_IP_SALT from the environment, or a random one made
at start-up and never saved. The counters live in this object's memory only; they are never
written to the database, a log or /health, and a restart clears them.

Behind the Vercel proxy (CTA_PROXY_SECRET set): a request must carry the shared secret in the
x-cta-proxy-secret header, and only then is the visitor read from the x-real-ip header that the
proxy set. Without the variable (local development) nothing changes.
"""

import hashlib
import hmac
import os
import secrets
import socket
import threading
import time
from collections import Counter, OrderedDict, deque
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from cta.api.screen import CRISIS_LINE
from cta.settings import ROOT

# The fixed replies. None contains anything the student typed.
TEXTS = {
    "kill_switch": f"The assistant is temporarily paused. Please check back later. {CRISIS_LINE}",
    "rate_limited": "You're asking quickly. Please wait a moment and try again.",
    "daily_cap": (
        f"The assistant has reached its limit for today. Please try again tomorrow. {CRISIS_LINE}"
    ),
    "timeout": "That took too long. Please try again in a moment.",
}
# Statuses of failed requests: their cost is unknown, so each counts a flat estimate.
FAILED_STATUSES = ("provider_error", "internal_error", "timeout")
BLOCK_REASONS = ("kill_switch", "rate_limited", "daily_cap", "monthly_cap", "timeout", "distress",
                 "danger",
                 "bereavement", "personal_data", "injection", "output", "stress",
                 "non_english")  # fmt: skip
DISABLED_FILE = Path("data") / "api_disabled"
PROXY_HEADER = "x-cta-proxy-secret"
FORWARDED_HEADER = "x-real-ip"
VISITOR_HEADER = "x-cta-visitor"  # set by web/proxy.ts; preferred over x-real-ip when trusted


def utc_now() -> datetime:
    return datetime.now(UTC)


def day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def month_start(now: datetime) -> datetime:
    """00:00 UTC on the first day of the month of `now` (the monthly cap counts from here)."""
    return day_start(now).replace(day=1)


def valid_ip(text: str) -> bool:
    """True for a plain IPv4 or IPv6 text (anything else from a header is ignored)."""
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_pton(family, text)
        except (OSError, ValueError):
            continue
        return True
    return False


def paused_text(contacts: dict | None = None) -> str:
    """The fixed reply at the monthly cap. The contact lines are written by code from
    config/contacts.yaml (the Registrar and Advisement), never by a model, and the text holds
    nothing the student typed."""
    from cta.graph.contact import contact_line

    return (
        "The assistant is paused for the rest of this month to stay within its budget. It will "
        "answer questions again next month. For help now: "
        f"{contact_line('registrar', contacts)} {contact_line('advisement', contacts)} "
        f"{CRISIS_LINE}"
    )


class Guard:
    """The state of the guardrails: counters, caches and the blocked counts shown in /health."""

    def __init__(self, settings: dict, root: Path = ROOT, now: Callable[[], datetime] = utc_now,
                 monotonic: Callable[[], float] = time.monotonic, proxy_secret: str = "",
                 ip_salt: str = ""):  # fmt: skip
        self.s, self.root, self.now, self.monotonic = settings, root, now, monotonic
        self.proxy_secret = proxy_secret
        self.proxy_rejected = 0  # requests refused for a missing or wrong secret (a count only)
        # the key of the hash: from the environment, or random and never saved
        self.salt = ip_salt.encode() if ip_salt else secrets.token_bytes(16)
        self.lock = threading.Lock()
        self.visitors: OrderedDict[str, dict] = OrderedDict()
        self.blocked: Counter[str] = Counter()
        self.spend_check_failures = 0
        self.redacted = 0  # questions scrubbed since the start (a count, no text)
        self._spend: tuple[float, float] | None = None  # (monotonic time, sum)
        self._month_spend: tuple[float, float] | None = None  # the same for the UTC month
        # cost of requests whose log row could not be written, for the current UTC day (memory only)
        self._unlogged: tuple[datetime, float] = (day_start(self.now()), 0.0)
        self._unlogged_month: tuple[datetime, float] = (month_start(self.now()), 0.0)

    # ---- 1. the kill switch ----

    def disabled(self) -> bool:
        return bool(self.s["disabled"]) or os.path.exists(self.root / DISABLED_FILE)

    # ---- 2. the rate limit ----

    def proxy_ok(self, request) -> bool:
        """True when no proxy secret is configured (local use) or the request carries it."""
        if not self.proxy_secret:
            return True
        sent = request.headers.get(PROXY_HEADER, "")
        return hmac.compare_digest(sent.encode(), self.proxy_secret.encode())

    def proxy_trusted(self, request) -> bool:
        """True only when a proxy secret is configured AND this request carries it: the one case
        in which the forwarded visitor is used. (Local use, with no secret, is not "trusted".)"""
        return bool(self.proxy_secret) and self.proxy_ok(request)

    def forwarded_present(self, request) -> bool:
        """Whether the request carries a usable forwarded visitor (a plain IP) in a header the
        limiter key reads: x-cta-visitor or x-real-ip when the secret matched, else x-real-ip.
        Logging only; visitor_key makes the same choice."""
        trusted = self.proxy_trusted(request)
        names = (VISITOR_HEADER, FORWARDED_HEADER) if trusted else (FORWARDED_HEADER,)
        return any(valid_ip(request.headers.get(name, "").strip()) for name in names)

    def tag(self, value: str) -> str:
        """The salted HMAC-SHA256 of a visitor value, in hex (the limiter key; never logged)."""
        return hmac.new(self.salt, value.encode(), hashlib.sha256).hexdigest()

    def visitor_key(self, request) -> str:
        """A keyed hash (HMAC-SHA256) of the network address. The only read of the address in the
        API. With a proxy secret set and sent, the address is the one the proxy forwarded:
        x-cta-visitor first, then x-real-ip; otherwise the connection address."""
        host = request.client.host if request.client else ""
        if self.proxy_secret and self.proxy_ok(request):
            for name in (VISITOR_HEADER, FORWARDED_HEADER):
                forwarded = request.headers.get(name, "").strip()
                if valid_ip(forwarded):
                    host = forwarded
                    break
        return self.tag(host)

    def rate_limited(self, key: str) -> bool:
        """Count this request for `key`; True when it is over the per-minute or per-day limit."""
        now, today = self.monotonic(), day_start(self.now())
        with self.lock:
            entry = self.visitors.pop(key, None) or {"times": deque(), "day": today, "n": 0}
            self.visitors[key] = entry  # most recently used last
            while len(self.visitors) > self.s["rate_limit_max_keys"]:
                self.visitors.popitem(last=False)  # the least recently used visitor is forgotten
            if entry["day"] != today:
                entry["day"], entry["n"] = today, 0
            times = entry["times"]
            while times and now - times[0] >= 60:
                times.popleft()
            if len(times) >= self.s["rate_per_minute"] or entry["n"] >= self.s["rate_per_day"]:
                return True
            times.append(now)
            entry["n"] += 1
            return False

    # ---- 3. the daily spend cap ----

    def spend_today(self, conn) -> float:
        """Today's (UTC) cost of public requests; failed requests count a flat estimate."""
        return self.spend_since(conn, day_start(self.now()))

    def spend_month(self, conn) -> float:
        """This UTC month's cost of public requests (the same rows and estimate as the day)."""
        return self.spend_since(conn, month_start(self.now()))

    def spend_since(self, conn, start: datetime) -> float:
        row = conn.execute(
            "SELECT coalesce(sum(coalesce(cost_usd, "
            "CASE WHEN status = ANY(%s) THEN %s ELSE 0 END)), 0) "
            "FROM request_logs WHERE source = 'api' AND ts >= %s",
            (list(FAILED_STATUSES), self.s["failed_request_cost_usd"], start),
        ).fetchone()
        return float(row[0])

    def add_unlogged(self, record: dict) -> None:
        """Count the cost of a request whose log row failed, so the cap still sees it (T13)."""
        cost = record.get("cost_usd")
        if cost is None:  # a failed request: the same flat estimate the database sum uses
            cost = (
                self.s["failed_request_cost_usd"] if record.get("status") in FAILED_STATUSES else 0
            )
        with self.lock:
            self._unlogged = (day_start(self.now()), self.unlogged_today() + float(cost))
            self._unlogged_month = (month_start(self.now()), self.unlogged_month() + float(cost))

    def unlogged_today(self) -> float:
        day, total = self._unlogged
        return total if day == day_start(self.now()) else 0.0

    def unlogged_month(self) -> float:
        month, total = self._unlogged_month
        return total if month == month_start(self.now()) else 0.0

    def cached_spend(self, connect: Callable) -> float | None:
        """The sum, cached for spend_cache_s. None when the query failed (the caller fails open)."""
        now = self.monotonic()
        if self._spend and now - self._spend[0] < self.s["spend_cache_s"]:
            return self._spend[1]
        try:
            with connect() as conn:
                total = self.spend_today(conn)
        except Exception:  # noqa: BLE001 - any failure: count it, allow the request
            self.spend_check_failures += 1
            return None
        self._spend = (now, total)
        return total

    def over_cap(self, connect: Callable) -> bool:
        total = self.cached_spend(connect)
        return total is not None and total + self.unlogged_today() >= self.s["daily_spend_cap_usd"]

    # ---- 4. the monthly spend cap (checked AFTER the safety screen, see app.py) ----

    def cached_month_spend(self, connect: Callable) -> float | None:
        """This month's sum, cached for monthly_spend_cache_s. None when the query failed."""
        now = self.monotonic()
        if self._month_spend and now - self._month_spend[0] < self.s["monthly_spend_cache_s"]:
            return self._month_spend[1]
        try:
            with connect() as conn:
                total = self.spend_month(conn)
        except Exception:  # noqa: BLE001 - any failure: count it, allow the request (fail open)
            self.spend_check_failures += 1
            return None
        self._month_spend = (now, total)
        return total

    def over_monthly_cap(self, connect: Callable) -> bool:
        """True when this month's cost has reached the cap. The caller answers paused_text() and
        makes no model call; the regex safety screen has already run by then."""
        total = self.cached_month_spend(connect)
        cap = self.s["monthly_spend_cap_usd"]
        over = total is not None and total + self.unlogged_month() >= cap
        if over:
            self.blocked["monthly_cap"] += 1
        return over

    # ---- the order of the checks ----

    def stage1(self, request, connect: Callable) -> str | None:
        """The reason this request is blocked, or None. Counts the block."""
        reason = None
        if self.rate_limited(self.visitor_key(request)):
            reason = "rate_limited"
        if reason:
            self.blocked[reason] += 1
        return reason

    def cap_reason(self, connect: Callable) -> str | None:
        """"kill_switch", "daily_cap", "monthly_cap" or None. Called AFTER the regex safety screen
        (app.py): the screen needs no model call and costs nothing, so neither the kill switch nor
        a cap ever replaces its reply."""
        reason = None
        if self.disabled():
            reason = "kill_switch"
        elif self.over_cap(connect):
            reason = "daily_cap"
        elif self.over_monthly_cap(connect):
            return "monthly_cap"  # over_monthly_cap counts its own block
        if reason:
            self.blocked[reason] += 1
        return reason

    def health(self, connect: Callable) -> dict:
        total = self.cached_spend(connect)
        if total is not None:
            total += self.unlogged_today()
        cap = self.s["daily_spend_cap_usd"]
        month = self.cached_month_spend(connect)
        if month is not None:
            month += self.unlogged_month()
        month_cap = self.s["monthly_spend_cap_usd"]
        return {
            "disabled": self.disabled(),
            "spend_today_usd": None if total is None else round(total, 6),
            "spend_cap_usd": cap,
            "spend_cap_reached": total is not None and total >= cap,
            "spend_month_usd": None if month is None else round(month, 6),
            "monthly_cap_usd": month_cap,
            "monthly_cap_reached": month is not None and month >= month_cap,
            "spend_check_failures": self.spend_check_failures,
            "blocked": {k: self.blocked.get(k, 0) for k in BLOCK_REASONS},
            "redacted": self.redacted,
            "proxy_required": bool(self.proxy_secret),
            "proxy_rejected": self.proxy_rejected,
        }  # fmt: skip
