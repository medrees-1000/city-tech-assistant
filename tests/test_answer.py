"""Answer tests: fake client for embeddings and chat, throwaway schema, no network."""

from datetime import date
from types import SimpleNamespace

import pytest

from cta import answer as ans_mod
from cta.settings import load_models
from tests.test_search import DIM, FakeClient, vec

CFG = load_models(
    env={"CTA_RERANK": "off", "CTA_ROUTER_MODE": "off"}
)  # the reranker has its own tests
TODAY = date(2026, 10, 11)


class FakeChatClient(FakeClient):
    def __init__(self, query, reply="The deadline is Nov 6 [1]."):
        super().__init__(query)
        self.reply, self.chat_calls, self.messages = reply, 0, None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create_chat))

    def create_chat(self, **kwargs):
        self.chat_calls += 1
        self.messages = kwargs["messages"]
        self.kwargs = kwargs
        message = SimpleNamespace(content=self.reply)
        usage = SimpleNamespace(prompt_tokens=1000, completion_tokens=500)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


def add_chunk(conn, cid, embedding, kind="section", **kw):
    row = {
        "source": "https://example.edu/p", "heading_path": f"Heading {cid}",
        "terms": ["Fall 2026"], "last_updated": "2026-09-15", "text": f"text of {cid}",
    } | kw  # fmt: skip
    conn.execute(
        "INSERT INTO chunks (id, kind, source, source_id, doc_type, scope, terms, last_updated, "
        "fetched_at, heading_path, text, content_hash, meta_hash, embedding, embedding_model) "
        "VALUES (%s, %s, %s, %s, 'faq', 'city_tech', %s, %s, 'x', %s, %s, 'h', 'm', %s, %s)",
        (cid, kind, row["source"], cid, row["terms"], row["last_updated"], row["heading_path"],
         row["text"], embedding, CFG["embedding_model"]),
    )  # fmt: skip
    conn.commit()


@pytest.fixture
def db(conn):
    add_chunk(conn, "near", vec(1.0, 0.0))
    add_chunk(conn, "far", vec(0.0, 1.0))
    add_chunk(conn, "catalog:DEN 2400", vec(0.9, 0.1), kind="course", source="catalog_course")
    return conn


def go(conn, tmp_path, client, question="When is the deadline?", **kw):
    return ans_mod.answer(
        conn, question, TODAY, cfg=CFG, client_factory=lambda: client,
        cache_path=tmp_path / "c.json", **kw,
    )  # fmt: skip


def test_prompt_order_instructions_first_date_and_question_last():
    chunks = [
        {"id": "a", "kind": "section", "source": "https://x", "heading_path": "H",
         "terms": [], "last_updated": None, "text": "body text"}
    ]  # fmt: skip
    msgs = ans_mod.build_messages(chunks, TODAY, "What is X?")
    assert msgs[0] == {"role": "system", "content": ans_mod.INSTRUCTIONS}
    user = msgs[1]["content"]
    assert (
        user.index("[1] id: a") < user.index("body text") < user.index("Today's date: 2026-10-11")
    )
    assert user.endswith("Question: What is X?")
    assert user.index("Today's date") < user.index("Question:")


def test_source_block_shows_terms_last_updated_and_course_label():
    section = {"id": "s", "kind": "section", "source": "https://x/y", "heading_path": "A > B",
               "terms": ["Fall 2026"], "last_updated": "2026-09-15", "text": "t"}  # fmt: skip
    block = ans_mod.format_source(2, section)
    assert block.startswith(
        "[2] id: s\nsource: https://x/y\nheading: A > B\nterms: Fall 2026\nlast updated: 2026-09-15"
    )
    course = {**section, "id": "catalog:DEN 2400", "kind": "course", "source": "catalog_course",
              "terms": [], "last_updated": None}  # fmt: skip
    block = ans_mod.format_source(1, course)
    assert "source: Course catalog: DEN 2400" in block and "terms:" not in block


def test_marker_and_citation_parsing():
    a = ans_mod.parse_reply("ABSTAIN: the sources do not list hours.", 5)
    assert (
        a["abstained"] and a["reason"] == "the sources do not list hours." and a["citations"] == []
    )
    b = ans_mod.parse_reply("Due Nov 6 [1]. Also see [3] and [1].", 5)
    assert not b["abstained"] and b["citations"] == [1, 3] and b["invalid"] == []
    c = ans_mod.parse_reply("Claim [2] and invented [9] and [0].", 3)
    assert c["invalid"] == [0, 9]
    assert not ans_mod.parse_reply("I think ABSTAIN: later", 1)["abstained"]


@pytest.mark.integration
def test_normal_answer_cost_from_usage_and_log_row(db, tmp_path):
    client = FakeChatClient(vec(1.0, 0.0))
    a = go(db, tmp_path, client)
    assert not a.abstained and a.citations == [1] and a.invalid_citations == []
    assert client.chat_calls == 1 and client.messages[0]["role"] == "system"
    assert client.kwargs["temperature"] == 0.1 and client.kwargs["top_p"] == 0.3
    assert client.kwargs["reasoning_effort"] == "none"
    chat = (1000 * 0.10 + 500 * 0.50) / 1_000_000
    assert a.chat_cost == pytest.approx(chat)
    assert a.cost == pytest.approx(chat + 7 * 0.02 / 1_000_000)
    row = db.execute(
        "SELECT question, today, retrieved, abstained, chat_model, prompt_tokens, "
        "completion_tokens, embedding_tokens, cost_usd, latency_ms, query_cache_hit "
        "FROM request_logs"
    ).fetchall()
    assert len(row) == 1
    q, today, retrieved, abstained, model, pt, ct, et, cost, latency, hit = row[0]
    assert (q, today, abstained, model, pt, ct, et, hit) == (
        "When is the deadline?", TODAY, False, "gpt-6-luna", 1000, 500, 7, False
    )  # fmt: skip
    assert retrieved[0]["id"] == "near" and retrieved[0]["similarity"] == pytest.approx(1.0)
    assert float(cost) == pytest.approx(a.cost) and latency >= 0


@pytest.mark.integration
def test_answer_model_key_changes_only_the_answer_call(db, tmp_path):
    default = FakeChatClient(vec(1.0, 0.0))
    a = go(db, tmp_path, default)
    assert default.kwargs["model"] == "gpt-6-luna"
    cfg = {**CFG, "answer": {**CFG["answer"], "model": "gpt-6.1-sol"}}
    client = FakeChatClient(vec(1.0, 0.0))
    b = ans_mod.answer(
        db, "When is the deadline?", TODAY, cfg=cfg, client_factory=lambda: client,
        cache_path=tmp_path / "c.json",
    )  # fmt: skip
    assert client.kwargs["model"] == "gpt-6.1-sol"
    # same prompt, same sampling settings; only the model and so the price differ
    assert client.messages == default.messages
    assert {k: v for k, v in client.kwargs.items() if k != "model"} == {
        k: v for k, v in default.kwargs.items() if k != "model"
    }
    assert b.chat_cost == pytest.approx((1000 * 2.00 + 500 * 10.00) / 1_000_000)
    assert a.chat_cost == pytest.approx((1000 * 0.10 + 500 * 0.50) / 1_000_000)
    models = [r[0] for r in db.execute("SELECT chat_model FROM request_logs ORDER BY id")]
    assert models == ["gpt-6-luna", "gpt-6.1-sol"]


@pytest.mark.integration
def test_below_threshold_makes_no_chat_call(db, tmp_path):
    client = FakeChatClient(vec(0.0, 0.0, 1.0))  # orthogonal to every chunk: similarity 0
    a = go(db, tmp_path, client)
    assert (
        a.abstained
        and a.abstain_reason == "below_threshold"
        and a.text == ans_mod.THRESHOLD_ABSTAIN
    )
    assert client.chat_calls == 0 and a.chat_cost == 0
    assert db.execute("SELECT abstained, abstain_reason FROM request_logs").fetchone() == (
        True, "below_threshold"
    )  # fmt: skip


@pytest.mark.integration
def test_model_abstain_is_detected(db, tmp_path):
    client = FakeChatClient(vec(1.0, 0.0), reply="ABSTAIN: The sources do not give the room.")
    a = go(db, tmp_path, client)
    assert a.abstained and a.abstain_reason == "The sources do not give the room."


@pytest.mark.integration
def test_invalid_citation_is_reported(db, tmp_path):
    a = go(db, tmp_path, FakeChatClient(vec(1.0, 0.0), reply="Claim [1] and made up [8]."))
    assert a.invalid_citations == [8] and a.citations == [1, 8]


@pytest.mark.integration
def test_personal_data_is_redacted_before_the_insert(db, tmp_path):
    question = "My ID 23456789, email jane.doe@mail.citytech.cuny.edu: when is the deadline?"
    reply = "Contact jane.doe@mail.citytech.cuny.edu about 23456789 [1]."
    go(db, tmp_path, FakeChatClient(vec(1.0, 0.0), reply=reply), question=question)
    stored_q, stored_a = db.execute("SELECT question, answer FROM request_logs").fetchone()
    assert stored_q == "My ID [ID], email [EMAIL]: when is the deadline?"
    assert "23456789" not in stored_a and "@" not in stored_a


@pytest.mark.integration
def test_dry_run_calls_no_chat_and_logs_nothing(db, tmp_path):
    client = FakeChatClient(vec(1.0, 0.0))
    a = go(db, tmp_path, client, dry_run=True)
    assert client.chat_calls == 0 and a.prompt and a.text == ""
    assert db.execute("SELECT count(*) FROM request_logs").fetchone()[0] == 0


@pytest.mark.integration
def test_cache_hit_is_logged(db, tmp_path):
    go(db, tmp_path, FakeChatClient(vec(1.0, 0.0)))
    go(db, tmp_path, FakeChatClient(vec(1.0, 0.0)))
    hits = [r[0] for r in db.execute("SELECT query_cache_hit FROM request_logs ORDER BY id")]
    assert hits == [False, True]


def test_dimension_constant_matches_config():
    assert DIM == CFG["embedding_dimensions"] == 1536
