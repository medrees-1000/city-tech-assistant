"""Embedding client and loader tests. No network, and the real `chunks` table is never touched:
database tests run in a throwaway schema that is dropped afterwards."""

import hashlib
import random
from types import SimpleNamespace

import httpx2
import openai
import pytest

from cta.index import chunks as ch
from cta.index import embed, load
from cta.settings import load_models
from tests.helpers import PROCESSED_FIXTURES as FIXTURES
from tests.helpers import words

CFG = load_models(env={})
DIM = CFG["embedding_dimensions"]


def vector_for(text: str, dim: int = DIM) -> list[float]:
    rng = random.Random(hashlib.sha256(text.encode()).hexdigest())
    return [rng.uniform(-1, 1) for _ in range(dim)]


class FakeClient:
    """Stands in for openai.OpenAI: deterministic vectors, counts calls, can fail first."""

    def __init__(self, dim: int = DIM, errors: list[Exception] | None = None):
        self.dim, self.errors, self.calls, self.texts = dim, list(errors or []), 0, []
        self.embeddings = SimpleNamespace(create=self.create)

    def create(self, model, input):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        self.texts += input
        data = [
            SimpleNamespace(index=i, embedding=vector_for(t, self.dim)) for i, t in enumerate(input)
        ]
        return SimpleNamespace(data=data, usage=SimpleNamespace(total_tokens=sum(map(len, input))))


def api_error(cls, status: int):
    request = httpx2.Request("POST", "https://api.openai.com/v1/embeddings")
    return cls("boom", response=httpx2.Response(status, request=request), body=None)


# ---- embed.py ----


def test_batches_of_64():
    client = FakeClient()
    vectors, tokens = embed.embed_texts(client, "m", [f"t{i}" for i in range(130)], DIM)
    assert client.calls == 3 and len(vectors) == 130 and tokens > 0


def test_wrong_dimension_fails():
    with pytest.raises(embed.ApiError, match="3 dimensions, expected 1536"):
        embed.embed_texts(FakeClient(dim=3), "m", ["a"], DIM)


def test_retries_on_429_then_succeeds():
    client = FakeClient(errors=[api_error(openai.RateLimitError, 429)] * 2)
    waits = []
    vectors, _ = embed.embed_texts(client, "m", ["a"], DIM, sleep=waits.append)
    assert client.calls == 3 and waits == [1, 2] and len(vectors) == 1


def test_gives_up_after_three_retries():
    client = FakeClient(errors=[api_error(openai.InternalServerError, 503)] * 9)
    with pytest.raises(embed.ApiError, match="after 3 retries"):
        embed.embed_texts(client, "m", ["a"], DIM, sleep=lambda s: None)
    assert client.calls == 4


def test_no_retry_on_bad_key():
    client = FakeClient(errors=[api_error(openai.AuthenticationError, 401)])
    with pytest.raises(embed.ApiError, match="not retrying") as e:
        embed.embed_texts(client, "m", ["a"], DIM, sleep=lambda s: None)
    assert client.calls == 1 and "sk-" not in str(e.value)


# ---- make_plan (pure) ----


def row(c, model="text-embedding-3-small"):
    return (c["content_hash"], c["meta_hash"], model)


def test_make_plan_classifies():
    cs = ch.build_chunks(FIXTURES, CFG, words)
    existing = {c["id"]: row(c) for c in cs}
    existing[cs[0]["id"]] = ("old", cs[0]["meta_hash"], "text-embedding-3-small")
    existing[cs[1]["id"]] = (cs[1]["content_hash"], "old", "text-embedding-3-small")
    del existing[cs[2]["id"]]
    existing["gone"] = ("x", "y", "z")
    plan = load.make_plan(cs, existing, "text-embedding-3-small")
    assert [len(plan.new), len(plan.changed), len(plan.meta_only), len(plan.stale)] == [1, 1, 1, 1]
    assert len(plan.unchanged) == len(cs) - 3


def test_other_embedding_model_counts_as_changed():
    cs = ch.build_chunks(FIXTURES, CFG, words)
    plan = load.make_plan(cs, {c["id"]: row(c, "old-model") for c in cs}, "text-embedding-3-small")
    assert len(plan.changed) == len(cs)


# ---- database: throwaway schema ----


def go(conn, chunks, client, *, yes=True, cfg=CFG, validate=lambda: True):
    lines: list[str] = []
    code = load.run(conn, chunks, cfg, words, lambda: client, yes, False, validate, lines.append)
    return code, "\n".join(lines)


def built():
    return ch.build_chunks(FIXTURES, CFG, words)


@pytest.mark.integration
def test_first_load_embeds_everything_second_embeds_nothing(conn):
    cs = built()
    client = FakeClient()
    code, text = go(conn, cs, client)
    assert code == 0 and len(client.texts) == len(cs)
    assert f"rows in chunks: {len(cs)}; rows with NULL embedding: 0" in text
    assert "(OK)" in text
    again = FakeClient()
    go(conn, cs, again)
    assert again.calls == 0


@pytest.mark.integration
def test_real_table_is_not_touched(conn):
    real = "SELECT count(*), max(updated_at) FROM public.chunks"
    before = conn.execute(real).fetchone()
    go(conn, built(), FakeClient())
    assert conn.execute(real).fetchone() == before


@pytest.mark.integration
def test_one_changed_chunk_reembeds_only_that_chunk(conn):
    cs = built()
    go(conn, cs, FakeClient())
    cs2 = built()
    cs2[0]["text"] += " edited"
    cs2[0] = ch.finish(cs2[0], CFG["embedding_model"], DIM)
    client = FakeClient()
    go(conn, cs2, client)
    assert client.texts == [cs2[0]["text"]]


@pytest.mark.integration
def test_metadata_only_change_makes_no_api_call(conn):
    cs = built()
    go(conn, cs, FakeClient())
    cs2 = built()
    cs2[0]["last_updated"] = "2026-01-01"
    cs2[0] = ch.finish(cs2[0], CFG["embedding_model"], DIM)
    client = FakeClient()
    go(conn, cs2, client)
    assert client.calls == 0
    got = conn.execute("SELECT last_updated FROM chunks WHERE id = %s", (cs2[0]["id"],)).fetchone()
    assert got[0] == "2026-01-01"


@pytest.mark.integration
def test_model_change_reembeds_all(conn):
    cs = built()
    go(conn, cs, FakeClient())
    conn.execute("UPDATE chunks SET embedding_model = 'older-model'")
    client = FakeClient()
    go(conn, cs, client)
    assert len(client.texts) == len(cs)


@pytest.mark.integration
def test_stale_rows_are_removed(conn):
    cs = built()
    go(conn, cs, FakeClient())
    go(conn, cs[1:], FakeClient())
    assert conn.execute("SELECT count(*) FROM chunks").fetchone()[0] == len(cs) - 1


@pytest.mark.integration
def test_without_yes_nothing_changes(conn):
    client = FakeClient()
    code, text = go(conn, built(), client, yes=False)
    assert code == 0 and client.calls == 0 and "run again with --yes" in text
    assert conn.execute("SELECT count(*) FROM chunks").fetchone()[0] == 0


@pytest.mark.integration
def test_cost_cap_stops_before_the_api(conn):
    cfg = {**CFG, "eval": {**CFG["eval"], "max_cost_usd": 0.0}}
    client = FakeClient()
    code, text = go(conn, built(), client, cfg=cfg)
    assert code == 1 and client.calls == 0 and "above eval.max_cost_usd" in text


@pytest.mark.integration
def test_failed_validation_refuses(conn):
    client = FakeClient()
    code, text = go(conn, built(), client, validate=lambda: False)
    assert code == 1 and client.calls == 0 and "cta.validate" in text


@pytest.mark.integration
def test_failure_midway_leaves_table_as_it_was(conn):
    cs = built()
    go(conn, cs, FakeClient())
    plan = load.make_plan(cs, {}, "m")  # pretend all are new: the second insert will be bad
    bad = [dict(c) for c in plan.new]
    bad[1]["kind"] = None  # NOT NULL violation
    plan.new = bad
    with pytest.raises(Exception):  # noqa: B017
        load.apply_plan(conn, plan, [vector_for("x")] * len(bad), CFG)
    conn.rollback()
    assert conn.execute("SELECT count(*) FROM chunks").fetchone()[0] == len(cs)
