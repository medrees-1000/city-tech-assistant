"""Retrieval: embed the question, return the k best chunks.

    uv run python -m cta.index.search "How do I apply for graduation?" -k 5 [--rerank pool_a]

Vector search: exact cosine scan over all chunks, no filters. With `retrieval.rerank` set to pool_a
(the production setting) a model then reorders the 20 best chunks (cta.index.rerank). The keyword
(hybrid, BM25) variants and the department filter were rejected experiments and were removed in the
cleanup of Oct 19, 2026; they are reproducible at git tag pre-cleanup.
Question embeddings are cached in data/cache/query_embeddings.json (speed and repeatable eval runs;
never answers). The key is a hash of the model name and the exact question, so the question text
itself is not stored, and another model never reuses old vectors.
"""

import argparse
import dataclasses
import hashlib
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from cta.index import rerank as reranker
from cta.index.db import connect
from cta.index.embed import ApiError, embed_texts, make_client
from cta.index.jsoncache import read_cache, write_cache
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
    top_vector_similarity: float | None = None  # best cosine similarity in the vector list
    retrieval_ms: float = 0.0  # the whole search call, including the query embedding if not cached
    rerank_mode: str = "off"
    rerank: reranker.Rerank | None = None  # the reranker's outcome, when it ran
    pool: list[dict] = field(default_factory=list, repr=False)  # the candidates it scored

    @property
    def total_cost(self) -> float:
        """Query embedding plus reranker calls."""
        return self.cost + (self.rerank.cost if self.rerank else 0.0)


def cache_key(model: str, question: str) -> str:
    return hashlib.sha256(f"{model}\n{question}".encode()).hexdigest()


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
    rerank: str | None = None,
    rerank_limit: float | None = None,
) -> Search:
    started = time.perf_counter()
    cfg = cfg or load_models()
    rerank = rerank or cfg["retrieval"]["rerank"]
    if rerank != "off":
        return search_reranked(
            conn, question, k, rerank, cfg, client_factory, cache_path, rerank_limit, started
        )
    vector, tokens, calls, hit = query_vector(question, cfg, client_factory, cache_path)
    literal = "[" + ",".join(map(str, vector)) + "]"
    columns = ", ".join(RESULT_COLUMNS)
    rows = conn.execute(
        f"SELECT {columns}, 1 - (embedding <=> %s::vector) AS similarity FROM chunks "
        "WHERE embedding IS NOT NULL ORDER BY embedding <=> %s::vector, id LIMIT %s",
        (literal, literal, k),
    ).fetchall()
    # The abstain threshold reads this value: the best vector cosine similarity.
    top_similarity = rows[0][-1] if rows else None
    cost = cost_usd(cfg, cfg["embedding_model"], tokens)
    return Search(
        [row_dict(r, i) for i, r in enumerate(rows, 1)], hit, calls, tokens, cost,
        cache_key(cfg["embedding_model"], question), top_vector_similarity=top_similarity,
        retrieval_ms=(time.perf_counter() - started) * 1000,
    )  # fmt: skip


def search_reranked(
    conn, question, k, rerank, cfg, client_factory, cache_path, rerank_limit, started
) -> Search:
    """Step 3: fetch the pool of the chosen variant, let the reranker order it, keep the top k.
    The abstain threshold (Search.top_vector_similarity) is the first stage's best vector cosine
    similarity, kept as it is: rerank scores are 0 to 10 judgements, not similarities, and the
    threshold was chosen on cosine values."""
    pool = reranker.POOLS[rerank]
    first = search(
        conn, question, pool["size"], cfg=cfg, client_factory=client_factory,
        cache_path=cache_path, rerank="off",
    )  # fmt: skip
    outcome = reranker.rerank(
        question, first.results, cfg, client_factory=client_factory, max_cost=rerank_limit,
        cache_path=Path(cfg["rerank"].get("cache_path") or cache_path.with_name("rerank.json")),
    )  # fmt: skip
    results = [
        first.results[i] | {"rank": new_rank, "first_stage_rank": first.results[i]["rank"]}
        for new_rank, i in enumerate(outcome.order[:k], 1)
    ]
    return dataclasses.replace(
        first, results=results, rerank_mode=rerank, rerank=outcome, pool=first.results,
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
        "--rerank", choices=("off", "pool_a"), help="override retrieval.rerank"
    )
    args = parser.parse_args(argv[1:])
    try:
        with connect() as conn:
            found = search(
                conn,
                args.question,
                args.k,
                rerank=args.rerank,
            )
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
