"""Chunks and their loader: building the chunks from the processed records (pure: no network, no
database), then the embedding client and the loader. Database tests run in a throwaway schema that
is dropped afterwards; the real `chunks` table is never touched.
"""

import hashlib
import json
import random
from types import SimpleNamespace

import httpx2
import openai
import pytest

from cta.index import chunks as ch
from cta.index import embed, load
from cta.settings import load_models
from tests.helpers import PROCESSED_FIXTURES, words
from tests.helpers import PROCESSED_FIXTURES as FIXTURES

# ---- from test_chunks.py ----

CFG = load_models(env={})


def build(count=words):
    return ch.build_chunks(PROCESSED_FIXTURES, CFG, count)


def by_id():
    return {c["id"]: c for c in build()}


def test_counts_by_kind():
    kinds = [c["kind"] for c in build()]
    assert (kinds.count("section"), kinds.count("course"), kinds.count("contact")) == (2, 3, 2)


def test_table_merges_into_parent_and_keeps_its_heading():
    c = by_id()["page/x/page#1"]
    assert c["merged_section_ids"] == ["page/x/page#2"]
    assert c["text"].startswith("Deadlines\n\nSee the following table:")
    assert "## Fall 2026 Dates" in c["text"] and "| 1 | 2 |" in c["text"]
    assert c["terms"] == ["Fall 2026"] and c["term"] == "Fall 2026"  # from the merged table
    assert "page/x/page#2" not in by_id()


def test_embed_false_section_is_left_out_and_ids_keep_position():
    ids = [c["id"] for c in build() if c["kind"] == "section"]
    assert ids == ["page/x/page#1", "page/x/page#3"]


def test_course_chunk_content():
    c = by_id()["catalog:CST 1100"]
    assert c["text"].splitlines()[0] == "CST 1100 - Intro"
    assert "Prerequisites: CST 1000." in c["text"]
    assert "Prerequisites: Prerequisites" not in c["text"]
    assert "Department: Computer Systems Technology" in c["text"]
    assert "Computer Systems - BTech (degree map, requirements)" in c["text"]
    assert (c["doc_type"], c["scope"], c["source"]) == (
        "catalog_course",
        "city_tech",
        "catalog_course",
    )


def test_shorthand_is_flagged_not_expanded():
    text = by_id()["catalog:CST 1205"]["text"]
    assert "PRE_CST1100 (shorthand as printed in the catalog, not expanded)" in text
    assert "none listed" in by_id()["catalog:EET 3672"]["text"]


def test_contact_chunks():
    cs = by_id()
    assert cs["contact:bursar"]["text"].startswith("Contact: Bursar office\n\nCONTACT US")
    assert (
        cs["contact:bursar"]["scope"] == "city_tech" and cs["contact:bursar"]["department"] is None
    )
    dept = cs["contact:CST-NYT"]
    assert dept["text"].startswith("Contact: Computer Systems Technology\n")
    assert (dept["scope"], dept["department"], dept["doc_type"]) == (
        "department",
        "CST-NYT",
        "contacts",
    )


def test_hashes_are_stable_and_separate():
    a, b = build(), build()
    assert [(c["content_hash"], c["meta_hash"]) for c in a] == [
        (c["content_hash"], c["meta_hash"]) for c in b
    ]
    c = by_id()["catalog:CST 1100"]
    other = dict(c, source_id="changed")
    assert ch.finish(dict(other), CFG["embedding_model"], 1536)["content_hash"] == c["content_hash"]
    assert ch.finish(dict(other), CFG["embedding_model"], 1536)["meta_hash"] != c["meta_hash"]
    assert ch.finish(dict(c), "other-model", 1536)["content_hash"] != c["content_hash"]


def test_duplicate_id_fails():
    one = ch.raw_chunks(PROCESSED_FIXTURES)[0]
    with pytest.raises(ValueError, match="duplicate chunk ids"):
        ch.check_chunks([one, dict(one)], words, 6000)


def test_token_guard_fails_instead_of_truncating():
    with pytest.raises(ValueError, match="over max_chunk_tokens"):
        ch.check_chunks(ch.raw_chunks(PROCESSED_FIXTURES), words, 3)


def test_gold_problems(tmp_path):
    q = tmp_path / "q.jsonl"
    gold = [{"id": "page/x/page#2"}, {"id": "catalog:CST 1100"}, {"id": "page/x/page#9"},
            {"id": "fall-2026-044"}, {"id": "catalog:ZZZ 1"}]  # fmt: skip
    q.write_text(json.dumps({"id": "q1", "gold_sources": gold}) + "\n")
    assert ch.gold_problems(build(), q) == ["q1: page/x/page#9", "q1: catalog:ZZZ 1"]


@pytest.mark.skipif(not (ch.PROCESSED / "courses").exists(), reason="data/processed not present")
def test_real_data_every_gold_source_has_a_chunk():
    chunks = ch.build_chunks(cfg=CFG, count=words)
    assert ch.gold_problems(chunks) == []
    assert len(chunks) == len({c["id"] for c in chunks})


def test_stats_and_main_say_so_when_there_is_no_data(monkeypatch, capsys, tmp_path):
    """Batch 1, item 4: an empty data folder used to crash --stats with min() of an empty list."""
    from cta.index import chunks as chunks_module

    assert chunks_module.stats([], lambda t: 0, {}) == chunks_module.NO_DATA
    # a real empty folder: build_chunks finds nothing (the fresh-clone case that crashed)
    real = chunks_module.build_chunks
    monkeypatch.setattr(chunks_module, "build_chunks", lambda **kw: real(processed=tmp_path, **kw))
    monkeypatch.setattr(chunks_module, "PROCESSED", tmp_path)
    for flags in (["x", "--stats"], ["x", "--write"], ["x", "--stats", "--write"]):
        assert chunks_module.main(flags) == 1
        out = capsys.readouterr().out
        assert "no chunks" in out and "Traceback" not in out
    assert not (tmp_path / "chunks.jsonl").exists()  # nothing written


# ---- from test_embed_load.py ----
#
# Embedding client and loader tests. No network, and the real `chunks` table is never touched:
# database tests run in a throwaway schema that is dropped afterwards.

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
