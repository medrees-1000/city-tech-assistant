"""Automatic web-page checks from docs/data-validation.md ("Web pages").

Run: uv run python -m cta.validate.pages
Pending manual items (not here): chair details vs the department PDF; refund pages show which
terms they cover.
"""

import json
import re
import sys
from collections import Counter
from urllib.parse import urlsplit

from cta.settings import ROOT
from cta.validate.findings import Finding

EMAIL_OK = re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$")
SPACED = re.compile(r"\S\s+@\w|\w@\s+\S")
PLACEHOLDER = re.compile(r"\{\{.*?\}\}")
CHAIR_FIELDS = ("name", "role", "room", "phone", "email")


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


def email_repairs(records: list[dict]) -> dict[str, list[dict]]:
    """Pages where an email address had to be repaired (for the validation log)."""
    return {r["source_url"]: r["email_repairs"] for r in records if r["email_repairs"]}


def run_page_checks(manifest: list[dict], records: list[dict], log: list[dict]) -> list[Finding]:
    return [
        *check_status(manifest),
        *check_redirects(manifest),
        *check_bodies(records),
        *check_hashes_and_log(manifest, log),
        *check_cleaned_text(records),
        *check_chairs(records),
    ]


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
    findings = run_page_checks(manifest, records, log)
    for k, v in counts_per_owner(records).items():
        print(f"{k:28} {v}")
    for f in findings:
        print(f"[{f.severity.upper()}] {f.check} {f.course}: {f.message}")
    for url, reps in email_repairs(records).items():
        print(f"[REPAIRED] {url}: {reps}")
    fails = sum(f.severity == "fail" for f in findings)
    print(f"{len(records)} pages, {fails} failures, {len(findings) - fails} warnings")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
