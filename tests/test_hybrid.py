"""Hybrid search tests (Phase 3, step 1): no network, the throwaway schema for database parts."""

import copy
from datetime import date

import pytest

from cta import answer as ans_mod
from cta.eval import compare
from cta.index import search as srch
from cta.settings import load_models
from tests.test_answer import FakeChatClient, add_chunk
from tests.test_search import vec

CFG = load_models(
    env={"CTA_RERANK": "off", "CTA_ROUTER_MODE": "off"}
)  # the reranker has its own tests


def hybrid_cfg():
    cfg = copy.deepcopy(CFG)
    cfg["retrieval"]["mode"] = "hybrid"
    return cfg


# ---- reciprocal rank fusion (pure) ----


def test_rrf_scores_and_order_with_hand_made_lists():
    fused = srch.rrf(["a", "b", "c"], ["b", "d"], k=60)
    assert [e["id"] for e in fused] == ["b", "a", "d", "c"]
    by = {e["id"]: e for e in fused}
    assert by["b"]["rrf_score"] == pytest.approx(1 / 62 + 1 / 61)  # in both lists: both terms
    assert by["a"]["rrf_score"] == pytest.approx(1 / 61)
    assert (by["b"]["vector_rank"], by["b"]["keyword_rank"]) == (2, 1)
    assert (by["a"]["vector_rank"], by["a"]["keyword_rank"]) == (1, None)
    assert (by["d"]["vector_rank"], by["d"]["keyword_rank"]) == (None, 2)


def test_rrf_ties_break_by_id_whichever_list_they_came_from():
    assert [e["id"] for e in srch.rrf(["y"], ["x"])] == ["x", "y"]  # same score 1/61
    assert [e["id"] for e in srch.rrf(["x"], ["y"])] == ["x", "y"]
    assert [e["id"] for e in srch.rrf(["b", "a"], [])] == [
        "b",
        "a",
    ]  # different ranks: rank decides


def test_rrf_k_changes_the_scores_not_the_order_of_a_single_list():
    assert [e["id"] for e in srch.rrf(["a", "b"], [], k=1)] == ["a", "b"]
    assert srch.rrf(["a"], [], k=1)[0]["rrf_score"] == pytest.approx(1 / 2)


def test_tsquery_text_quotes_every_lexeme():
    assert srch.tsquery_text(["eet", "3672"]) == "'eet' | '3672'"
    assert srch.tsquery_text(["o'brien"]) == "'o''brien'"
    assert srch.tsquery_text([]) == ""


# ---- configuration ----


def test_default_mode_is_vector_and_the_switch_is_validated():
    assert load_models(env={})["retrieval"]["mode"] == "vector"
    assert load_models(env={"CTA_RETRIEVAL_MODE": "hybrid"})["retrieval"]["mode"] == "hybrid"
    with pytest.raises(ValueError, match="retrieval.mode"):
        load_models(env={"CTA_RETRIEVAL_MODE": "bm25"})
    assert CFG["retrieval"]["candidates"] == 20 and CFG["retrieval"]["rrf_k"] == 60


# ---- the generated column and the keyword query (database) ----


@pytest.mark.integration
def test_tsv_is_a_generated_column_that_follows_the_text(conn):
    add_chunk(conn, "c1", vec(1.0), text="Prerequisites for EET 3672")
    assert conn.execute("SELECT tsv @@ to_tsquery('simple', '''3672''') FROM chunks").fetchone()[0]
    conn.execute("UPDATE chunks SET text = 'nothing about it here'")
    assert not conn.execute(
        "SELECT tsv @@ to_tsquery('simple', '''3672''') FROM chunks"
    ).fetchone()[0]
    with pytest.raises(Exception, match="generated column"):
        conn.execute("UPDATE chunks SET tsv = to_tsvector('x')")
    conn.rollback()


@pytest.mark.integration
def test_the_english_configuration_keeps_codes_and_drops_stop_words(conn):
    lex = srch.keyword_lexemes
    assert lex(conn, "EET 3672") == ["3672", "eet"]
    assert lex(conn, "MAT 1275CO") == ["1275co", "mat"]  # lowercased, whole, not stemmed
    assert "1275" not in lex(conn, "MAT 1275CO")  # 1275 and 1275CO are different lexemes
    assert lex(conn, "What are the prerequisites for CST 3613?") == ["3613", "cst", "prerequisit"]
    assert lex(conn, "what is the") == []  # only stop words
    assert lex(conn, "EET3212") == ["eet3212"]  # without a space it is one lexeme


@pytest.mark.integration
def test_keyword_query_is_an_or_not_an_and(conn):
    add_chunk(conn, "only-code", vec(1.0), text="EET 3672 is a course")
    add_chunk(conn, "only-word", vec(1.0), text="a lab about sensors")
    add_chunk(conn, "neither", vec(1.0), text="completely unrelated")
    query = srch.tsquery_text(srch.keyword_lexemes(conn, "EET 3672 sensors"))
    assert set(srch.keyword_ids(conn, query, 10)) == {"only-code", "only-word"}


# ---- the mode switch ----


def add_world(conn):
    """near: close to the query vector, no keyword. kw: far from it, contains the word 'zebra'."""
    for i in range(4):
        add_chunk(conn, f"near{i}", vec(1.0, 0.1 * i), text=f"filler text {i}")
    add_chunk(conn, "kw", vec(0.0, 1.0), text="the zebra crossing rules")


def run_search(conn, tmp_path, question, mode, k=3):
    client = FakeChatClient(vec(1.0, 0.0))
    return srch.search(conn, question, k, cfg=CFG, client_factory=lambda: client,
                       cache_path=tmp_path / "c.json", mode=mode)  # fmt: skip


@pytest.mark.integration
def test_hybrid_brings_in_a_keyword_hit_that_vector_search_misses(conn, tmp_path):
    add_world(conn)
    vector = run_search(conn, tmp_path, "zebra", "vector")
    hybrid = run_search(conn, tmp_path, "zebra", "hybrid")
    assert "kw" not in [r["id"] for r in vector.results] and vector.mode_used == "vector"
    ids = [r["id"] for r in hybrid.results]
    assert ids[0] == "kw" and hybrid.mode_used == "hybrid"
    top = hybrid.results[0]
    assert (top["keyword_rank"], top["vector_rank"]) == (1, 5)  # fused with its vector rank
    assert top["similarity"] == pytest.approx(0.0, abs=1e-6)  # similarity stays the cosine
    for field in srch.RESULT_COLUMNS + ("rank", "similarity", "vector_rank", "keyword_rank"):
        assert field in top


@pytest.mark.integration
def test_empty_keyword_query_falls_back_to_vector_only(conn, tmp_path):
    add_world(conn)
    vector = run_search(conn, tmp_path, "what is the", "vector")
    hybrid = run_search(conn, tmp_path, "what is the", "hybrid")
    assert hybrid.mode_used == "vector (empty keyword query)"
    assert [r["id"] for r in hybrid.results] == [r["id"] for r in vector.results]


@pytest.mark.integration
def test_top_vector_similarity_is_the_best_cosine_in_both_modes(conn, tmp_path):
    add_world(conn)
    a, b = (
        run_search(conn, tmp_path, "zebra", "vector"),
        run_search(conn, tmp_path, "zebra", "hybrid"),
    )
    assert a.top_vector_similarity == pytest.approx(b.top_vector_similarity)
    assert (
        b.top_vector_similarity > 0.99 and b.results[0]["similarity"] < 0.01
    )  # not the fused top-1


def answer_with(conn, tmp_path, client, question="zebra"):
    return ans_mod.answer(
        conn, question, date(2026, 10, 11), cfg=hybrid_cfg(), client_factory=lambda: client,
        cache_path=tmp_path / "c.json",
    )  # fmt: skip


@pytest.mark.integration
def test_the_abstain_threshold_uses_the_vector_similarity_not_the_fused_top(conn, tmp_path):
    add_world(conn)
    client = FakeChatClient(vec(1.0, 0.0))
    a = answer_with(conn, tmp_path, client)
    # the fused top-1 is the keyword hit (cosine ~0) but the best vector similarity is ~1
    assert a.search.results[0]["id"] == "kw" and a.search.results[0]["similarity"] < 0.59
    assert not a.abstained and client.chat_calls == 1


@pytest.mark.integration
def test_a_keyword_hit_cannot_rescue_a_low_vector_similarity(conn, tmp_path):
    add_chunk(conn, "kw", vec(0.0, 1.0), text="the zebra crossing rules")
    add_chunk(conn, "far", vec(0.0, 0.0, 1.0), text="other")
    client = FakeChatClient(vec(1.0, 0.0))
    a = answer_with(conn, tmp_path, client)
    assert a.search.results[0]["id"] == "kw"  # found by keyword
    assert a.abstained and a.abstain_reason == "below_threshold" and client.chat_calls == 0


# ---- comparison rule ----


def stats(mrr, r5):
    return {m: 0.5 for m in compare.METRICS} | {"mrr": mrr, "recall@5": r5, "n": 30}


@pytest.mark.parametrize(
    ("before", "after", "keep"),
    [
        ((0.789, 0.775), (0.809, 0.765), True),  # MRR +0.020, recall -0.010: gain and small drop
        ((0.789, 0.775), (0.789, 0.785), True),  # recall@5 alone improves by 0.010
        ((0.789, 0.775), (0.795, 0.780), False),  # gains below 0.01
        ((0.789, 0.775), (0.850, 0.740), False),  # recall@5 drops by 0.035
        ((0.789, 0.775), (0.760, 0.800), False),  # MRR drops by 0.029
    ],
)
def test_the_pre_registered_rule(before, after, keep):
    assert compare.verdict(stats(*before), stats(*after))[0] is keep


def test_rank_changes_treat_a_miss_as_worse_than_any_rank():
    ranks_before = {"q1": 3, "q2": None, "q3": 2, "q4": 12}
    ranks_after = {"q1": 1, "q2": 9, "q3": None, "q4": None}
    old = [{"id": q, "first_rank": r} for q, r in ranks_before.items()]
    new = [{"id": q, "first_rank": r} for q, r in ranks_after.items()]
    improved, worsened, same = compare.changes(old, new)
    assert [q for q, *_ in improved] == ["q1", "q2"]
    assert [q for q, *_ in worsened] == ["q3"] and [q for q, *_ in same] == ["q4"]
    assert compare.shown(None) == "miss" and compare.shown(12) == "miss" and compare.shown(4) == "4"
