"""Parse every crawled page into data/processed/pages/<owner>/<slug>.json.

Run: uv run python -m cta.parse.pages
Reads data/processed/pages_manifest.json and the raw HTML. No network.
"""

import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from cta.parse.html import not_collected, parse_page
from cta.settings import ROOT, load_sources


def slug_of(url: str) -> str:
    last = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    return last.removesuffix(".aspx") if "." in last else "index"


def record_for(entry: dict, raw_root: Path, no_index: dict[str, str] | None = None) -> dict:
    """One manifest entry -> one page record. owner/kind come from the manifest.

    no_index maps a URL to the reason the page is kept but not indexed (index: false)."""
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
    manifest: list[dict], raw_root: Path, out_dir: Path, no_index: dict[str, str] | None = None
) -> list[dict]:
    records = []
    for entry in manifest:
        rec = record_for(entry, raw_root, no_index)
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
    no_index = load_sources().get("no_index_pages", {})
    records = build_pages(manifest, ROOT / "data" / "raw", processed, no_index)
    collected = sum(r["status"] == "collected" for r in records)
    indexed = sum(r["index"] for r in records)
    print(f"{len(records)} pages parsed, {collected} collected, {indexed} to index")
    print("by status:", dict(Counter((r["status"], r["index"]) for r in records)))


if __name__ == "__main__":
    main()
