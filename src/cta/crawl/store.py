"""Raw store under data/raw/ and the append-only fetch log."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit


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
