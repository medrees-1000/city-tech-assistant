"""The local API (Phase 4). No network, no database, no paid call: the connection is a stub."""

import json
from datetime import date
from types import SimpleNamespace

import psycopg
import pytest
from fastapi.testclient import TestClient

from cta.answer import THRESHOLD_ABSTAIN, Answer
from cta.api import __main__ as api_main
from cta.api import app as api_app
from cta.api import convert, schema
from cta.api.checks import StartupError, startup_problems
from cta.graph import build, render
from cta.graph import chain as chains
from cta.graph.build import Router
from cta.index.db import migration_files
from cta.index.embed import ApiError
from cta.index.rerank import Rerank
from cta.index.search import Search
from cta.settings import ROOT, TRACING_VARIABLES, load_models
from tests.test_chain import WORLD

ENV = {"OPENAI_API_KEY": "sk-test"}
CFG = load_models(env={})  # router on, contacts on: the defaults


class FakeConn:
    """Answers SELECT 1 and the schema_migrations query; nothing else."""

    def __init__(self, applied):
        self.applied = applied

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, *args):
        return [(n,) for n in self.applied] if "schema_migrations" in sql else [(1,)]


def all_applied():
    return [p.name for p in migration_files()]


def ok_connect():
    return FakeConn(all_applied())


def down_connect():
    raise ConnectionError("password authentication failed for user cta at 10.0.0.5")


def make_app(**kw):
    return api_app.create_app(
        CFG, connect=kw.pop("connect", ok_connect), env=kw.pop("env", ENV), **kw
    )


# ---- /health ----


def test_health_is_ok_with_the_database_up():
    body = TestClient(make_app()).get("/health").json()
    assert body["status"] == "ok" and body["db"] == "ok" and body["router"] == "on"
    assert set(body) == {"status", "db", "version", "router", "log_failures", "feedback_failures"}
    assert body["log_failures"] == 0 and body["feedback_failures"] == 0


def test_health_is_503_with_the_database_down_and_shows_no_driver_text():
    app = make_app(check_startup=False, connect=down_connect)
    r = TestClient(app).get("/health")
    assert r.status_code == 503 and r.json()["db"] == "down" and r.json()["status"] == "degraded"
    assert "password" not in r.text and "10.0.0.5" not in r.text


# ---- the startup guards ----


@pytest.mark.parametrize("name", TRACING_VARIABLES)
def test_the_app_refuses_to_start_with_any_tracing_variable_on(name):
    with pytest.raises(StartupError, match=name):
        make_app(env=ENV | {name: "true"})


def test_tracing_values_that_are_off_do_not_block_the_start():
    make_app(env=ENV | {"LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": ""})


@pytest.mark.parametrize("key", ["mode", "contacts"])
def test_router_and_contacts_must_be_on(key):
    cfg = load_models(env={})
    cfg["router"][key] = "off"
    with pytest.raises(StartupError, match=f"router.{key} must be on"):
        api_app.create_app(cfg, connect=ok_connect, env=ENV)


def test_a_missing_openai_key_is_refused_and_the_key_value_is_not_needed():
    with pytest.raises(StartupError, match="OPENAI_API_KEY is not set"):
        make_app(env={})


def test_missing_data_files_are_listed(tmp_path):
    problems = startup_problems(CFG, env=ENV, connect=ok_connect, root=tmp_path)
    assert any("config/contacts.yaml" in p for p in problems)
    assert any("calendar_events.json" in p for p in problems)
    assert any("data/processed/courses" in p for p in problems)


def test_database_down_gives_a_fixed_message_without_driver_text():
    problems = startup_problems(CFG, env=ENV, connect=down_connect)
    assert problems == [
        "database not reachable, or schema_migrations missing (run: docker compose up -d)"
    ]


def test_unapplied_migrations_are_named():
    problems = startup_problems(CFG, env=ENV, connect=lambda: FakeConn(all_applied()[:-1]))
    assert len(problems) == 1 and migration_files()[-1].name in problems[0]


def test_all_problems_are_reported_together():
    cfg = load_models(env={})
    cfg["router"]["mode"] = "off"
    with pytest.raises(StartupError) as e:
        api_app.create_app(cfg, connect=down_connect, env={"LANGSMITH_TRACING": "1"})
    for text in ("tracing is enabled", "router.mode", "OPENAI_API_KEY", "database not reachable"):
        assert text in str(e.value)


def test_a_good_setup_has_no_problems():
    assert startup_problems(CFG, env=ENV, connect=ok_connect) == []


def test_the_launcher_prints_the_problems_and_does_not_start_the_server(monkeypatch, capsys):
    started = []
    monkeypatch.setattr(api_main, "startup_problems", lambda cfg: ["nope"])
    monkeypatch.setattr(api_main.uvicorn, "run", lambda *a, **k: started.append((a, k)))
    assert api_main.main(["x"]) == 2 and not started
    assert "nope" in capsys.readouterr().out


def test_the_launcher_listens_on_localhost_only(monkeypatch):
    started = []
    monkeypatch.setattr(api_main, "startup_problems", lambda cfg: [])
    monkeypatch.setattr(api_main.uvicorn, "run", lambda *a, **k: started.append(k))
    assert api_main.main(["x", "--port", "8123"]) == 0
    assert started == [{"factory": True, "host": "127.0.0.1", "port": 8123, "access_log": False}]


# ---- config ----


def test_api_config_defaults_and_the_date_override():
    assert CFG["api"] == {"today": None, "max_question_chars": 500, "max_body_bytes": 4096}
    assert str(load_models(env={"CTA_API_TODAY": "2026-10-11"})["api"]["today"]) == "2026-10-11"
    with pytest.raises(ValueError, match="api.today"):
        load_models(env={"CTA_API_TODAY": "yesterday"})


def test_env_example_lists_the_new_names():
    names = {
        ln.split("=")[0] for ln in (ROOT / ".env.example").read_text().splitlines() if "=" in ln
    }
    assert {"CTA_ROUTER_CONTACTS", "CTA_API_TODAY"} <= names


# ================= POST /ask (step 3) =================

TODAY = date(2026, 10, 11)
EVENTS = build.load_events()
REGISTRAR = render.registrar_contact()
PAGE = "https://www.citytech.cuny.edu/registrar/faqs.aspx"


class Client:
    """Scripted chat client: classifier, calendar selector, chain answer and retrieval answer."""

    def __init__(self, intent="other", mention=None, row_ids=(), answer="ok [1]", fail=None,
                 topic=None):  # fmt: skip
        self.intent, self.mention, self.row_ids = intent, mention, list(row_ids)
        self.topic = topic  # the topic call's reply text; None = an unusable reply
        self.answer_text, self.fail, self.calls = answer, fail, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kw):
        system = kw["messages"][0]["content"]
        which = (
            "classify" if system.startswith("You route")
            else "select" if system.startswith("You choose")
            else "topic" if system.startswith("You label")
            else "answer"
        )  # fmt: skip
        self.calls.append(which)
        if self.fail:
            raise self.fail
        reply = {
            "classify": json.dumps({"intent": self.intent, "term_mention": self.mention}),
            "select": json.dumps({"row_ids": self.row_ids}),
            "answer": self.answer_text,
            "topic": self.topic if self.topic is not None else "not json",
        }[which]
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=10)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply))], usage=usage
        )


def chunk(cid, source=PAGE, kind="section", **kw):
    base = {"id": cid, "kind": kind, "source": source, "source_id": cid, "merged_section_ids": [],
            "doc_type": "faq", "department": None, "scope": "city_tech", "term": None, "terms": [],
            "heading_path": "FAQ > Question", "last_updated": None, "text": "Some  text\nhere.",
            "similarity": 0.7, "rank": 1}  # fmt: skip
    return base | kw


def retrieve_answer(text="Yes. [1]", abstained=False, reason=None, citations=(1,), n=3):
    chunks = [chunk(f"page/registrar/faqs#{i}", rank=i) for i in range(1, n + 1)]
    pool = [chunk(f"page/registrar/faqs#{i}", rank=i, similarity=0.9 - i / 10) for i in range(1, 8)]
    scores = [5.0, 1.0, 9.0, 0.0, 0.0, 0.0, 0.0]
    rerank = Rerank(order=[2, 0, 1, 3, 4, 5, 6], scores=scores, ms=11.0, prompt_tokens=40,
                    completion_tokens=5, cost=0.0004)  # fmt: skip
    search = Search(chunks, True, 0, 7, 1e-7, top_vector_similarity=0.8, retrieval_ms=60.0,
                    rerank_mode="pool_a", rerank=rerank, pool=pool)  # fmt: skip
    return Answer(text, abstained, reason, chunks, list(citations), [], search, prompt_tokens=300,
                  completion_tokens=20, chat_cost=0.0002, chat_ms=400)  # fmt: skip


def cfg_for(**api):
    cfg = load_models(env={"CTA_RERANK": "off", "CTA_ROUTER_CHAIN": "on"})
    cfg["api"] |= api
    return cfg


def make_client_app(client, monkeypatch, stub=None, cfg=None, tmp_root=None, connect=ok_connect,
                    clock=lambda: TODAY, log_writer=None, feedback_writer=None):  # fmt: skip
    cfg = cfg or cfg_for()
    if stub is not None:
        monkeypatch.setattr(build, "answer", lambda *a, **k: stub)
    monkeypatch.setattr(chains, "load_records", lambda *a, **k: WORLD)

    def factory(conn, cfg):
        return Router(conn, cfg, lambda: client, events=EVENTS, contact=REGISTRAR)

    logs, votes = [], {}  # the rows the API would have written, and the votes it would have saved

    def remember(conn, record):
        logs.append(record)

    def vote_writer(conn, request_id, vote):
        if request_id not in {r["request_id"] for r in logs}:
            return False
        votes[request_id] = vote
        return True

    writer = log_writer or remember
    app = api_app.create_app(cfg, connect=connect, check_startup=False, router_factory=factory,
                             root=tmp_root or ROOT, clock=clock, log_writer=writer,
                             feedback_writer=feedback_writer or vote_writer,
                             client_factory=lambda: client)  # fmt: skip
    test_client = TestClient(app, raise_server_exceptions=False)
    test_client.logs, test_client.votes = logs, votes
    return test_client


def ask(client, question="How do I apply for graduation?"):
    return client.post("/ask", json={"question": question})


# ---- the contract ----


def test_a_retrieval_answer_has_every_contract_field_and_validates(monkeypatch):
    c = make_client_app(Client(), monkeypatch, retrieve_answer())
    r = ask(c)
    assert r.status_code == 200
    body = r.json()
    fields = ("request_id question answer answer_type abstained abstain_reason route citations "
              "contact how_found meta").split()  # fmt: skip
    assert set(body) == set(fields)
    schema.AskResponse.model_validate(body)
    assert body["route"] == "retrieve" and body["answer_type"] == "answer" and not body["abstained"]
    assert body["answer"] == "Yes. [1]" and body["contact"] is None
    assert body["request_id"] == r.headers["X-Request-ID"]
    assert body["meta"]["today"] == "2026-10-11" and body["meta"]["model"] == "gpt-6-luna"


def test_citations_are_the_numbered_sources_with_a_cited_flag_and_a_short_excerpt(monkeypatch):
    body = ask(make_client_app(Client(), monkeypatch, retrieve_answer())).json()
    cites = body["citations"]
    assert [c["n"] for c in cites] == [1, 2, 3] and [c["cited"] for c in cites] == [
        True,
        False,
        False,
    ]
    assert cites[0]["url"] == PAGE and cites[0]["file"] is None and cites[0]["doc_type"] == "faq"
    assert "scope" not in cites[0]  # dropped from the contract (owner decision)
    assert cites[0]["title"] == "FAQ > Question" and cites[0]["excerpt"] == "Some text here."


def test_how_found_has_the_pool_with_rerank_order_stages_tokens_and_cost(monkeypatch):
    hf = ask(make_client_app(Client(), monkeypatch, retrieve_answer())).json()["how_found"]
    assert hf["route_detail"] == "other" and hf["intent"] == "other"
    assert hf["top_vector_similarity"] == 0.8 and hf["abstain_threshold"] == 0.59
    pool = {p["id"]: p for p in hf["retrieved"]}
    assert len(pool) == 7
    best = pool["page/registrar/faqs#3"]  # the reranker put pool index 2 first
    assert (best["final_rank"], best["rerank_score"], best["sent_to_answerer"]) == (1, 9.0, True)
    assert pool["page/registrar/faqs#2"]["final_rank"] == 3
    assert pool["page/registrar/faqs#5"]["sent_to_answerer"] is True  # final rank 5
    assert pool["page/registrar/faqs#6"]["final_rank"] == 6
    assert pool["page/registrar/faqs#6"]["sent_to_answerer"] is False
    st = hf["stages_ms"]
    assert st["rerank"] == 11.0 and st["retrieval"] == 49.0 and st["select"] is None
    assert st["classify"] is not None and st["answer"] is not None and st["total"] > 0
    assert hf["tokens"]["embedding"] == 7 and hf["tokens"]["rerank_prompt"] == 40
    assert hf["tokens"]["prompt"] == 400  # 300 for the answer + 100 for the classifier
    cost = hf["cost_usd"]
    assert cost["rerank"] == 0.0004 and cost["total"] == pytest.approx(
        cost["classify"] + cost["embedding"] + cost["rerank"] + cost["answer"], abs=1e-7
    )
    assert hf["cache_hits"] == {"embedding": True, "rerank": False}
    assert hf["calendar"] is None and hf["chain"] is None


def test_a_threshold_abstention_with_a_clear_office_has_a_card_and_no_contact_sentence(monkeypatch):
    stub = retrieve_answer(THRESHOLD_ABSTAIN, True, "below_threshold", citations=())
    stub.sources[0]["id"] = "page/CST-NYT/tutoring#2"
    body = ask(
        make_client_app(Client(), monkeypatch, stub), "Are there open seats in CST 1101?"
    ).json()
    assert body["abstained"] and body["answer_type"] == "abstain" and body["route"] == "retrieve"
    assert body["abstain_reason"] == "below_threshold"
    assert body["answer"] == "I could not find this in the City Tech sources I have."
    assert body["citations"] == []  # an abstention cites nothing
    card = body["contact"]
    assert (
        card["office"] == "CST-NYT" and card["name"] == "the Computer Systems Technology department"
    )
    assert card["emails"] == [{"address": "compsystech@citytech.cuny.edu", "for": None}]
    assert card["phones"] == ["718-260-5170"] and card["note"] is None
    assert len(body["how_found"]["retrieved"]) == 7  # what was retrieved is still shown


@pytest.mark.parametrize(
    ("question", "chunk"),
    [
        ("what questions can I ask you", "page/MATH-NYT/faqs#12"),
        ("my mom died", "page/financial-aid/faqs#9"),
        ("Should I take an Incomplete?", "page/registrar/incomplete#1"),
    ],
)
def test_an_abstention_with_no_clear_office_has_contact_null_and_no_contact_line(
    monkeypatch, question, chunk
):
    stub = retrieve_answer(THRESHOLD_ABSTAIN, True, "below_threshold", citations=())
    stub.sources[0]["id"] = chunk  # a low-similarity best chunk from an unrelated office
    r = ask(make_client_app(Client(), monkeypatch, stub), question)
    body = r.json()
    assert body["abstained"] and body["answer_type"] == "abstain" and body["contact"] is None
    assert body["answer"] == "I could not find this in the City Tech sources I have."
    assert body["abstain_reason"] == "below_threshold" and body["citations"] == []
    assert "Contact" not in body["answer"] and body["how_found"]["retrieved"]


def test_a_model_written_abstention_is_coded_model_and_gets_a_department_card(monkeypatch):
    stub = retrieve_answer("ABSTAIN: The sources do not list who teaches MAT 1475.", True,
                           "The sources do not list who teaches MAT 1475.", ())  # fmt: skip
    body = ask(make_client_app(Client(), monkeypatch, stub), "Who is teaching MAT 1475?").json()
    assert body["abstain_reason"] == "model" and body["contact"]["office"] == "MATH-NYT"
    assert body["answer"] == "The sources do not list who teaches MAT 1475."


def test_advisement_is_no_longer_attached_by_a_chunk_from_its_pages(monkeypatch):
    stub = retrieve_answer(THRESHOLD_ABSTAIN, True, "below_threshold", ())
    stub.sources[0]["id"] = "page/advisement/virtual-advisors#2"
    body = ask(
        make_client_app(Client(), monkeypatch, stub), "Apply to Architectural Technology?"
    ).json()
    assert body["contact"] is None and body["abstained"]


# ---- the calendar and chain routes ----


def test_a_calendar_answer_cites_its_rows_with_a_public_pdf_url_only_when_a_page_links_it(
    monkeypatch, tmp_path
):
    pages = tmp_path / "data" / "processed" / "pages" / "registrar"
    pages.mkdir(parents=True)
    links = [
        {"url": "https://www.citytech.cuny.edu/registrar/docs/fall_2026.pdf", "text": "Fall 2026"}
    ]
    (pages / "academic-calendar.json").write_text(json.dumps({"pdf_links": links}))
    client = Client("calendar", "Fall 2026", ["fall-2026-040"])
    body = ask(
        make_client_app(client, monkeypatch, tmp_root=tmp_path), "Last day to withdraw?"
    ).json()
    assert body["route"] == "calendar" and body["answer_type"] == "answer"
    cite = body["citations"][0]
    assert cite["doc_type"] == "calendar" and cite["file"] == "fall_2026.pdf"
    assert cite["url"] == "https://www.citytech.cuny.edu/registrar/docs/fall_2026.pdf"
    assert cite["term"] == "Fall 2026" and cite["last_updated"]
    hf = body["how_found"]
    assert hf["retrieved"] == [] and hf["calendar"]["selected"] == ["fall-2026-040"]
    assert hf["stages_ms"]["select"] is not None and hf["stages_ms"]["answer"] is None
    assert client.calls == ["classify", "select"]


def test_the_same_calendar_answer_has_no_url_when_no_page_links_the_file(monkeypatch, tmp_path):
    client = Client("calendar", "Fall 2026", ["fall-2026-040"])
    cite = ask(make_client_app(client, monkeypatch, tmp_root=tmp_path)).json()["citations"][0]
    assert cite["file"] == "fall_2026.pdf" and cite["url"] is None


def test_a_row_with_no_date_is_not_announced_and_keeps_the_registrar_line(monkeypatch):
    client = Client("calendar", "Spring 2027", ["spring-2027-055"])
    body = ask(make_client_app(client, monkeypatch), "When is commencement?").json()
    assert body["answer_type"] == "not_announced" and not body["abstained"]
    assert "not announced yet" in body["answer"] and "Contact the Registrar" in body["answer"]
    assert body["contact"] is None


def test_a_calendar_abstention_has_one_registrar_card_and_no_sentence(monkeypatch):
    client = Client("calendar", "Summer 2027", [])
    body = ask(make_client_app(client, monkeypatch), "When does Summer 2027 start?").json()
    assert body["abstained"] and body["route"] == "calendar"
    assert body["abstain_reason"].startswith("calendar_")
    assert body["contact"]["office"] == "registrar" and "Contact" not in body["answer"]
    assert not body["answer"].startswith("ABSTAIN")


def test_a_chain_answer_cites_course_records_without_any_url(monkeypatch):
    client = Client("prerequisite", answer="AA 1001 needs BB 1001 [1][2].")
    body = ask(make_client_app(client, monkeypatch), "What do I need before AA 1001?").json()
    assert body["route"] == "chain" and not body["abstained"]
    assert [c["id"] for c in body["citations"]] == ["catalog:AA 1001", "catalog:BB 1001"]
    assert all(c["url"] is None and c["file"] is None for c in body["citations"])
    assert body["citations"][0]["title"].startswith("City Tech course catalog: ")
    chain = body["how_found"]["chain"]
    assert chain["code"] == "AA 1001" and chain["course_count"] == 2 and chain["truncated"] is False
    assert body["how_found"]["stages_ms"]["walk"] is not None


def test_a_chain_with_no_record_abstains_with_the_department_card(monkeypatch):
    client = Client("prerequisite")
    body = ask(make_client_app(client, monkeypatch), "What do I need before CST 4999?").json()
    assert (
        body["route"] == "chain"
        and body["abstained"]
        and body["abstain_reason"] == "chain_no_record"
    )
    assert body["contact"]["office"] == "CST-NYT" and "Contact" not in body["answer"]
    assert body["answer"].startswith("No record exists in the catalog data for CST 4999")


def test_a_chain_no_record_outside_the_four_departments_has_no_contact(monkeypatch):
    body = ask(
        make_client_app(Client("prerequisite"), monkeypatch), "What do I need before ENG 1101?"
    ).json()
    assert body["route"] == "chain" and body["abstained"] and body["contact"] is None
    assert "Contact" not in body["answer"]


# ---- URL rules ----


def test_urls_come_only_from_the_chunk_page_or_a_page_that_links_the_file():
    urls = {"fall_2026.pdf": "https://www.citytech.cuny.edu/registrar/docs/fall_2026.pdf"}
    web = convert.citation(1, chunk("a"), True, urls, {})
    pdf_mapped = convert.citation(1, chunk("p", "data/pdfs/fall_2026.pdf"), True, urls, {})
    pdf_unmapped = convert.citation(1, chunk("q", "data/pdfs/other.pdf"), True, urls, {})
    course = convert.citation(
        1, chunk("catalog:CST 1", "catalog_course", kind="course"), True, urls, {}
    )
    assert web.url == PAGE and web.file is None
    assert pdf_mapped.url == urls["fall_2026.pdf"] and pdf_mapped.file == "fall_2026.pdf"
    assert pdf_unmapped.url is None and pdf_unmapped.file == "other.pdf"
    assert course.url is None and course.file is None


def test_the_url_map_uses_only_https_links_on_the_city_tech_host_and_decodes_names(tmp_path):
    d = tmp_path / "registrar"
    d.mkdir()
    links = [
        {"url": "https://www.citytech.cuny.edu/registrar/docs/a%20b.pdf", "text": ""},
        {"url": "http://www.citytech.cuny.edu/registrar/docs/insecure.pdf", "text": ""},
        {"url": "https://other.example.org/x/outside.pdf", "text": ""},
    ]
    (d / "p.json").write_text(json.dumps({"pdf_links": links}))
    assert convert.build_url_map(tmp_path) == {
        "a b.pdf": "https://www.citytech.cuny.edu/registrar/docs/a%20b.pdf"
    }


# ---- errors ----


def error_ok(r, status, code):
    body = r.json()
    assert r.status_code == status and body["error"]["code"] == code
    assert body["request_id"] == r.headers["X-Request-ID"]
    return body


def test_empty_or_too_long_questions_are_422_without_echoing_the_input(monkeypatch):
    c = make_client_app(Client(), monkeypatch, retrieve_answer())
    error_ok(c.post("/ask", json={"question": "   "}), 422, "invalid_question")
    long = "x" * 501
    body = error_ok(c.post("/ask", json={"question": long}), 422, "invalid_question")
    assert long not in json.dumps(body)
    assert c.post("/ask", json={"question": "x" * 500}).status_code == 200


def test_a_bad_body_is_422_and_a_large_body_is_413(monkeypatch):
    c = make_client_app(Client(), monkeypatch, retrieve_answer())
    error_ok(c.post("/ask", json={"q": "x"}), 422, "invalid_request")
    error_ok(
        c.post("/ask", content=b"not json", headers={"content-type": "application/json"}),
        422,
        "invalid_request",
    )
    error_ok(c.post("/ask", json={"question": "x" * 5000}), 413, "too_large")


def test_a_provider_failure_is_502_with_no_provider_text(monkeypatch):
    c = make_client_app(Client(), monkeypatch, retrieve_answer())

    def fail(*a, **k):
        raise ApiError("chat request failed: 401 sk-secret-key quota")

    monkeypatch.setattr(build, "answer", fail)
    r = ask(c)
    body = error_ok(r, 502, "provider_error")
    assert "sk-secret" not in r.text and "401" not in r.text and body["error"]["message"]


def test_a_database_failure_is_503_and_an_unexpected_error_is_500_with_a_generic_message(
    monkeypatch,
):
    def broken():
        raise psycopg.OperationalError("connection to server at 10.0.0.5 failed")

    r = ask(make_client_app(Client(), monkeypatch, retrieve_answer(), connect=broken))
    error_ok(r, 503, "unavailable")
    assert "10.0.0.5" not in r.text
    c = make_client_app(Client(), monkeypatch, retrieve_answer())

    def boom(*a, **k):
        raise RuntimeError("secret trace /home/x")

    monkeypatch.setattr(build, "answer", boom)
    r = ask(c)
    error_ok(r, 500, "internal_error")
    assert "secret" not in r.text and "/home" not in r.text


def test_unknown_paths_and_methods_use_the_error_envelope(monkeypatch):
    c = make_client_app(Client(), monkeypatch, retrieve_answer())
    error_ok(c.get("/nope"), 404, "not_found")
    error_ok(c.get("/ask"), 405, "method_not_allowed")


# ---- date, logging, no model call ----


def test_the_date_is_the_server_date_unless_the_config_overrides_it(monkeypatch):
    c = make_client_app(Client(), monkeypatch, retrieve_answer(), clock=lambda: date(2030, 1, 2))
    assert ask(c).json()["meta"]["today"] == "2030-01-02"
    cfg = cfg_for(today=date(2026, 10, 11))
    c = make_client_app(
        Client(), monkeypatch, retrieve_answer(), cfg=cfg, clock=lambda: date(2030, 1, 2)
    )
    assert ask(c).json()["meta"]["today"] == "2026-10-11"


def test_the_router_is_called_without_writing_a_log_row_in_this_step(monkeypatch):
    seen = []

    class Spy:
        def answer(self, question, today, run_id=None, log=True):
            seen.append((question, today, log))
            return Router(None, cfg_for(), lambda: Client(), events=EVENTS).answer(
                question, today, log=False
            )

    monkeypatch.setattr(build, "answer", lambda *a, **k: retrieve_answer())
    app = api_app.create_app(
        cfg_for(), connect=ok_connect, check_startup=False,
        router_factory=lambda conn, cfg: Spy(), clock=lambda: TODAY,
    )  # fmt: skip
    assert TestClient(app).post("/ask", json={"question": "  hello  "}).status_code == 200
    assert seen == [("hello", TODAY, False)]  # the question is stripped; log=False


# ---- personal-account abstentions (step 4b) ----


def test_a_retrieval_abstention_on_an_account_question_is_coded_personal_account(monkeypatch):
    stub = retrieve_answer(THRESHOLD_ABSTAIN, True, "below_threshold", ())
    body = ask(make_client_app(Client(), monkeypatch, stub), "What is my GPA this semester?").json()
    assert body["abstained"] and body["abstain_reason"] == "personal_account"
    assert body["contact"]["office"] == "registrar"  # the contact the mapping already chose
    assert "personal" not in body["answer"] and body["citations"] == []


def test_a_model_written_abstention_on_an_account_question_gets_the_code_not_the_sentence(
    monkeypatch,
):
    stub = retrieve_answer("ABSTAIN: The sources do not show your balance.", True,
                           "The sources do not show your balance.", ())  # fmt: skip
    body = ask(make_client_app(Client(), monkeypatch, stub), "What is my balance?").json()
    assert body["abstain_reason"] == "personal_account" and body["contact"]["office"] == "bursar"
    assert "balance" not in body["abstain_reason"]


def test_a_normal_abstention_does_not_get_the_account_code(monkeypatch):
    stub = retrieve_answer(THRESHOLD_ABSTAIN, True, "below_threshold", ())
    body = ask(
        make_client_app(Client(), monkeypatch, stub), "Are there open seats in CST 1101?"
    ).json()
    assert body["abstain_reason"] == "below_threshold" and body["contact"]["office"] == "CST-NYT"
    model = retrieve_answer("ABSTAIN: Nothing.", True, "Nothing.", ())
    body = ask(make_client_app(Client(), monkeypatch, model), "Who teaches MAT 1475?").json()
    assert body["abstain_reason"] == "model"


def test_calendar_and_chain_abstentions_keep_their_own_codes_even_with_an_account_word(monkeypatch):
    client = Client("calendar", "Summer 2027", [])
    body = ask(make_client_app(client, monkeypatch), "When is my refund in Summer 2027?").json()
    assert body["abstain_reason"].startswith("calendar_")


def test_an_answered_account_word_question_is_not_touched(monkeypatch):
    body = ask(make_client_app(Client(), monkeypatch, retrieve_answer()),
               "When is my tuition bill due this fall?").json()  # fmt: skip
    assert not body["abstained"] and body["abstain_reason"] is None


def test_abstain_code_unit():
    t = convert.contacts.load_contacts()
    assert convert.abstain_code(None, "my gpa", t) is None
    assert convert.abstain_code("below_threshold", "my gpa", t) == "personal_account"
    assert convert.abstain_code("below_threshold", "the gpa", t) == "below_threshold"
    assert convert.abstain_code("some sentence", "my transcript", t) == "personal_account"
    assert convert.abstain_code("some sentence", "hello", t) == "model"
    assert convert.abstain_code("chain_no_record", "my gpa", t) == "chain_no_record"


# ================= request logging (step 5) =================

import logging  # noqa: E402

from cta.api import requestlog  # noqa: E402

ALLOWED_COLUMNS = set(requestlog.COLUMNS) - {"source"}  # `source` is added by the writer ('api')


def test_an_answered_request_writes_one_row_with_the_redacted_text_and_the_numbers(monkeypatch):
    c = make_client_app(Client(), monkeypatch, retrieve_answer())
    r = ask(c, "My email is jane.doe@example.com, how do I apply for graduation?")
    assert r.status_code == 200 and len(c.logs) == 1
    row = c.logs[0]
    assert set(row) <= ALLOWED_COLUMNS  # no ip, user agent, cookie or other identifier column
    assert row["request_id"] == r.json()["request_id"] and row["status"] == "ok"
    assert "jane.doe@example.com" not in row["question"] and "[EMAIL]" in row["question"]
    assert row["answer"] == "Yes. [1]" and row["route"] == "retrieve" and row["abstained"] is False
    assert row["chat_model"] == "gpt-6-luna" and row["today"] == "2026-10-11"
    assert row["prompt_tokens"] == 400 and row["embedding_tokens"] == 7
    assert row["cost_usd"] == r.json()["how_found"]["cost_usd"]["total"] > 0
    assert (
        row["latency_ms"] > 0 and row["query_cache_hit"] is True and row["contact_office"] is None
    )
    assert row["retrieved"][0] == {"id": "page/registrar/faqs#3", "similarity": 0.6}
    trace = row["trace"]
    assert trace["answer_type"] == "answer" and trace["route"] == "retrieve"
    assert trace["stages_ms"]["rerank"] == 11.0 and len(trace["retrieved"]) == 7
    assert "Some text here" not in json.dumps(trace)  # ids and numbers only, no chunk text


def test_an_abstention_row_has_the_code_the_office_and_the_answer_without_the_contact_line(
    monkeypatch,
):
    stub = retrieve_answer(THRESHOLD_ABSTAIN, True, "below_threshold", citations=())
    c = make_client_app(Client(), monkeypatch, stub)
    ask(c, "Are there open seats in CST 1101?")
    row = c.logs[0]
    assert row["abstained"] is True and row["abstain_reason"] == "below_threshold"
    assert row["contact_office"] == "CST-NYT" and row["trace"]["answer_type"] == "abstain"
    assert row["answer"] == "I could not find this in the City Tech sources I have."
    assert row["status"] == "ok"


def test_a_not_announced_row(monkeypatch):
    client = Client("calendar", "Spring 2027", ["spring-2027-055"])
    c = make_client_app(client, monkeypatch)
    ask(c, "When is commencement?")
    row = c.logs[0]
    assert row["trace"]["answer_type"] == "not_announced" and row["route"] == "calendar"
    assert row["abstained"] is False and row["trace"]["calendar"]["selected"] == ["spring-2027-055"]
    assert row["retrieved"] == [{"id": "spring-2027-055"}]  # a calendar row, not a chunk


def test_error_rows_carry_the_status_and_no_answer(monkeypatch):
    c = make_client_app(Client(), monkeypatch, retrieve_answer())

    def fail(*a, **k):
        raise ApiError("provider text sk-secret")

    monkeypatch.setattr(build, "answer", fail)
    assert ask(c, "Where is my GPA, jane@x.edu?").status_code == 502
    row = c.logs[0]
    assert row["status"] == "provider_error" and row["answer"] is None and row["route"] is None
    assert "jane@x.edu" not in row["question"] and row["trace"] == {"error": "provider_error"}
    assert "sk-secret" not in json.dumps(row, default=str)

    def boom(*a, **k):
        raise RuntimeError("secret trace")

    monkeypatch.setattr(build, "answer", boom)
    assert ask(c, "q").status_code == 500
    assert c.logs[1]["status"] == "internal_error" and "secret" not in json.dumps(c.logs[1])


def test_a_rejected_question_logs_only_its_length(monkeypatch):
    c = make_client_app(Client(), monkeypatch, retrieve_answer())
    assert c.post("/ask", json={"question": "x" * 501}).status_code == 422
    row = c.logs[0]
    assert row["status"] == "invalid_question" and row["question"] == ""
    assert row["trace"] == {"error": "invalid_question", "chars": 501}
    assert c.post("/ask", json={"question": "   "}).status_code == 422
    assert c.logs[1]["trace"]["chars"] == 0
    assert len(c.logs) == 2  # a malformed body or an oversized body writes nothing


def test_a_failing_log_write_never_fails_the_request_and_is_counted(monkeypatch, caplog):
    def broken(conn, record):
        raise RuntimeError("insert failed for question: my secret question text")

    c = make_client_app(Client(), monkeypatch, retrieve_answer(), log_writer=broken)
    with caplog.at_level(logging.WARNING, logger="cta.api"):
        r = ask(c, "my secret question text")
    assert r.status_code == 200 and r.json()["answer"] == "Yes. [1]"
    assert c.get("/health").json()["log_failures"] == 1
    assert [m.getMessage() for m in caplog.records] == [requestlog.WARNING]
    assert "secret" not in caplog.text and "question text" not in caplog.text
    ask(c, "again")
    assert c.get("/health").json()["log_failures"] == 2


def test_a_database_outage_is_counted_as_an_unlogged_request(monkeypatch):
    def broken():
        raise psycopg.OperationalError("down")

    c = make_client_app(Client(), monkeypatch, retrieve_answer(), connect=broken)
    assert ask(c).status_code == 503 and c.logs == []
    health = c.get("/health")
    assert health.status_code == 503 and health.json()["log_failures"] == 1


def test_a_login_question_is_a_personal_account_abstention_with_no_card(monkeypatch):
    stub = retrieve_answer(THRESHOLD_ABSTAIN, True, "below_threshold", citations=())
    stub.sources[0]["id"] = "page/DENT-NYT/faq#2"  # an unrelated best chunk
    c = make_client_app(Client(), monkeypatch, stub)
    body = ask(c, "I can't log in to CUNYfirst with my email address").json()
    assert body["abstained"] and body["abstain_reason"] == "personal_account"
    assert body["contact"] is None and body["answer_type"] == "abstain"


# ---- fields the "How this was found" panel reads ----


def test_the_pool_chunks_carry_their_title_for_the_panel(monkeypatch):
    hf = ask(make_client_app(Client(), monkeypatch, retrieve_answer())).json()["how_found"]
    assert all(c["title"] == "FAQ > Question" for c in hf["retrieved"])


def test_a_course_chunk_title_has_the_catalog_prefix():
    chunk_ = chunk("catalog:CST 1", "catalog_course", kind="course", heading_path="CST 1 - Intro")
    assert convert.pool_title(chunk_) == "City Tech course catalog: CST 1 - Intro"
    assert convert.pool_title({"id": "x"}) is None


def test_the_chain_block_names_the_courses_without_a_record(monkeypatch):
    client = Client("prerequisite", answer="AA 1001 needs BB 1001 [1][2].")
    body = ask(make_client_app(client, monkeypatch), "What do I need before AA 1001?").json()
    assert body["how_found"]["chain"]["no_record_codes"] == ["ENG 1101"]
