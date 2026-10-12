"""Retrieval: embed the question, return the k best chunks.

    uv run python -m cta.index.search "How do I apply for graduation?" -k 5 [--mode hybrid]

Two modes (config `retrieval.mode`, default vector = the frozen baseline):
- vector: exact cosine scan over all chunks, no filters.
- hybrid (Phase 3, step 1, rejected, off): the vector top N plus the Postgres ts_rank keyword top N.
- hybrid_bm25 (step 1b): the vector top N plus the BM25 top N (cta.index.bm25), same fusion.
  Fusion is reciprocal rank fusion; then the top k. No filters in any mode.
Question embeddings are cached in data/cache/query_embeddings.json (speed and repeatable eval runs;
never answers). The key is a hash of the model name and the exact question, so the question text
itself is not stored, and another model never reuses old vectors.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from cta.index import bm25
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
    mode_used: str = "vector"  # "hybrid", "vector", or "vector (empty keyword query)"
    top_vector_similarity: float | None = None  # best cosine similarity in the vector list
    retrieval_ms: float = 0.0  # the whole search call, including the query embedding if not cached


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


def rrf(
    vector_ids: list[str],
    keyword_ids: list[str],
    k: int = 60,
    keyword_name: str = "keyword_rank",
) -> list[dict]:
    """Reciprocal rank fusion: score = sum over the lists of 1 / (k + rank), ranks from 1. A chunk
    in both lists gets both terms. Best score first; ties break by id."""
    scores: dict[str, dict] = {}
    for name, ids in (("vector_rank", vector_ids), (keyword_name, keyword_ids)):
        for rank, cid in enumerate(ids, 1):
            entry = scores.setdefault(
                cid,
                {
                    "id": cid,
                    "rrf_score": 0.0,
                    "vector_rank": None,
                    "keyword_rank": None,
                    "bm25_rank": None,
                },
            )
            entry[name] = rank
            entry["rrf_score"] += 1.0 / (k + rank)
    return sorted(scores.values(), key=lambda e: (-e["rrf_score"], e["id"]))


def tsquery_text(lexemes: list[str]) -> str:
    """An OR query over already-normalised lexemes, each quoted so no character in it is syntax."""
    quoted = ["'" + lex.replace("\\", "\\\\").replace("'", "''") + "'" for lex in lexemes]
    return " | ".join(quoted)


def keyword_lexemes(conn, question: str) -> list[str]:
    """The question's lexemes under the same 'english' configuration as the index (stop words
    dropped, ordinary words stemmed, codes such as EET 3672 or MAT 1275CO kept)."""
    rows = conn.execute(
        "SELECT lexeme FROM unnest(to_tsvector('english', %s)) ORDER BY lexeme", (question,)
    )
    return [r[0] for r in rows]


def keyword_ids(conn, query: str, limit: int) -> list[str]:
    """Chunk ids matching any lexeme, best ts_rank first, ties by id. ts_rank counts how often and
    where the query words occur in a chunk; it does not weigh rare words more than common ones (no
    inverse document frequency), so "student" counts as much as "3672", and it does not normalise by
    chunk length."""
    rows = conn.execute(
        "SELECT id FROM chunks WHERE tsv @@ to_tsquery('simple', %s) "
        "ORDER BY ts_rank(tsv, to_tsquery('simple', %s)) DESC, id LIMIT %s",
        (query, query, limit),
    )
    return [r[0] for r in rows]


def row_dict(row, rank: int) -> dict:
    return {"rank": rank, "similarity": row[-1]} | dict(zip(RESULT_COLUMNS, row[:-1], strict=True))


def search(
    conn,
    question: str,
    k: int = 5,
    *,
    cfg: dict | None = None,
    client_factory=make_client,
    cache_path: Path = CACHE_PATH,
    mode: str | None = None,
) -> Search:
    started = time.perf_counter()
    cfg = cfg or load_models()
    mode = mode or cfg["retrieval"]["mode"]
    n = cfg["retrieval"]["candidates"]
    vector, tokens, calls, hit = query_vector(question, cfg, client_factory, cache_path)
    literal = "[" + ",".join(map(str, vector)) + "]"
    columns = ", ".join(RESULT_COLUMNS)
    select = f"SELECT {columns}, 1 - (embedding <=> %s::vector) AS similarity FROM chunks"
    used, query, lexemes = "vector", "", []
    if mode == "hybrid":
        lexemes = keyword_lexemes(conn, question)
        query = tsquery_text(lexemes)
    elif mode == "hybrid_bm25":
        lexemes = bm25.query_lexemes(conn, question)
    if mode in ("hybrid", "hybrid_bm25"):
        used = mode if lexemes else "vector (empty keyword query)"
    fused_mode = used in ("hybrid", "hybrid_bm25")
    rows = conn.execute(
        f"{select} WHERE embedding IS NOT NULL ORDER BY embedding <=> %s::vector, id LIMIT %s",
        (literal, literal, n if fused_mode else k),
    ).fetchall()
    top_similarity = rows[0][-1] if rows else None
    if not fused_mode:
        results = [
            row_dict(r, i) | {"vector_rank": i, "keyword_rank": None, "bm25_rank": None}
            for i, r in enumerate(rows, 1)
        ]
    else:
        by_id = {r[0]: r for r in rows}
        if used == "hybrid":
            keyword, name = keyword_ids(conn, query, n), "keyword_rank"
        else:
            keyword, name = bm25.bm25_ids(conn, lexemes, n), "bm25_rank"
        fused = rrf([r[0] for r in rows], keyword, cfg["retrieval"]["rrf_k"], name)[:k]
        missing = [e["id"] for e in fused if e["id"] not in by_id]
        if missing:  # keyword-only hits: fetch them with their cosine similarity
            extra = conn.execute(f"{select} WHERE id = ANY(%s)", (literal, missing)).fetchall()
            by_id |= {r[0]: r for r in extra}
        results = [
            row_dict(by_id[e["id"]], i) | e | {"id": e["id"]} for i, e in enumerate(fused, 1)
        ]
    cost = cost_usd(cfg, cfg["embedding_model"], tokens)
    return Search(
        results, hit, calls, tokens, cost, cache_key(cfg["embedding_model"], question),
        mode_used=used, top_vector_similarity=top_similarity,
        retrieval_ms=(time.perf_counter() - started) * 1000,
    )  # fmt: skip


def format_result(r: dict) -> str:
    head = (
        f"{r['rank']:2}  {r['similarity']:.3f}  {r['id']}  [{r['doc_type']}]  {r['heading_path']}"
    )
    return head + "\n      " + r["text"][:200].replace("\n", " ")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m cta.index.search")
    parser.add_argument("question")
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument(
        "--mode", choices=("vector", "hybrid", "hybrid_bm25"), help="override retrieval.mode"
    )
    args = parser.parse_args(argv[1:])
    try:
        with connect() as conn:
            found = search(conn, args.question, args.k, mode=args.mode)
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
