"""Fakes and builders shared by the test files, so that no test file imports another one."""

import functools
import json
import re
import tempfile
import time
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from langsmith import Client as LangsmithClient

from cta.answer import Answer
from cta.api import app as api_app
from cta.api import tracing
from cta.eval.questions import load_questions
from cta.graph import build, render
from cta.graph import chain as ch
from cta.graph import chain as chains
from cta.graph import chain_render as cr
from cta.graph.build import Router
from cta.graph.state import RoutedAnswer
from cta.index.db import migration_files
from cta.index.rerank import Rerank
from cta.index.search import Search
from cta.parse.html import parse_page
from cta.settings import ROOT, load_models

# ---- from test_api ----

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
            else "language" if system.startswith("You detect the language")
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
            # round 1b: a short English question may reach the language step; "en" means no change
            "language": json.dumps({"language": "en", "english": "x", "note": ""}),
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


# An empty folder as the repo root, so the kill-switch file and the page records are never read
# from the real checkout; a test that needs real records passes tmp_root=ROOT.
guard_class = api_app.guard_mod.Guard


EMPTY_ROOT = Path(tempfile.mkdtemp(prefix="cta-test-root-"))


FIXED_NOW = datetime(2026, 10, 11, 15, 0, tzinfo=UTC)  # the guard's day and minute windows


def make_client_app(client, monkeypatch, stub=None, cfg=None, tmp_root=None, connect=ok_connect,
                    clock=lambda: TODAY, log_writer=None, feedback_writer=None,
                    env=None, headers=None):  # fmt: skip
    cfg = cfg or cfg_for()
    if stub is not None:
        monkeypatch.setattr(build, "answer", lambda *a, **k: stub)
    monkeypatch.setattr(chains, "load_records", lambda *a, **k: WORLD)
    # the guard reads the real clock by default; pin it so day and minute windows cannot drift
    pinned = functools.partial(guard_class, now=lambda: FIXED_NOW, monotonic=lambda: 1000.0)
    monkeypatch.setattr(api_app.guard_mod, "Guard", pinned)

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
                             root=tmp_root or EMPTY_ROOT, clock=clock, log_writer=writer,
                             feedback_writer=feedback_writer or vote_writer,
                             client_factory=lambda: client,
                             env={} if env is None else env)  # fmt: skip
    test_client = TestClient(app, raise_server_exceptions=False, headers=headers)
    test_client.logs, test_client.votes = logs, votes
    return test_client


def ask(client, question="How do I apply for graduation?"):
    return client.post("/ask", json={"question": question})


# ---- from test_guard ----

DEFAULTS = load_models(env={})["guardrails"]


def settings(**over):
    return {**DEFAULTS, **over}


def req(host="1.2.3.4"):
    return SimpleNamespace(client=SimpleNamespace(host=host))


class SpendConn:
    """A connection whose only job is to answer the spend query with a fixed sum."""

    def __init__(self, total=0.0, fail=False):
        self.total, self.fail, self.queries = total, fail, []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        if self.fail:
            raise ConnectionError("boom")
        self.queries.append((sql, params))
        return SimpleNamespace(fetchone=lambda: (self.total,))


def cfg_guard(**over):
    cfg = cfg_for()
    cfg["guardrails"] = {**cfg["guardrails"], **over}
    return cfg


# ---- from test_router ----

ROUTER_CFG = load_models(
    env={
        "CTA_RERANK": "off",
        "CTA_ROUTER_MODE": "on",
        "CTA_ROUTER_SELECTOR": "1",
        "CTA_ROUTER_CHAIN": "off",
        "CTA_ROUTER_CONTACTS": "off",
    }
)


def routed_ans(rows=(), route="calendar", abstained=False):
    ans = RoutedAnswer("t", abstained, None, [], search=Search([], False, 0, 0, 0.0))
    ans.row_ids, ans.route = list(rows), route
    return ans


class Script:
    """A chat client with fixed replies for the classifier, the selector and the answerer."""

    def __init__(
        self, intent="calendar", mention=None, row_ids=(), selector_text=None, answer="ok [1]"
    ):
        self.intent, self.mention, self.row_ids = intent, mention, list(row_ids)
        self.selector_text, self.answer_text, self.calls = selector_text, answer, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kw):
        system = kw["messages"][0]["content"]
        which = "classify" if system.startswith("You route") else "select" if system.startswith(
            "You choose") else "answer"  # fmt: skip
        self.calls.append(which)
        reply = {
            "classify": json.dumps({"intent": self.intent, "term_mention": self.mention}),
            "select": self.selector_text or json.dumps({"row_ids": self.row_ids}),
            "answer": self.answer_text,
        }[which]
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=10)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply))], usage=usage
        )


def make_router(script, monkeypatch, events, cfg=ROUTER_CFG):
    stub = Answer(
        "old path [1]", False, None, [{"id": "c1"}], [1], [], Search([], False, 0, 0, 0.0)
    )
    seen = []
    monkeypatch.setattr(build, "answer", lambda *a, **k: seen.append((a, k)) or stub)
    return Router(None, cfg, lambda: script, events=events, contact="registrar@x.edu"), seen


# ---- from test_clarify ----

DEV = [q for q in load_questions() if q["split"] == "dev"]


CLARIFY_CFG = load_models(
    env={"CTA_RERANK": "off", "CTA_ROUTER_MODE": "on", "CTA_ROUTER_CHAIN": "on"}
)


def stored_intents() -> list[tuple[str, str]]:
    """(question text, intent) for every stored dev answer that carries a router record."""
    text = {q["id"]: q["question"] for q in DEV}
    out = []
    for path in sorted((ROOT / "eval" / "results").glob("*.json")):
        run = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(run, dict) or run.get("split") != "dev":
            continue
        for r in run.get("per_question", []):
            intent = (r.get("router") or {}).get("intent")
            if intent and r["id"] in text:
                out.append((text[r["id"]], intent))
    return out


# ---- from test_chain ----

def rec(code, text="", style=None, title=None, dept="CST-NYT"):
    return {
        "code": code, "title": title or f"Title of {code}", "credits": 3,
        "description": f"About {code}.", "prerequisite_text": text,
        "prereq_style": style or ("text" if text else "none"), "rule_id": None,
        "course_group_id": "1", "department": dept, "department_name": "Dept",
        "fetched_at": "x", "programs": [],
    }  # fmt: skip


def recs(*records):
    return {r["code"]: r for r in records}


WORLD = recs(
    rec("AA 1001", "PRE: BB 1001"),
    rec("BB 1001", "PRE: ENG 1101"),
    rec("DD 1001", "PRE_X", "shorthand"),
    rec(
        "CST 1001", ""
    ),  # a CST prefix is in the data, so CST 4999 is "no record", not "outside" (item D)
)


# ---- from test_chain_render ----

HEADING = re.compile(r"^### (.+?) — (.+?) \[(\d+)\]$", re.M)


CFG_CODE = load_models(
    env={
        "CTA_RERANK": "off",
        "CTA_ROUTER_MODE": "on",
        "CTA_ROUTER_CHAIN": "on",
        "CTA_ROUTER_CONTACTS": "off",
        "CTA_ROUTER_CHAIN_RENDER": "code",
    }  # fmt: skip
)


CFG_MODEL = load_models(
    env={
        "CTA_RERANK": "off",
        "CTA_ROUTER_MODE": "on",
        "CTA_ROUTER_CHAIN": "on",
        "CTA_ROUTER_CONTACTS": "off",
        "CTA_ROUTER_CHAIN_RENDER": "model",
    }  # fmt: skip
)


def route(cfg, client, monkeypatch, question="What are the prerequisites for CST 3504?"):
    stub = Answer("old path [1]", False, None, [], [1], [], Search([], False, 0, 0, 0.0))
    monkeypatch.setattr(build, "answer", lambda *a, **k: stub)
    router = Router(None, cfg, lambda: client, events=[], contact="c")
    return router.answer(question, build.date(2026, 10, 13), log=False)


# ---- from test_chunks ----

PROCESSED_FIXTURES = Path(__file__).parent / "fixtures" / "processed"


def words(text: str) -> int:  # token counter without tiktoken or network
    return len(text.split())


# ---- from test_outside_marking ----

RECORDS = ch.load_records()


PREFIXES = ch.known_prefixes(RECORDS)


MARK = re.compile(r"\b([A-Z]{2,5}) (\w+) \(no catalog record\)")


ASKED = re.compile(
    r"There is no catalog record for (\S+ \S+) "
    r"in the four departments \(CST, Math, EET, Dental Hygiene\)\."
)


def outside_rewrite(old: str) -> str:
    """What the new render must equal: only the marking of outside-prefix codes rewritten."""
    text = MARK.sub(
        lambda m: (
            m.group(0) if m.group(1) in PREFIXES else f"{m.group(1)} {m.group(2)} ({cr.OUTSIDE})"
        ),
        old,
    )
    return ASKED.sub(
        lambda m: (
            m.group(0) if m.group(1).split()[0] in PREFIXES else ch.outside_sentence(m.group(1))
        ),
        text,
    )


# ---- from test_parse_html ----

PAGES = Path(__file__).parent / "fixtures" / "pages"


HOST = "https://www.citytech.cuny.edu"


def parse(name: str, path: str = "/x.aspx", kind: str = "office", owner: str = "bursar") -> dict:
    meta = {
        "source_url": HOST + path, "final_url": HOST + path,
        "fetched_at": "2026-10-11T00:00:00+00:00", "content_hash": "abc",
        "http_status": 200, "kind": kind, "owner": owner,
    }  # fmt: skip
    html = (
        (PAGES / f"{name}.html").read_bytes()
        if (PAGES / f"{name}.html").exists()
        else name.encode()
    )
    return parse_page(html, meta)


# ---- from test_parse_pages ----


def entry(path, name, kind="office", owner="bursar", status=200, error=""):
    return {
        "url": HOST + path, "kind": kind, "owner": owner, "status": status, "error": error,
        "final_url": HOST + path if status else None,
        "saved_as": f"raw/{name}.html" if name else None,
        "content_hash": "h" if status else None, "fetched_at": "2026-10-11T00:00:00+00:00",
    }  # fmt: skip


# ---- from test_requestlog ----

def insert(conn, source, days_old, rid=None):
    conn.execute(
        "INSERT INTO request_logs (source, question, ts, request_id) "
        "VALUES (%s, 'q', now() - make_interval(days => %s), %s)",
        (source, days_old, rid),
    )


def notice_text() -> str:
    from cta.settings import ROOT

    return (ROOT / "web" / "lib" / "notice.ts").read_text(encoding="utf-8")


# ---- from test_run_answers ----

def stored_chunk(source_id, merged=(), sim=0.7):
    return {"id": source_id, "source_id": source_id, "merged_section_ids": list(merged),
            "similarity": sim, "kind": "section", "source": "https://x", "heading_path": "H",
            "terms": [], "last_updated": None, "text": "body"}  # fmt: skip


def top(*ids):
    return [stored_chunk(i) for i in ids] + [stored_chunk(f"f{n}") for n in range(10 - len(ids))]


class FakeSearch:
    cache_hit = False
    cost = 0.0
    total_cost = 0.0


def ans(text="The deadline is Nov 6 [1].", abstained=False, cost=0.0002, sources=None, **kw):
    a = Answer(
        text,
        abstained,
        "r" if abstained else None,
        sources or top("g")[:5],
        citations=kw.get("citations", [1]),
        invalid_citations=kw.get("invalid", []),
    )
    a.search, a.chat_cost, a.latency_ms, a.chat_ms = FakeSearch(), cost, 1200, 900
    return a


def question(qid="q1", gold="Nov 6", sources=("g",), qtype="lookup"):
    return {"id": qid, "question": "When?", "gold_answer": gold, "type": qtype, "department": None,
            "gold_sources": [{"id": s} for s in sources]}  # fmt: skip


# ---- from test_search ----

SEARCH_CFG = load_models(
    env={"CTA_RERANK": "off", "CTA_ROUTER_MODE": "off"}
)  # the reranker has its own tests


DIM = SEARCH_CFG["embedding_dimensions"]


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


# ---- from test_answer ----

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


# ---- from test_topic ----

def reply(topic_text, in_scope):
    return json.dumps({"topic": topic_text, "in_scope": in_scope})


# ---- from test_tracing ----

KEY = "lsv2_pt_THISISAFAKEKEYFORTESTS0123456789"


class Resp:
    status_code = 200
    text = "{}"
    headers: dict = {}
    content = b"{}"
    ok = True

    def json(self):
        return {}

    def raise_for_status(self):
        pass


class FakeSession:
    """Records every request the langsmith client would make; sends nothing."""

    def __init__(self):
        self.calls = []

    def request(self, method, url, **kw):
        body = kw.get("data") or kw.get("json") or b""
        if not isinstance(body, bytes | str):
            body = json.dumps(body, default=str)
        self.calls.append(
            (method, url, body if isinstance(body, str) else body.decode("utf-8", "replace"))
        )
        return Resp()

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, **kw):
        return self.request("POST", url, **kw)

    def patch(self, url, **kw):
        return self.request("PATCH", url, **kw)

    def close(self):
        pass

    def mount(self, *a, **k):
        return None

    @property
    def everything(self) -> str:
        return "\n".join(f"{m} {u} {b}" for m, u, b in self.calls)


def fake_tracing():
    session = FakeSession()
    client = LangsmithClient(
        api_key="k", api_url="http://fake.local", session=session, auto_batch_tracing=False,
        hide_inputs=tracing.scrub_payload, hide_outputs=tracing.scrub_payload,
        hide_metadata=tracing.scrub_payload, omit_traced_runtime_info=True, info={},
    )  # fmt: skip
    return tracing.Tracing(client, "test-project"), session


def app_with(monkeypatch, tracer, client=None, cfg=None, stub=None):
    monkeypatch.setattr(tracing.Tracing, "from_settings", classmethod(lambda cls, c, e: tracer))
    client = client or Client("calendar", "Fall 2026", ["fall-2026-040"])
    return make_client_app(client, monkeypatch, stub, cfg=cfg)


def trace_complete(calls, root="ask") -> bool:
    """True when the run named `root` was POSTed (the SDK posts runs from background threads in no
    fixed order, so the expected root must be waited for by name) and every POSTed run was also
    PATCHed (its end was sent)."""
    posted, roots = set(), set()
    for method, _url, body in calls:
        if method != "POST":
            continue
        try:
            run = json.loads(body)
        except ValueError:
            continue
        if isinstance(run, dict) and run.get("id"):
            posted.add(run["id"])
            if run.get("name") == root:
                roots.add(run["id"])
    patched = {url.rsplit("/", 1)[-1] for method, url, _ in calls if method == "PATCH"}
    return bool(posted) and bool(roots) and posted <= patched


def flush(tracer, session=None, expect=True, root="ask"):
    """Make the captured traffic complete. `client.flush()` drains the SDK's own queue; the runs
    themselves are posted from background threads, so then wait for an explicit condition: with
    `expect` (a trace is supposed to exist) every run that was POSTed has also been PATCHed (its end
    was sent), and at least one was. Bounded by a hard timeout so a missing trace fails the
    assertion that follows instead of hanging. `expect=False`: nothing was traced by design, so
    nothing can be in flight and no wait is needed."""
    tracer.client.flush()
    session = session or tracer.client.session
    if not expect:
        return
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if trace_complete(list(session.calls), root):
            return
        time.sleep(0.01)


# ---- the plain chat fake ----


class Model:
    """A chat client that always replies with `content` (10 prompt and 5 completion tokens)."""

    def __init__(self, content):
        self.content = content
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kw):
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
        msg = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=usage)
