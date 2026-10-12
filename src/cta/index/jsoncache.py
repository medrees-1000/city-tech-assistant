"""A small JSON file used as a cache (query embeddings, rerank scores). Never holds answers."""

import json
import os
from pathlib import Path


def read_cache(path: Path) -> dict:
    """The cache as a dict; a missing, unreadable or corrupt file is an empty cache."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_cache(path: Path, cache: dict) -> None:
    """Write through a temporary file so an interrupted write cannot corrupt the cache."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass  # the cache is only a speed-up
