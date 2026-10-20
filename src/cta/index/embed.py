"""Embedding client: batches, retries, dimension check, real token usage.

The API key is read by the OpenAI client from the environment (OPENAI_API_KEY, loaded from .env)
and is never printed or put in an error message."""

import json
import os
import time
from collections.abc import Callable
from contextvars import ContextVar
from pathlib import Path

import openai
from dotenv import load_dotenv

from cta.settings import ROOT

# ---- a small JSON file used as a cache: query embeddings, rerank scores, never answers ----
# (was jsoncache.py)

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


BATCH_SIZE = 64
MAX_RETRIES = 3  # retries after the first attempt; waits 1, 2, 4 seconds
# The API sets a smaller number for its own requests (guardrails.model_retries); the eval and the
# indexing never set it, so they keep MAX_RETRIES.
retry_limit: ContextVar[int] = ContextVar("retry_limit", default=MAX_RETRIES)


class ApiError(RuntimeError):
    pass


def make_client(timeout: float | None = None) -> openai.OpenAI:
    """A client with the library's own retries off: this module does the retrying. `timeout`
    (seconds per call) is set only by the API; None keeps the library's default (eval, indexing)."""
    load_dotenv(ROOT / ".env")
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise ApiError("OPENAI_API_KEY is not set; add it to .env")
    if timeout is None:
        return openai.OpenAI(max_retries=0)
    return openai.OpenAI(max_retries=0, timeout=timeout)


def retryable(error: Exception) -> bool:
    """Rate limits, server errors and dropped connections. A 400-class error (bad key, bad
    request) will not get better by waiting."""
    if isinstance(error, openai.RateLimitError | openai.APIConnectionError):
        return True
    return isinstance(error, openai.APIStatusError) and error.status_code >= 500


def with_retries(call, what: str, sleep: Callable[[float], None] = time.sleep):
    """Run call(); retry retryable errors up to MAX_RETRIES times (waits 1, 2, 4 seconds). Other
    errors, such as a bad key, fail at once. Error messages never contain the key."""
    limit = retry_limit.get()
    for attempt in range(limit + 1):
        try:
            return call()
        except openai.OpenAIError as e:
            if not retryable(e):
                status = getattr(e, "status_code", None)
                raise ApiError(
                    f"{what} rejected ({type(e).__name__}, status {status}); not retrying"
                ) from None
            if attempt == limit:
                raise ApiError(
                    f"{what} failed after {limit} retries ({type(e).__name__})"
                ) from None
            sleep(2**attempt)


def embed_batch(client, model: str, texts: list[str], sleep: Callable[[float], None]):
    return with_retries(
        lambda: client.embeddings.create(model=model, input=texts), "embedding request", sleep
    )


def embed_texts(
    client,
    model: str,
    texts: list[str],
    dimensions: int,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[list[list[float]], int]:
    """(one vector per text, in order; tokens the API reports). Every vector must have
    `dimensions` numbers."""
    vectors: list[list[float]] = []
    tokens = 0
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]
        response = embed_batch(client, model, batch, sleep)
        rows = sorted(response.data, key=lambda d: d.index)
        if len(rows) != len(batch):
            raise ApiError(f"asked for {len(batch)} embeddings, got {len(rows)}")
        for row in rows:
            if len(row.embedding) != dimensions:
                raise ApiError(
                    f"embedding has {len(row.embedding)} dimensions, expected {dimensions}"
                )
            vectors.append(list(row.embedding))
        tokens += response.usage.total_tokens
    return vectors, tokens
