"""Search tests: fake embedding client, throwaway schema, hand-made 1536-number vectors."""

import json
import math

import pytest

from cta.index import search as srch
from cta.settings import load_models

CFG = load_models(env={"CTA_RERANK": "off"})  # the reranker has its own tests
DIM = CFG["embedding_dimensions"]


def vec(*head: float) -> list[float]:
    """A vector that starts with `head` and is zero elsewhere."""
    return list(head) + [0.0] * (DIM - len(head))


class FakeClient:
    def __init__(self, vector):
        self.vector, self.calls = vector, 0
        self.embeddings = self

    def create(self, model, input):
        self.calls += 1
        data = [type("D", (), {"index": 0, "embedding": self.vector})()]
        return type("R", (), {"data": data, "usage": type("U", (), {"total_tokens": 7})()})()


def factory(vector):
    client = FakeClient(vector)
    return client, (lambda: client)


# ---- cache (no database) ----


def test_cache_key_includes_the_model():
    assert srch.cache_key("model-a", "q") != srch.cache_key("model-b", "q")
    assert srch.cache_key("model-a", "q") == srch.cache_key("model-a", "q")
    assert "q" not in srch.cache_key("model-a", "q")  # a hash, not the question


def test_cache_hit_makes_no_client_call(tmp_path):
    path = tmp_path / "c.json"
    client, make = factory(vec(1.0))
    first = srch.query_vector("hello", CFG, make, path)
    second = srch.query_vector("hello", CFG, make, path)
    assert (first[2], first[3]) == (1, False) and (second[2], second[3]) == (0, True)
    assert client.calls == 1 and first[0] == second[0]


def test_other_model_does_not_reuse_the_vector(tmp_path):
    path = tmp_path / "c.json"
    client, make = factory(vec(1.0))
    srch.query_vector("hello", CFG, make, path)
    other = {**CFG, "embedding_model": "text-embedding-3-large", "embedding_dimensions": DIM}
    srch.query_vector("hello", other, make, path)
    assert client.calls == 2


@pytest.mark.parametrize("content", [None, "not json", "[1, 2]", '{"k": "bad"}', ""])
def test_missing_or_corrupt_cache_does_not_crash(tmp_path, content):
    path = tmp_path / "c.json"
    if content is not None:
        path.write_text(content)
    client, make = factory(vec(1.0))
    vector, _, calls, hit = srch.query_vector("hello", CFG, make, path)
    assert calls == 1 and not hit and len(vector) == DIM
    assert json.loads(path.read_text())  # rewritten as a valid cache


def test_wrong_size_cached_vector_is_ignored(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({srch.cache_key(CFG["embedding_model"], "hello"): [0.1, 0.2]}))
    client, make = factory(vec(1.0))
    assert srch.query_vector("hello", CFG, make, path)[3] is False


# ---- database: throwaway schema ----

CHUNKS = {  # id -> embedding; the query is vec(1, 0)
    "a": vec(1.0, 0.0),
    "b": vec(1.0, 1.0),
    "c": vec(0.0, 1.0),
    "d": vec(-1.0, 0.0),
}


@pytest.fixture
def loaded(conn):
    for cid, v in CHUNKS.items():
        conn.execute(
            "INSERT INTO chunks (id, kind, source, source_id, doc_type, scope, fetched_at, "
            "heading_path, text, content_hash, meta_hash, embedding, embedding_model) "
            "VALUES (%s, 'section', 'src', %s, 'faq', 'city_tech', 'x', %s, %s, 'h', 'm', %s, %s)",
            (cid, cid, f"Heading {cid}", f"text {cid}", v, CFG["embedding_model"]),
        )
    conn.commit()
    return conn


def run(conn, tmp_path, k=4):
    client, make = factory(vec(1.0, 0.0))
    return srch.search(conn, "q", k, cfg=CFG, client_factory=make, cache_path=tmp_path / "c.json")


@pytest.mark.integration
def test_ordered_by_similarity_with_values(loaded, tmp_path):
    found = run(loaded, tmp_path)
    assert [r["id"] for r in found.results] == ["a", "b", "c", "d"]
    assert [r["rank"] for r in found.results] == [1, 2, 3, 4]
    sims = [r["similarity"] for r in found.results]
    for got, want in zip(sims, [1.0, 1 / math.sqrt(2), 0.0, -1.0], strict=True):
        assert got == pytest.approx(want, abs=1e-6)
    assert sims == sorted(sims, reverse=True)


@pytest.mark.integration
def test_k_limits_results_and_carries_fields(loaded, tmp_path):
    found = run(loaded, tmp_path, k=2)
    assert len(found.results) == 2
    first = found.results[0]
    for field in srch.RESULT_COLUMNS + ("rank", "similarity"):
        assert field in first
    assert first["heading_path"] == "Heading a" and first["merged_section_ids"] == []


@pytest.mark.integration
def test_second_search_is_a_cache_hit_with_no_cost(loaded, tmp_path):
    first, second = run(loaded, tmp_path), run(loaded, tmp_path)
    assert (first.api_calls, first.cache_hit, first.tokens) == (1, False, 7)
    assert first.cost == pytest.approx(7 * 0.02 / 1_000_000)
    assert (second.api_calls, second.cache_hit, second.cost) == (0, True, 0.0)


@pytest.mark.integration
def test_search_changes_nothing(loaded, tmp_path):
    state = "SELECT count(*), max(updated_at) FROM chunks"
    real = "SELECT count(*), max(updated_at) FROM public.chunks"
    before = (loaded.execute(state).fetchone(), loaded.execute(real).fetchone())
    run(loaded, tmp_path)
    assert (loaded.execute(state).fetchone(), loaded.execute(real).fetchone()) == before
