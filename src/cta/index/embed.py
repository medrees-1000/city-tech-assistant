"""Embedding client: batches, retries, dimension check, real token usage.

The API key is read by the OpenAI client from the environment (OPENAI_API_KEY, loaded from .env)
and is never printed or put in an error message.
"""

import os
import time
from collections.abc import Callable

import openai
from dotenv import load_dotenv

from cta.settings import ROOT

BATCH_SIZE = 64
MAX_RETRIES = 3  # retries after the first attempt; waits 1, 2, 4 seconds


class ApiError(RuntimeError):
    pass


def make_client() -> openai.OpenAI:
    """A client with the library's own retries off: this module does the retrying."""
    load_dotenv(ROOT / ".env")
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise ApiError("OPENAI_API_KEY is not set; add it to .env")
    return openai.OpenAI(max_retries=0)


def retryable(error: Exception) -> bool:
    """Rate limits, server errors and dropped connections. A 400-class error (bad key, bad
    request) will not get better by waiting."""
    if isinstance(error, openai.RateLimitError | openai.APIConnectionError):
        return True
    return isinstance(error, openai.APIStatusError) and error.status_code >= 500


def with_retries(call, what: str, sleep: Callable[[float], None] = time.sleep):
    """Run call(); retry retryable errors up to MAX_RETRIES times (waits 1, 2, 4 seconds). Other
    errors, such as a bad key, fail at once. Error messages never contain the key."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            return call()
        except openai.OpenAIError as e:
            if not retryable(e):
                status = getattr(e, "status_code", None)
                raise ApiError(
                    f"{what} rejected ({type(e).__name__}, status {status}); not retrying"
                ) from None
            if attempt == MAX_RETRIES:
                raise ApiError(
                    f"{what} failed after {MAX_RETRIES} retries ({type(e).__name__})"
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
