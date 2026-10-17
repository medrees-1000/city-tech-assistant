import json
from pathlib import Path

import pytest

from cta.index import chunks as ch
from cta.settings import load_models

FIXTURES = Path(__file__).parent / "fixtures" / "processed"
CFG = load_models(env={})


def words(text: str) -> int:  # token counter without tiktoken or network
    return len(text.split())


def build(count=words):
    return ch.build_chunks(FIXTURES, CFG, count)


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
    one = ch.raw_chunks(FIXTURES)[0]
    with pytest.raises(ValueError, match="duplicate chunk ids"):
        ch.check_chunks([one, dict(one)], words, 6000)


def test_token_guard_fails_instead_of_truncating():
    with pytest.raises(ValueError, match="over max_chunk_tokens"):
        ch.check_chunks(ch.raw_chunks(FIXTURES), words, 3)


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
