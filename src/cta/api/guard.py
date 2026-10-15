"""Cost and abuse guards of the API (Phase 4 step 7, Stage 1; docs/decisions.md).

Plain code, API layer only. In the order they run inside POST /ask: the kill switch, the
per-visitor rate limit and the daily spend cap. The timeouts are applied in app.py.

Privacy: the visitor's network address is read in ONE place (`Guard.visitor_key`) and goes straight
into a salted hash. The salt is random, made at start-up and never saved. The counters live in this
object's memory only; they are never written to the database, a log or /health, and a restart
clears them.
"""

import hashlib
import os
import secrets
import threading
import time
from collections import Counter, OrderedDict, deque
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from cta.settings import ROOT

# The fixed replies. None contains anything the student typed.
TEXTS = {
    "kill_switch": "The assistant is switched off for now. Please check back later.",
    "rate_limited": "You're asking quickly. Please wait a moment and try again.",
    "daily_cap": "The assistant has reached its limit for today. Please try again tomorrow.",
    "timeout": "That took too long. Please try again in a moment.",
}
# Statuses of failed requests: their cost is unknown, so each counts a flat estimate.
FAILED_STATUSES = ("provider_error", "internal_error", "timeout")
BLOCK_REASONS = ("kill_switch", "rate_limited", "daily_cap", "timeout", "distress", "bereavement",
                 "personal_data", "injection", "output", "stress", "non_english")  # fmt: skip
DISABLED_FILE = Path("data") / "api_disabled"


def utc_now() -> datetime:
    return datetime.now(UTC)


def day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


class Guard:
    """The state of the guardrails: counters, caches and the blocked counts shown in /health."""

    def __init__(self, settings: dict, root: Path = ROOT, now: Callable[[], datetime] = utc_now,
                 monotonic: Callable[[], float] = time.monotonic):  # fmt: skip
        self.s, self.root, self.now, self.monotonic = settings, root, now, monotonic
        self.salt = secrets.token_bytes(16)  # never saved; a restart makes a new one
        self.lock = threading.Lock()
        self.visitors: OrderedDict[str, dict] = OrderedDict()
        self.blocked: Counter[str] = Counter()
        self.spend_check_failures = 0
        self.redacted = 0  # questions scrubbed since the start (a count, no text)
        self._spend: tuple[float, float] | None = None  # (monotonic time, sum)

    # ---- 1. the kill switch ----

    def disabled(self) -> bool:
        return bool(self.s["disabled"]) or os.path.exists(self.root / DISABLED_FILE)

    # ---- 2. the rate limit ----

    def visitor_key(self, request) -> str:
        """A salted hash of the network address. The only read of the address in the API."""
        address = request.client.host if request.client else ""
        return hashlib.sha256(self.salt + address.encode()).hexdigest()

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
        start = day_start(self.now())
        row = conn.execute(
            "SELECT coalesce(sum(coalesce(cost_usd, "
            "CASE WHEN status = ANY(%s) THEN %s ELSE 0 END)), 0) "
            "FROM request_logs WHERE source = 'api' AND ts >= %s",
            (list(FAILED_STATUSES), self.s["failed_request_cost_usd"], start),
        ).fetchone()
        return float(row[0])

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
        return total is not None and total >= self.s["daily_spend_cap_usd"]

    # ---- the order of the checks ----

    def stage1(self, request, connect: Callable) -> str | None:
        """The reason this request is blocked, or None. Counts the block."""
        reason = None
        if self.disabled():
            reason = "kill_switch"
        elif self.rate_limited(self.visitor_key(request)):
            reason = "rate_limited"
        elif self.over_cap(connect):
            reason = "daily_cap"
        if reason:
            self.blocked[reason] += 1
        return reason

    def health(self, connect: Callable) -> dict:
        total = self.cached_spend(connect)
        cap = self.s["daily_spend_cap_usd"]
        return {
            "disabled": self.disabled(),
            "spend_today_usd": None if total is None else round(total, 6),
            "spend_cap_usd": cap,
            "spend_cap_reached": total is not None and total >= cap,
            "spend_check_failures": self.spend_check_failures,
            "blocked": {k: self.blocked.get(k, 0) for k in BLOCK_REASONS},
            "redacted": self.redacted,
        }  # fmt: skip
