"""Parse every crawled page into data/processed/pages/<owner>/<slug>.json.

Run: uv run python -m cta.parse.pages
Reads data/processed/pages_manifest.json and the raw HTML. No network.
"""

import json
import re
from collections import Counter
from fnmatch import fnmatchcase
from pathlib import Path
from urllib.parse import urlsplit

from cta.parse.html import not_collected, parse_page
from cta.parse.terms import covered_terms, tag_terms
from cta.settings import ROOT, load_sources


def slug_of(url: str) -> str:
    last = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    return last.removesuffix(".aspx") if "." in last else "index"


def doc_type_for(url: str, rules: list[dict] | None) -> str | None:
    """The doc_type of the first rule whose pattern matches the URL path (None if none does)."""
    path = urlsplit(url).path
    return next((r["doc_type"] for r in rules or [] if fnmatchcase(path, r["path"])), None)


def record_for(
    entry: dict,
    raw_root: Path,
    no_index: dict[str, str] | None = None,
    metadata: dict[str, dict] | None = None,
    doc_rules: list[dict] | None = None,
    refund_pages: list[str] | None = None,
) -> dict:
    """One manifest entry -> one page record. owner/kind come from the manifest.

    no_index maps a URL to the reason the page is kept but not indexed (index: false).
    metadata maps a URL to extra fields for the record (doc_type, note)."""
    meta = {
        "source_url": entry["url"],
        "final_url": entry["final_url"],
        "fetched_at": entry["fetched_at"],
        "content_hash": entry["content_hash"],
        "http_status": entry["status"],
        "kind": entry["kind"],
        "owner": entry["owner"],
    }
    if entry["status"] != 200:
        reason = f"http {entry['status']}" if entry["status"] else f"not fetched: {entry['error']}"
        rec = not_collected(meta, reason)
    else:
        rec = parse_page((raw_root / entry["saved_as"]).read_bytes(), meta)
    if entry["url"] in (no_index or {}):
        rec["index"] = False
        rec["index_reason"] = no_index[entry["url"]]
    is_dept = entry["kind"] == "department"
    rec["doc_type"] = doc_type_for(entry["url"], doc_rules)  # null if no rule covers the page
    rec["department"] = entry["owner"] if is_dept else None  # null for central offices
    rec["scope"] = "department" if is_dept else "city_tech"
    rec["term"] = None  # web pages print no term
    rec["last_updated"] = None  # nor a last-updated date
    rec.update((metadata or {}).get(entry["url"], {}))
    tag_terms(rec)
    if entry["url"] in (refund_pages or []):
        rec.update(covered_terms(rec))  # what the page names; nothing is assumed
    return rec


def merge_manifest(path: Path, results: list[dict]) -> list[dict]:
    """Add or replace manifest entries by URL (used when a few pages are fetched later)."""
    manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    by_url = {e["url"]: e for e in manifest}
    for r in results:
        by_url[r["url"]] = r
    merged = list(by_url.values())
    path.write_text(json.dumps(merged, indent=1), encoding="utf-8")
    return merged


def panel_list(contact: dict) -> list[dict]:
    return [{"heading": p["heading"], "markdown": p["markdown"]} for p in contact["panels"]]


HOURS_HEADING = re.compile(r"^[A-Z0-9 &/-]*HOURS$")  # "IN-PERSON HOURS", "WEB-LAB HOURS"


def hours_part(markdown: str) -> str | None:
    """The hours inside a CONTACT US panel: from the first "... HOURS" line to the last table (the
    hours are in tables), as printed. What follows (the FAFSA and TAP school codes) is not hours."""
    blocks = markdown.split("\n\n")
    start = next((i for i, b in enumerate(blocks) if HOURS_HEADING.match(b)), None)
    if start is None:
        return None
    tables = [i for i in range(start, len(blocks)) if blocks[i].startswith("|")]
    end = tables[-1] + 1 if tables else len(blocks)
    return "\n\n".join(blocks[start:end])


def hours_entries(panels: list[dict]) -> list[dict]:
    """Hours as printed: every panel with HOURS in its heading, and the hours part of CONTACT US.
    Not typo-fixed. embed false like the rest of the contact data."""
    out = []
    for p in panels:
        if "hours" in p["heading"].lower():
            out.append({"heading": p["heading"], "markdown": p["markdown"], "where": "panel",
                        "embed": False})  # fmt: skip
        elif p["heading"].lower() == "contact us" and (md := hours_part(p["markdown"])):
            out.append({"heading": f"{p['heading']} (hours part)", "markdown": md,
                        "where": "inside the CONTACT US panel", "embed": False})  # fmt: skip
    return out


def build_contacts(records: list[dict]) -> dict[str, dict]:
    """One contact record per owner from the collected pages' contact panels.

    If the panels are identical on every page the record has one set of panels. If they differ,
    the most common set is used and every variant is listed with its pages (nothing is guessed)."""
    variants: dict[str, dict[str, dict]] = {}
    for r in records:
        if r["status"] != "collected" or not r["contact"]["panels"]:
            continue
        key = json.dumps([(p["heading"], p["markdown"]) for p in r["contact"]["panels"]])
        v = variants.setdefault(r["owner"], {}).setdefault(
            key, {"contact": r["contact"], "pages": []}
        )
        v["pages"].append(r["source_url"])
    contacts = {}
    for owner, by_key in sorted(variants.items()):
        ranked = sorted(by_key.values(), key=lambda v: -len(v["pages"]))
        best = ranked[0]
        pages = [r for r in records if r["owner"] == owner and r["source_url"] in best["pages"]]
        contacts[owner] = {
            "owner": owner,
            "kind": pages[0]["kind"],
            "panels": panel_list(best["contact"]),
            "emails": best["contact"]["emails"],
            "phones": best["contact"]["phones"],
            "hours": hours_entries(panel_list(best["contact"])),
            "source_pages": best["pages"],
            "fetched_at": max(r["fetched_at"] for r in pages),
            "consistent": len(ranked) == 1,
        }
        if len(ranked) > 1:
            contacts[owner]["variants"] = [
                {"panels": panel_list(v["contact"]), "pages": v["pages"]} for v in ranked
            ]
    return contacts


def build_pages(
    manifest: list[dict],
    raw_root: Path,
    out_dir: Path,
    no_index: dict[str, str] | None = None,
    metadata: dict[str, dict] | None = None,
    doc_rules: list[dict] | None = None,
    refund_pages: list[str] | None = None,
) -> list[dict]:
    records = []
    for entry in manifest:
        rec = record_for(entry, raw_root, no_index, metadata, doc_rules, refund_pages)
        path = out_dir / "pages" / rec["owner"] / f"{slug_of(rec['source_url'])}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
        records.append(rec)
    for owner, contact in build_contacts(records).items():
        path = out_dir / "contacts" / f"{owner}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(contact, indent=1, ensure_ascii=False), encoding="utf-8")
    return records


def main() -> None:
    processed = ROOT / "data" / "processed"
    manifest = json.loads((processed / "pages_manifest.json").read_text(encoding="utf-8"))
    sources = load_sources()
    no_index = sources.get("no_index_pages", {})
    records = build_pages(
        manifest,
        ROOT / "data" / "raw",
        processed,
        no_index,
        sources.get("page_metadata", {}),
        sources.get("page_doc_types", []),
        sources.get("refund_pages", []),
    )
    collected = sum(r["status"] == "collected" for r in records)
    indexed = sum(r["index"] for r in records)
    print(f"{len(records)} pages parsed, {collected} collected, {indexed} to index")
    print("by status:", dict(Counter((r["status"], r["index"]) for r in records)))


if __name__ == "__main__":
    main()
