"""BM25 keyword side (Phase 3, step 1b): pure scoring on hand-made chunks, and the database."""

import copy
import math
from datetime import date

import pytest

from cta import answer as ans_mod
from cta.index import bm25
from cta.index import search as srch
from cta.settings import load_models
from tests.test_answer import FakeChatClient, add_chunk
from tests.test_hybrid import add_world
from tests.test_search import vec

CFG = load_models(env={})


def rows(**docs):
    """(chunk id, lexeme, tf) rows from {id: {lexeme: tf}}."""
    return [(cid, lex, tf) for cid, terms in docs.items() for lex, tf in terms.items()]


def test_constants_are_the_pre_registered_ones():
    assert (bm25.K1, bm25.B) == (1.2, 0.75)


def test_idf_is_higher_for_a_rare_lexeme():
    index = bm25.build_index(rows(a={"rare": 1, "common": 1}, b={"common": 1}, c={"common": 1},
                                  d={"common": 1}))  # fmt: skip
    assert index.idf("rare") == pytest.approx(math.log(1 + (4 - 1 + 0.5) / (1 + 0.5)))
    assert index.idf("common") == pytest.approx(math.log(1 + (4 - 4 + 0.5) / (4 + 0.5)))
    assert index.idf("rare") > index.idf("common") > 0
    assert index.idf("missing") == pytest.approx(math.log(1 + (4 + 0.5) / 0.5))  # df = 0


def test_score_matches_the_formula_by_hand():
    index = bm25.build_index(rows(a={"zebra": 2, "pad": 8}, b={"pad": 10}))
    avg = (10 + 10) / 2
    expected = index.idf("zebra") * 2 * (1.2 + 1) / (2 + 1.2 * (1 - 0.75 + 0.75 * 10 / avg))
    ((cid, score),) = index.search(["zebra"], 5)  # noqa: E999
    assert cid == "a" and score == pytest.approx(expected)


def test_a_longer_chunk_scores_lower_for_the_same_term_frequency():
    index = bm25.build_index(rows(short={"zebra": 1, "pad": 9}, long={"zebra": 1, "pad": 99}))
    ranked = index.search(["zebra"], 5)
    assert [c for c, _ in ranked] == ["short", "long"] and ranked[0][1] > ranked[1][1]


def test_term_frequency_saturates():
    index = bm25.build_index(rows(one={"zebra": 1, "pad": 19}, five={"zebra": 5, "pad": 15},
                                  ten={"zebra": 10, "pad": 10}))  # fmt: skip
    s = dict(index.search(["zebra"], 5))
    assert s["one"] < s["five"] < s["ten"] and (s["ten"] - s["five"]) < (s["five"] - s["one"])


def test_ties_break_by_id_and_limit_applies():
    index = bm25.build_index(rows(b={"zebra": 1, "pad": 4}, a={"zebra": 1, "pad": 4}, c={"x": 5}))
    assert [c for c, _ in index.search(["zebra"], 5)] == ["a", "b"]
    assert [c for c, _ in index.search(["zebra"], 1)] == ["a"]


def test_empty_query_and_unknown_lexemes_match_nothing():
    index = bm25.build_index(rows(a={"zebra": 1}))
    assert index.search([], 5) == [] and index.search(["nope"], 5) == []
    assert bm25.build_index([]).search(["zebra"], 5) == []


def test_duplicate_query_lexemes_are_ignored():
    index = bm25.build_index(rows(a={"zebra": 1, "pad": 3}, b={"pad": 4}))
    assert index.search(["zebra", "zebra"], 5) == index.search(["zebra"], 5)


def test_a_rare_term_outweighs_several_common_ones():
    docs = {f"d{i}": {"student": 3, "depart": 3, "pad": 4} for i in range(8)}
    docs["target"] = {"3672": 1, "pad": 9}
    index = bm25.build_index(rows(**docs))
    assert index.search(["student", "depart", "3672"], 3)[0][0] == "target"


# ---- the database parts ----


@pytest.mark.integration
def test_lexemes_for_codes_and_for_expire_versus_expiration(conn):
    assert bm25.query_lexemes(conn, "EET 3672") == ["3672", "eet"]
    assert bm25.query_lexemes(conn, "MAT 1275CO") == ["1275co", "mat"]
    assert bm25.query_lexemes(conn, "expire") == bm25.query_lexemes(conn, "expiration") == ["expir"]
    assert bm25.query_lexemes(conn, "what is the") == []


@pytest.mark.integration
def test_the_index_counts_positions_from_the_tsvector(conn):
    add_chunk(conn, "c1", vec(1.0), text="zebra zebra crossing of the road")
    index = bm25.load_index(conn)
    assert index.ids == ["c1"] and index.postings["zebra"] == [(0, 2)]
    assert index.lengths == [4]  # zebra zebra cross road: stop words are not indexed


@pytest.mark.integration
def test_the_index_is_cached_and_rebuilt_when_the_chunks_change(conn):
    add_chunk(conn, "c1", vec(1.0), text="zebra crossing")
    first = bm25.load_index(conn)
    assert bm25.load_index(conn) is first  # cached for the same chunks
    add_chunk(conn, "c2", vec(1.0), text="another zebra")
    second = bm25.load_index(conn)
    assert second is not first and sorted(second.ids) == ["c1", "c2"]


# ---- the mode switch ----


def run_search(conn, tmp_path, question, mode, k=3):
    client = FakeChatClient(vec(1.0, 0.0))
    return srch.search(conn, question, k, cfg=CFG, client_factory=lambda: client,
                       cache_path=tmp_path / "c.json", mode=mode)  # fmt: skip


@pytest.mark.integration
def test_hybrid_bm25_brings_in_a_keyword_hit_and_labels_its_rank(conn, tmp_path):
    add_world(conn)
    vector = run_search(conn, tmp_path, "zebra", "vector")
    found = run_search(conn, tmp_path, "zebra", "hybrid_bm25")
    assert "kw" not in [r["id"] for r in vector.results] and found.mode_used == "hybrid_bm25"
    top = found.results[0]
    assert top["id"] == "kw" and top["bm25_rank"] == 1 and top["keyword_rank"] is None
    assert top["vector_rank"] == 5 and top["similarity"] == pytest.approx(0.0, abs=1e-6)
    assert all(r["bm25_rank"] is None for r in vector.results)


@pytest.mark.integration
def test_hybrid_bm25_with_an_empty_query_falls_back_to_vector(conn, tmp_path):
    add_world(conn)
    vector = run_search(conn, tmp_path, "what is the", "vector")
    found = run_search(conn, tmp_path, "what is the", "hybrid_bm25")
    assert found.mode_used == "vector (empty keyword query)"
    assert [r["id"] for r in found.results] == [r["id"] for r in vector.results]


@pytest.mark.integration
def test_the_old_hybrid_mode_is_unchanged_and_still_uses_keyword_rank(conn, tmp_path):
    add_world(conn)
    found = run_search(conn, tmp_path, "zebra", "hybrid")
    top = found.results[0]
    assert top["id"] == "kw" and top["keyword_rank"] == 1 and top["bm25_rank"] is None


def test_the_modes_are_validated_and_vector_is_still_the_default():
    assert load_models(env={})["retrieval"]["mode"] == "vector"
    assert (
        load_models(env={"CTA_RETRIEVAL_MODE": "hybrid_bm25"})["retrieval"]["mode"] == "hybrid_bm25"
    )
    with pytest.raises(ValueError, match="retrieval.mode"):
        load_models(env={"CTA_RETRIEVAL_MODE": "bm26"})


@pytest.mark.integration
def test_the_threshold_still_uses_the_vector_similarity(conn, tmp_path):
    add_world(conn)
    cfg = copy.deepcopy(CFG)
    cfg["retrieval"]["mode"] = "hybrid_bm25"
    client = FakeChatClient(vec(1.0, 0.0))
    a = ans_mod.answer(conn, "zebra", date(2026, 10, 11), cfg=cfg, client_factory=lambda: client,
                       cache_path=tmp_path / "c.json")  # fmt: skip
    assert a.search.results[0]["id"] == "kw" and a.search.results[0]["similarity"] < 0.59
    assert a.search.top_vector_similarity > 0.99 and not a.abstained and client.chat_calls == 1
