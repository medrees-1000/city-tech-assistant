"""Vector-only baseline retrieval: embed the question, return the k nearest chunks.

    uv run python -m cta.index.search "How do I apply for graduation?" -k 5

Exact cosine scan over all chunks: no index, no filters, no term or department logic (Phase 3).
Question embeddings are cached in data/cache/query_embeddings.json (speed and repeatable eval runs;
never answers). The key is a hash of the model name and the exact question, so the question text
itself is not stored, and another model never reuses old vectors.
"""

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from cta.index.db import connect
from cta.index.embed import ApiError, embed_texts, make_client
from cta.settings import ROOT, cost_usd, load_models

CACHE_PATH = ROOT / "data" / "cache" / "query_embeddings.json"
RESULT_COLUMNS = (
    "id", "kind", "source", "source_id", "merged_section_ids", "doc_type", "department", "term",
    "terms", "heading_path", "last_updated", "text",
)  # fmt: skip


@dataclass
class Search:
    results: list[dict]
    cache_hit: bool
    api_calls: int
    tokens: int
    cost: float
    question_key: str = field(repr=False, default="")


def cache_key(model: str, question: str) -> str:
    return hashlib.sha256(f"{model}\n{question}".encode()).hexdigest()


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


def query_vector(question: str, cfg: dict, client_factory, cache_path: Path):
    """(vector, tokens, api_calls, cache_hit)."""
    model, dims = cfg["embedding_model"], cfg["embedding_dimensions"]
    key = cache_key(model, question)
    cache = read_cache(cache_path)
    hit = cache.get(key)
    if isinstance(hit, list) and len(hit) == dims:
        return hit, 0, 0, True
    vectors, tokens = embed_texts(client_factory(), model, [question], dims)
    cache[key] = vectors[0]
    write_cache(cache_path, cache)
    return vectors[0], tokens, 1, False


def search(
    conn,
    question: str,
    k: int = 5,
    *,
    cfg: dict | None = None,
    client_factory=make_client,
    cache_path: Path = CACHE_PATH,
) -> Search:
    cfg = cfg or load_models()
    vector, tokens, calls, hit = query_vector(question, cfg, client_factory, cache_path)
    literal = "[" + ",".join(map(str, vector)) + "]"
    rows = conn.execute(
        f"SELECT {', '.join(RESULT_COLUMNS)}, 1 - (embedding <=> %s::vector) AS similarity "
        "FROM chunks WHERE embedding IS NOT NULL ORDER BY embedding <=> %s::vector, id LIMIT %s",
        (literal, literal, k),
    ).fetchall()
    results = [
        {"rank": n, "similarity": r[-1]} | dict(zip(RESULT_COLUMNS, r[:-1], strict=True))
        for n, r in enumerate(rows, 1)
    ]
    cost = cost_usd(cfg, cfg["embedding_model"], tokens)
    return Search(results, hit, calls, tokens, cost, cache_key(cfg["embedding_model"], question))


def format_result(r: dict) -> str:
    head = (
        f"{r['rank']:2}  {r['similarity']:.3f}  {r['id']}  [{r['doc_type']}]  {r['heading_path']}"
    )
    return head + "\n      " + r["text"][:200].replace("\n", " ")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m cta.index.search")
    parser.add_argument("question")
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args(argv[1:])
    try:
        with connect() as conn:
            found = search(conn, args.question, args.k)
    except ApiError as e:
        print(f"failed: {e}")
        return 1
    for r in found.results:
        print(format_result(r))
    source = "cache hit, no API call" if found.cache_hit else "embedded via the API"
    print(f"\nquery embedding: {source}; API calls: {found.api_calls}; tokens: {found.tokens}; "
          f"cost: ${found.cost:.7f}")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
