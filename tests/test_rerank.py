"""LLM reranker (Phase 3, step 3): scoring, ordering, fallback, cache, the 400-token cut, switch."""

import json

import openai
import pytest

from cta.index import rerank as rr
from cta.index import search as srch
from cta.index.chunks import get_encoding
from cta.settings import load_models
from tests.test_answer import FakeChatClient
from tests.test_search import vec

CFG = load_models(env={})


def put(conn, cid, scope, dept, embedding, text="plain text"):
    conn.execute(
        "INSERT INTO chunks (id, kind, source, source_id, doc_type, department, scope, fetched_at, "
        "heading_path, text, content_hash, meta_hash, embedding, embedding_model) "
        "VALUES (%s, 'section', 's', %s, 'faq', %s, %s, 'x', %s, %s, 'h', 'm', %s, %s)",
        (cid, cid, dept, scope, cid, text, embedding, CFG["embedding_model"]),
    )
    conn.commit()


def world(conn):
    """Query vector is vec(1, 0). The CST page is the closest chunk, then the others."""
    put(conn, "cst-page", "department", "CST-NYT", vec(1.0, 0.0), "zebra")
    put(conn, "eet-page", "department", "EET-NYT", vec(0.9, 0.1), "zebra")
    put(conn, "office", "city_tech", None, vec(0.8, 0.2), "zebra")
    put(conn, "cuny-doc", "cuny", None, vec(0.7, 0.3), "zebra")
    put(
        conn, "cst-course", "city_tech", "CST-NYT", vec(0.6, 0.4), "zebra"
    )  # a course: city_tech scope
    put(conn, "math-page", "department", "MATH-NYT", vec(0.5, 0.5), "zebra")


def ids(found_):
    return [r["id"] for r in found_.results]


def chunk(n, text="some text"):
    return {"id": f"c{n}", "kind": "section", "source": f"https://x/{n}", "heading_path": f"H{n}",
            "text": text}  # fmt: skip


def reply(*scores):
    return json.dumps({str(i): s for i, s in enumerate(scores, 1)})


def rerank(chunks, client, tmp_path, question="q?", **kw):
    return rr.rerank(question, chunks, CFG, client_factory=lambda: client,
                     cache_path=tmp_path / "rerank.json", **kw)  # fmt: skip


# ---- sorting, ties, parsing ----


def test_sorted_by_score_descending_and_ties_keep_the_first_stage_order():
    assert rr.order_by_score([3, 9, 3, 9, 0]) == [1, 3, 0, 2, 4]
    assert rr.order_by_score([5, 5, 5]) == [0, 1, 2]


@pytest.mark.parametrize(
    "bad",
    [
        "not json",
        "[1, 2, 3]",
        json.dumps({"1": 5, "2": 5}),  # candidate 3 missing
        json.dumps({"1": 5, "2": 5, "3": "high"}),  # not a number
        json.dumps({"1": 5, "2": 5, "3": 11}),  # above 10
        json.dumps({"1": 5, "2": 5, "3": -1}),  # below 0
        json.dumps({"1": 5, "2": 5, "3": True}),  # a boolean is not a score
        json.dumps({"1": 5, "2": 5, "3": None}),
    ],
)
def test_malformed_or_incomplete_replies_are_rejected(bad):
    assert rr.parse_scores(bad, 3) is None


def test_a_good_reply_parses_with_integers_floats_and_extra_keys_ignored():
    assert rr.parse_scores('{"1": 0, "2": 7.5, "3": 10, "4": 3}', 3) == [0.0, 7.5, 10.0]


# ---- the 400-token cut ----


def test_text_is_cut_to_the_first_400_tokens():
    encoding = get_encoding()
    long = " ".join(f"word{i}" for i in range(2000))
    cut = rr.cut(long)
    assert len(encoding.encode(cut)) == rr.CHUNK_TOKENS == 400
    assert long.startswith(cut)
    assert rr.cut("short text") == "short text"


def test_the_message_carries_the_cut_text_source_and_heading():
    long = " ".join(f"word{i}" for i in range(2000))
    user = rr.build_messages("When?", [chunk(1, long)])[1]["content"]
    assert "word0 " in user and "word1999" not in user
    assert "[1] source: https://x/1" in user and "heading: H1" in user and "Question: When?" in user


# ---- the call ----


def test_candidates_are_reordered_by_the_models_scores(tmp_path):
    client = FakeChatClient(vec(1.0), reply=reply(2, 9, 2, 5))
    got = rerank([chunk(n) for n in range(1, 5)], client, tmp_path)
    assert got.order == [1, 3, 0, 2] and not got.failed and not got.cache_hit
    assert got.cost > 0 and got.prompt_tokens == 1000 and got.api_ms >= 0
    kw = client.kwargs
    assert kw["temperature"] == 0 and kw["reasoning_effort"] == "none"
    assert kw["response_format"] == {"type": "json_object"} and kw["model"] == CFG["chat_model"]


def test_an_unusable_reply_keeps_the_first_stage_order_and_is_counted(tmp_path):
    client = FakeChatClient(vec(1.0), reply='{"1": 9}')  # incomplete
    got = rerank([chunk(n) for n in range(1, 4)], client, tmp_path)
    assert got.failed and got.reason == "unusable reply" and got.order == [0, 1, 2]
    assert got.cost > 0  # the call was paid for
    rerank([chunk(n) for n in range(1, 4)], client, tmp_path)
    assert client.chat_calls == 2  # a failed reply is not cached


def test_an_api_error_keeps_the_first_stage_order_and_is_counted(tmp_path):
    class Broken:
        class chat:  # noqa: N801
            class completions:  # noqa: N801
                @staticmethod
                def create(**kw):
                    raise openai.OpenAIError("no")

    got = rerank([chunk(1), chunk(2)], Broken, tmp_path)
    assert got.failed and "rejected" in got.reason and got.order == [0, 1] and got.cost == 0


def test_a_repeat_call_is_served_from_the_cache_at_no_cost(tmp_path):
    client = FakeChatClient(vec(1.0), reply=reply(1, 8))
    first = rerank([chunk(1), chunk(2)], client, tmp_path)
    again = rerank([chunk(1), chunk(2)], client, tmp_path)
    assert client.chat_calls == 1
    assert again.cache_hit and again.cost == 0 and again.order == first.order == [1, 0]
    assert again.api_ms == first.api_ms and again.prompt_tokens == first.prompt_tokens
    stored = (tmp_path / "rerank.json").read_text()
    assert "q?" not in stored and "some text" not in stored  # scores only


def test_the_cache_key_changes_with_question_text_model_and_prompt_version(tmp_path, monkeypatch):
    client = FakeChatClient(vec(1.0), reply=reply(1, 8))
    rerank([chunk(1), chunk(2)], client, tmp_path)
    rerank([chunk(1), chunk(2)], client, tmp_path, question="another?")
    rerank([chunk(1), chunk(2, "different")], client, tmp_path)
    monkeypatch.setattr(rr, "PROMPT_VERSION", 2)
    rerank([chunk(1), chunk(2)], client, tmp_path)
    assert client.chat_calls == 4


def test_a_call_that_could_pass_the_allowance_is_refused_before_it_is_made(tmp_path):
    client = FakeChatClient(vec(1.0), reply=reply(1, 8))
    with pytest.raises(rr.SpendLimit):
        rerank([chunk(1), chunk(2)], client, tmp_path, max_cost=0.0)
    assert client.chat_calls == 0


# ---- the switch and the search ----


def test_the_switch_values_and_the_default():
    assert CFG["retrieval"]["rerank"] == "pool_a"  # switched on in the commit after experiment 3
    assert (
        load_models(env={"CTA_RERANK": "off", "CTA_ROUTER_MODE": "off"})["retrieval"]["rerank"]
        == "off"
    )
    assert load_models(env={"CTA_RERANK": "pool_a"})["retrieval"]["rerank"] == "pool_a"
    with pytest.raises(ValueError, match="rerank"):
        load_models(env={"CTA_RERANK": "yes"})


def test_the_pools_are_the_ones_fixed_in_advance():
    assert rr.POOLS == {"pool_a": {"size": 20}}


def run(conn, tmp_path, rerank_mode, reply_text, question="What does the EET department do?", k=3):
    client = FakeChatClient(vec(1.0, 0.0), reply=reply_text)
    found = srch.search(conn, question, k, cfg=CFG, client_factory=lambda: client,
                        cache_path=tmp_path / "c.json", rerank=rerank_mode)  # fmt: skip
    return found, client


@pytest.mark.integration
def test_off_is_the_baseline_and_makes_no_chat_call(conn, tmp_path):
    world(conn)
    found, client = run(conn, tmp_path, "off", "unused")
    assert client.chat_calls == 0 and found.rerank is None and found.rerank_mode == "off"
    assert ids(found) == ["cst-page", "eet-page", "office"]


@pytest.mark.integration
def test_pool_a_reranks_the_vector_top_20_and_keeps_the_top_k(conn, tmp_path):
    world(conn)
    # first stage (vector): cst-page, eet-page, office, cuny-doc, cst-course, math-page
    found, client = run(conn, tmp_path, "pool_a", reply(0, 1, 9, 0, 5, 3))
    assert client.chat_calls == 1
    assert ids(found) == ["office", "cst-course", "math-page"]  # top 3 by score
    assert [r["rank"] for r in found.results] == [1, 2, 3]
    assert [r["first_stage_rank"] for r in found.results] == [3, 5, 6]
    assert len(found.pool) == 6 and found.rerank_mode == "pool_a" and not found.rerank.failed
    assert found.total_cost == pytest.approx(found.cost + found.rerank.cost)


@pytest.mark.integration
def test_a_failed_rerank_returns_the_first_stage_order(conn, tmp_path):
    world(conn)
    found, _ = run(conn, tmp_path, "pool_a", "garbage")
    assert found.rerank.failed
    assert ids(found) == ["cst-page", "eet-page", "office"]


@pytest.mark.integration
def test_the_abstain_threshold_value_is_the_first_stage_cosine_similarity(conn, tmp_path):
    world(conn)
    off, _ = run(conn, tmp_path, "off", "unused")
    on, _ = run(conn, tmp_path, "pool_a", reply(0, 0, 0, 0, 0, 10))  # math-page scored top
    assert on.results[0]["id"] == "math-page"
    assert on.top_vector_similarity == off.top_vector_similarity > 0.99
    assert on.top_vector_similarity != on.results[0]["similarity"]
