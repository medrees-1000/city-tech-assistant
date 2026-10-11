"""Automatic web-page checks from docs/data-validation.md ("Web pages").

Run: uv run python -m cta.validate.pages
Findings the owner has accepted (ACCEPTED below) are still printed, with the reason, but do not
count as unexpected failures.
Pending manual items (not here): chair details vs the department PDF; refund pages show which
terms they cover.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from cta.parse.html import PANELS, is_login_url
from cta.settings import ROOT
from cta.validate.findings import Finding

EMAIL_OK = re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$")
SPACED = re.compile(r"\S\s+@\w|\w@\s+\S")
PLACEHOLDER = re.compile(r"\{\{.*?\}\}")
CHAIR_FIELDS = ("name", "role", "room", "phone", "email")
LINK = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")
MAX_QUERY = 100
WI_FALL26 = "https://www.citytech.cuny.edu/advisement/writing-intensive-fall26.aspx"
TIME = re.compile(r"\d{1,2}:\d{2}\s*[AaPp]\.?[Mm]\.?")
WI_PLAIN = "https://www.citytech.cuny.edu/advisement/writing-intensive.aspx"
# Known and accepted by the owner (2026-10-11). (check, URL) -> reason. Still reported every run.
ACCEPTED = {
    ("body_non_empty", WI_FALL26): "known and accepted: returns 200 with an empty main content div;"
    " the page is kept as not_collected; cause not investigated",
    (
        "known_404",
        WI_PLAIN,
    ): "known and accepted: returns 404 although gen-ed and six-steps link to it;"
    " not collected; cause not investigated",
}


def page_text(rec: dict) -> str:
    parts = [f"{s['heading'] or ''}\n{s['markdown']}" for s in rec["sections"]]
    parts += [p["markdown"] for p in rec["contact"]["panels"]]
    return "\n".join(parts)


def check_status(manifest: list[dict]) -> list[Finding]:
    return [
        Finding("status_200", "fail", f"status {e['status']} {e['error']}".strip(), e["url"])
        for e in manifest
        if e["status"] != 200
    ]


def check_redirects(manifest: list[dict]) -> list[Finding]:
    """A page that moved must end at a 200 on the same host."""
    found = []
    for e in manifest:
        if not e["final_url"] or e["final_url"] == e["url"]:
            continue
        same_host = urlsplit(e["final_url"]).hostname == urlsplit(e["url"]).hostname
        if e["status"] != 200 or not same_host:
            msg = f"redirect to {e['final_url']} ended with {e['status']}, same host: {same_host}"
            found.append(Finding("redirects", "fail", msg, e["url"]))
    return found


def check_bodies(records: list[dict]) -> list[Finding]:
    """Non-empty main content. Placeholder-only pages are logged as not collected (a warning)."""
    found = []
    for r in records:
        if r["status"] == "collected":
            if not page_text(r).strip():
                found.append(
                    Finding("body_non_empty", "fail", "no text after stripping", r["source_url"])
                )
        elif r["http_status"] != 200:
            continue  # already reported by status_200
        elif r["reason"] == "only template placeholders":
            found.append(Finding("not_collected", "warning", r["reason"], r["source_url"]))
        else:
            found.append(
                Finding("body_non_empty", "fail", f"not collected: {r['reason']}", r["source_url"])
            )
    return found


def check_hashes_and_log(manifest: list[dict], log: list[dict]) -> list[Finding]:
    """Every fetched page has a content hash and a matching fetch-log row; the log has no gaps."""
    found = []
    by_url: dict[str, list[dict]] = {}
    for row in log:
        by_url.setdefault(row["url"], []).append(row)
        if row["status"] is None and not row.get("note"):
            found.append(Finding("fetch_log", "fail", "row has no status and no note", row["url"]))
        if not row.get("timestamp"):
            found.append(Finding("fetch_log", "fail", "row has no timestamp", row["url"]))
    for e in manifest:
        if e["status"] is None:
            continue
        if not e["content_hash"]:
            found.append(Finding("content_hash", "fail", "no content hash stored", e["url"]))
        urls = {e["url"], e["final_url"]}
        rows = [r for u in urls for r in by_url.get(u, [])]
        if not any(
            r["content_hash"] == e["content_hash"] and r["status"] == e["status"] for r in rows
        ):
            found.append(
                Finding("fetch_log", "fail", "no fetch-log row with this status and hash", e["url"])
            )
    return found


def check_cleaned_text(records: list[dict]) -> list[Finding]:
    """No leftover placeholders and no spaces inside email addresses in the cleaned output."""
    found = []
    for r in records:
        text = page_text(r)
        if PLACEHOLDER.search(text):
            found.append(
                Finding("placeholders", "fail", "{{...}} left in cleaned text", r["source_url"])
            )
        if SPACED.search(text):
            found.append(
                Finding("emails", "fail", "space around @ in cleaned text", r["source_url"])
            )
        for email in r["contact"]["emails"]:
            if not EMAIL_OK.match(email):
                found.append(
                    Finding("emails", "fail", f"malformed email {email!r}", r["source_url"])
                )
    return found


def check_chairs(records: list[dict]) -> list[Finding]:
    """Chair details on chairperson.aspx are complete and well formed (web side only)."""
    found = []
    for r in records:
        if not r["source_url"].endswith("chairperson.aspx") or r["status"] != "collected":
            continue
        chair = r["chair"]
        if not chair:
            found.append(Finding("chair", "fail", "no chair block found", r["source_url"]))
            continue
        missing = [f for f in CHAIR_FIELDS if not chair.get(f)]
        if missing:
            found.append(Finding("chair", "fail", f"chair missing {missing}", r["source_url"]))
        elif not EMAIL_OK.match(chair["email"]):
            found.append(
                Finding(
                    "chair", "fail", f"malformed chair email {chair['email']!r}", r["source_url"]
                )
            )
    return found


def check_links(records: list[dict]) -> list[Finding]:
    """No login links, and no link keeps a query string over 100 characters (both are removed)."""
    found = []
    for r in records:
        urls = LINK.findall(page_text(r)) + [link["url"] for link in r["pdf_links"]]
        for url in dict.fromkeys(urls):
            if is_login_url(url):
                found.append(
                    Finding("login_links", "fail", f"login link kept: {url[:80]}", r["source_url"])
                )
            elif len(urlsplit(url).query) > MAX_QUERY:
                msg = f"query string of {len(urlsplit(url).query)} characters kept: {url[:80]}"
                found.append(Finding("long_urls", "fail", msg, r["source_url"]))
    return found


def check_sections(records: list[dict]) -> list[Finding]:
    """No section with empty markdown."""
    return [
        Finding("empty_sections", "fail", f"empty section {s['heading']!r}", r["source_url"])
        for r in records
        for s in r["sections"]
        if not s["markdown"].strip()
    ]


def check_index_flags(records: list[dict]) -> list[Finding]:
    """Every record has index (bool); index false always says why."""
    found = []
    for r in records:
        if not isinstance(r.get("index"), bool):
            found.append(Finding("index", "fail", "index missing or not a bool", r["source_url"]))
        elif not r["index"] and not r.get("index_reason"):
            found.append(
                Finding("index", "fail", "index is false without a reason", r["source_url"])
            )
        elif r["index"] and r["status"] != "collected":
            found.append(
                Finding("index", "fail", "indexed page was not collected", r["source_url"])
            )
    return found


def check_contacts(contacts: list[dict]) -> list[Finding]:
    """The panels of an owner should be identical on all its pages; differences are warnings."""
    return [
        Finding("contacts", "warning", f"{c['owner']}: panels differ between pages", c["owner"])
        for c in contacts
        if not c["consistent"]
    ]


def squash_time(t: str) -> str:
    return re.sub(r"[\s.]", "", t).upper()


def raw_hours(html: str) -> list[dict]:
    """Sidebar panels (the selector the contact blocks use) that print hours: HOURS in the heading
    or a clock time in the visible text (HTML comments are not visible, so they do not count)."""
    found = []
    for panel in BeautifulSoup(html, "html.parser").select(PANELS):
        if panel.find_parent(class_="panel"):
            continue
        head = panel.select_one(".panel-heading")
        heading = head.get_text(" ", strip=True) if head else next(panel.stripped_strings, "")
        times = TIME.findall(panel.get_text(" ", strip=True))
        if "hours" in heading.lower() or times:
            found.append({"heading": heading, "times": [squash_time(t) for t in times]})
    return found


def load_raw(manifest: list[dict], raw_root: Path) -> dict[str, str]:
    """The saved raw HTML of every fetched page, by its URL."""
    return {
        e["url"]: (raw_root / e["saved_as"]).read_text(encoding="utf-8", errors="replace")
        for e in manifest
        if e.get("saved_as") and e.get("status") == 200
    }


def check_hours_stored(
    manifest: list[dict], raw: dict[str, str], contacts: list[dict]
) -> list[Finding]:
    """If the raw HTML of any page of an owner has an hours panel, the owner's contact record has
    hours, and every clock time printed in those panels is in the stored hours."""
    owner_of = {e["url"]: e["owner"] for e in manifest}
    printed: dict[str, set[str]] = {}
    for url, html in raw.items():
        for panel in raw_hours(html):
            printed.setdefault(owner_of[url], set()).update(panel["times"])
    by_owner = {c["owner"]: c for c in contacts}
    found = []
    for owner, times in sorted(printed.items()):
        stored = " ".join(h["markdown"] for h in (by_owner.get(owner) or {}).get("hours", []))
        if not stored:
            found.append(
                Finding("hours_missing", "fail", "the page prints hours, none stored", owner)
            )
            continue
        have = {squash_time(t) for t in TIME.findall(stored)}
        if times - have:
            found.append(
                Finding(
                    "hours_incomplete",
                    "fail",
                    f"times printed, not stored: {sorted(times - have)}",
                    owner,
                )
            )
    return found


def check_known_404s(log: list[dict]) -> list[Finding]:
    """A page the owner accepted as a 404 must still be a 404 (the latest fetch-log row decides)."""
    found = []
    for check, url in ACCEPTED:
        if check != "known_404":
            continue
        rows = [r for r in log if r["url"] == url and r["status"] is not None]
        if not rows:
            found.append(
                Finding("known_404_changed", "fail", "accepted URL was never fetched", url)
            )
        elif rows[-1]["status"] == 404:
            found.append(Finding("known_404", "fail", "returns 404", url))
        else:
            msg = f"now returns {rows[-1]['status']}; revisit the accepted list"
            found.append(Finding("known_404_changed", "fail", msg, url))
    return found


def apply_accepted(findings: list[Finding]) -> list[Finding]:
    for f in findings:
        f.accepted = ACCEPTED.get((f.check, f.course))
    return findings


def unexpected_failures(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == "fail" and not f.accepted]


def email_repairs(records: list[dict]) -> dict[str, list[dict]]:
    """Pages where an email address had to be repaired (for the validation log)."""
    return {r["source_url"]: r["email_repairs"] for r in records if r["email_repairs"]}


def run_page_checks(
    manifest: list[dict],
    records: list[dict],
    log: list[dict],
    contacts: list[dict] | None = None,
    raw: dict[str, str] | None = None,
) -> list[Finding]:
    return apply_accepted(
        [
            *check_status(manifest),
            *check_redirects(manifest),
            *check_bodies(records),
            *check_hashes_and_log(manifest, log),
            *check_cleaned_text(records),
            *check_chairs(records),
            *check_links(records),
            *check_sections(records),
            *check_index_flags(records),
            *check_contacts(contacts or []),
            *check_known_404s(log),
            *(check_hours_stored(manifest, raw, contacts or []) if raw is not None else []),
        ]
    )


def counts_per_owner(records: list[dict]) -> dict[str, dict[str, int]]:
    out: dict[str, Counter] = {}
    for r in records:
        c = out.setdefault(f"{r['kind']}:{r['owner']}", Counter())
        c["pages"] += 1
        c["collected"] += r["status"] == "collected"
        c["http_200"] += r["http_status"] == 200
    return {k: dict(v) for k, v in sorted(out.items())}


def main() -> int:
    processed = ROOT / "data" / "processed"
    manifest = json.loads((processed / "pages_manifest.json").read_text(encoding="utf-8"))
    records = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((processed / "pages").rglob("*.json"))
    ]
    log_path = ROOT / "data" / "raw" / "fetch_log.jsonl"
    log = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line]
    contacts = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((processed / "contacts").glob("*.json"))
    ]
    raw = load_raw(manifest, ROOT / "data" / "raw")
    findings = run_page_checks(manifest, records, log, contacts, raw)
    for k, v in counts_per_owner(records).items():
        print(f"{k:28} {v}")
    for f in findings:
        label = "ACCEPTED" if f.accepted else f.severity.upper()
        extra = f" ({f.accepted})" if f.accepted else ""
        print(f"[{label}] {f.check} {f.course}: {f.message}{extra}")
    for url, reps in email_repairs(records).items():
        print(f"[REPAIRED] {url}: {reps}")
    unexpected = unexpected_failures(findings)
    accepted = sum(1 for f in findings if f.accepted)
    warnings = sum(f.severity == "warning" for f in findings)
    print(
        f"{len(records)} pages, {len(unexpected)} unexpected failures, "
        f"{accepted} accepted, {warnings} warnings"
    )
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
