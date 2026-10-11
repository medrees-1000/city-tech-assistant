"""Parse every crawled page into data/processed/pages/<owner>/<slug>.json.

Run: uv run python -m cta.parse.pages
Reads data/processed/pages_manifest.json and the raw HTML. No network.
"""

import json
from pathlib import Path
from urllib.parse import urlsplit

from cta.parse.html import not_collected, parse_page
from cta.settings import ROOT


def slug_of(url: str) -> str:
    last = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    return last.removesuffix(".aspx") if "." in last else "index"


def record_for(entry: dict, raw_root: Path) -> dict:
    """One manifest entry -> one page record. owner/kind come from the manifest."""
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
        return not_collected(meta, reason)
    return parse_page((raw_root / entry["saved_as"]).read_bytes(), meta)


def build_pages(manifest: list[dict], raw_root: Path, out_dir: Path) -> list[dict]:
    records = []
    for entry in manifest:
        rec = record_for(entry, raw_root)
        path = out_dir / "pages" / rec["owner"] / f"{slug_of(rec['source_url'])}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
        records.append(rec)
    return records


def main() -> None:
    processed = ROOT / "data" / "processed"
    manifest = json.loads((processed / "pages_manifest.json").read_text(encoding="utf-8"))
    records = build_pages(manifest, ROOT / "data" / "raw", processed)
    collected = sum(r["status"] == "collected" for r in records)
    print(f"{len(records)} pages parsed, {collected} collected")


if __name__ == "__main__":
    main()
