"""The router graph (step 4a): classify -> calendar | retrieve, and calendar -> retrieve when no row
answers. Built with LangGraph.

    START -> classify --calendar--> calendar --(row found, or abstained)--> END
                 |                       |
                 +--other-----------> retrieve <--(valid empty selection)--+
                                         |
                                         v
                                        END

The retrieve node calls the existing pipeline (cta.answer.answer) unchanged. With router.mode "off"
answer_question calls it directly and the graph is never built.
"""

import json
import time
from dataclasses import dataclass
from datetime import date

from langgraph.graph import END, START, StateGraph

from cta.answer import Answer, answer, call_chat, parse_reply
from cta.graph import chain as chains
from cta.graph import chain_render, render, select, terms
from cta.graph import classify as classifier
from cta.graph import contact as contacts
from cta.graph.state import RoutedAnswer, RouterState
from cta.index.embed import make_client
from cta.index.search import Search
from cta.redact import redact
from cta.settings import ROOT, answer_model, cost_usd
from cta.validate.calendar import load_events_for_indexing

EVENTS_FILE = ROOT / "data" / "calendar" / "calendar_events.json"  # the file load_calendar.py loads


def load_events() -> list[dict]:
    """The verified calendar rows (the same function that fills the calendar_events table)."""
    return load_events_for_indexing(EVENTS_FILE)


@dataclass
class Deps:
    conn: object
    cfg: dict
    client_factory: object
    events: list[dict]
    contact: str
    log: bool = True


def call_numbers(call) -> dict:
    return {
        "prompt_tokens": call.prompt_tokens, "completion_tokens": call.completion_tokens,
        "cost": call.cost, "ms": round(call.ms, 1), "error": call.error,
    }  # fmt: skip


def calendar_answer(rendered: render.Rendered) -> RoutedAnswer:
    """The calendar route's answer: the rendered rows, cited [1], [2] ..., from the row sources."""
    ans = RoutedAnswer(
        rendered.text, False, None, rendered.sources, list(range(1, len(rendered.sources) + 1)),
        search=Search([], False, 0, 0, 0.0),
    )  # fmt: skip
    ans.row_ids = rendered.row_ids
    return ans


def abstain_answer(text: str, reason: str) -> RoutedAnswer:
    return RoutedAnswer(text, True, reason, [], search=Search([], False, 0, 0, 0.0))


# ---- nodes ----


def make_nodes(d: Deps):
    def classify_node(state: RouterState) -> dict:
        client = d.client_factory()
        result = classifier.classify(client, d.cfg, state["question"])
        info = call_numbers(result.call) | {"failed": result.failed}
        return {"intent": result.intent, "term_mention": result.term_mention, "classify": info}

    def after_classify(state: RouterState) -> str:
        if state["intent"] == "prerequisite":
            return "chain"
        return "calendar" if state["intent"] == "calendar" else "retrieve"

    def calendar_node(state: RouterState) -> dict:
        resolution = terms.resolve_term(state["term_mention"], state["today"], d.events)
        label = resolution.term or resolution.label
        info = {"term_status": resolution.status, "term": label, "invalid_ids": 0,
                "weekday_mismatches": 0, "selected": [], "select": None}  # fmt: skip
        if resolution.status == "unsupported":
            pool = resolution.pool
            if not pool:
                text = (
                    f"There is no published calendar for {label}, and no calendar row mentions it."
                )
                ans = abstain_answer(
                    render.abstain_text(text, d.contact), "calendar_unsupported_term"
                )
                return {"calendar": info, "answer": ans, "fallthrough": False, "route": "abstain"}
            version = 1  # the unsupported-term path keeps the 4a selector
        else:
            version = d.cfg["router"].get("selector", 1)
            pool = (
                terms.all_rows_pool(d.events)
                if version == 2
                else terms.term_pool(d.events, resolution.term)
            )
        client = d.client_factory()
        chosen = select.select_rows(
            client, d.cfg, state["question"], state["today"], label, pool, version
        )
        info["selector_version"] = version
        info["pool_size"] = len(pool)
        info["select"] = call_numbers(chosen.call) | {"status": chosen.status}
        info["invalid_ids"] = len(chosen.invalid_ids)
        if chosen.status == "empty" and resolution.status != "unsupported":
            return {"calendar": info, "fallthrough": True}  # nothing in the calendar answers it
        if chosen.status != "ok":
            reason = "calendar_selector_failed" if chosen.status == "failed" else "calendar_no_row"
            text = f"I could not find that in the {label} calendar."
            ans = abstain_answer(render.abstain_text(text, d.contact), reason)
            return {"calendar": info, "answer": ans, "fallthrough": False, "route": "abstain"}
        by_id = {r["id"]: r for r in pool}
        started = time.perf_counter()
        assumed = resolution.term if resolution.status == "assumed" else None
        rendered = render.render_rows([by_id[i] for i in chosen.row_ids], d.contact, assumed)
        info["render_ms"] = round((time.perf_counter() - started) * 1000, 3)
        info["weekday_mismatches"] = rendered.weekday_mismatches
        info["selected"] = rendered.row_ids
        info["tba_rows"] = rendered.tba_rows
        return {"calendar": info, "answer": calendar_answer(rendered), "fallthrough": False,
                "route": "calendar"}  # fmt: skip

    def after_calendar(state: RouterState) -> str:
        return "retrieve" if state.get("fallthrough") else END

    def chain_node(state: RouterState) -> dict:
        records = chains.load_records()
        found = chains.extract_course(state["question"], records)
        info = {"extraction": found.status, "code": found.code, "detail": found.detail}
        several = found.status == "codes"
        by_code = d.cfg["router"].get("chain_render", "model") == "code"
        if found.status not in ("code", "title", "codes") or (several and not by_code):
            info["fallthrough"] = True  # several courses have no model path: retrieval, as in 4b
            return {"chain": info, "chain_fallthrough": True}
        started = time.perf_counter()
        if several:
            result = chains.combined_chain(found.detail)
        else:
            result = chains.prerequisite_chain.invoke({"course_code": found.code})
        info["walk_ms"] = round((time.perf_counter() - started) * 1000, 3)
        if not result["found"]:
            text = chains.no_record_text(result["code"])
            info |= {"course_count": 0, "truncated": False, "no_record": True}
            ans = abstain_answer(text, "chain_no_record")
            return {"chain": info, "answer": ans, "route": "abstain"}
        sources = chains.sources_of(result, records)
        info |= {
            "course_count": result["course_count"], "truncated": result["truncated"],
            "unexpanded": result["unexpanded"], "dropped": result["dropped"],
            "no_record_codes": result["no_record"], "source_ids": [s["id"] for s in sources],
        }  # fmt: skip
        if d.cfg["router"].get("chain_render", "model") == "code":
            try:  # plain code writes the whole answer: no model call after the classifier
                text = chain_render.render(result, records)
            except chain_render.ChainRenderError:
                info["render_fallback"] = True  # a catalog text that is unsafe as markdown
                if several:  # no model path for several courses: retrieval
                    return {"chain": info, "chain_fallthrough": True}
            else:
                info["rendered_by"] = "code"
                ans = RoutedAnswer(
                    text, False, None, sources, list(range(1, len(sources) + 1)), [],
                    Search([], False, 0, 0, 0.0),
                )  # fmt: skip
                return {"chain": info, "answer": ans, "route": "chain"}
        messages = chains.build_messages(state["question"], state["today"], result, sources)
        chat_started = time.perf_counter()
        response = call_chat(d.client_factory(), d.cfg, messages)
        chat_ms = round((time.perf_counter() - chat_started) * 1000)
        text = (response.choices[0].message.content or "").strip()
        usage = response.usage
        parsed = parse_reply(text, len(sources))
        info |= {
            "chat_ms": chat_ms, "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
        }  # fmt: skip
        spent = cost_usd(d.cfg, d.cfg["chat_model"], usage.prompt_tokens, usage.completion_tokens)
        ans = RoutedAnswer(
            text, parsed["abstained"], parsed["reason"], sources, parsed["citations"],
            parsed["invalid"], Search([], False, 0, 0, 0.0), messages, usage.prompt_tokens,
            usage.completion_tokens, spent, 0, chat_ms,
        )  # fmt: skip
        return {"chain": info, "answer": ans, "route": "chain"}

    def after_chain(state: RouterState) -> str:
        return "retrieve" if state.get("chain_fallthrough") else END

    def retrieve_node(state: RouterState) -> dict:
        found = answer(
            d.conn, state["question"], state["today"], cfg=d.cfg,
            client_factory=d.client_factory, log=False, run_id=state.get("run_id"),
        )  # fmt: skip
        if state.get("chain_fallthrough"):
            route = "chain_fallthrough"
        else:
            route = "calendar_fallthrough" if state.get("fallthrough") else "other"
        return {"answer": found, "route": route}

    return (
        classify_node, after_classify, calendar_node, after_calendar, chain_node, after_chain,
        retrieve_node,
    )  # fmt: skip


def build_graph(d: Deps):
    """The compiled graph. Nodes close over the dependencies; the state carries the question."""
    (classify_node, after_classify, calendar_node, after_calendar, chain_node, after_chain,
     retrieve_node) = make_nodes(d)  # fmt: skip
    graph = StateGraph(RouterState)
    graph.add_node("classify", classify_node)
    graph.add_node("calendar", calendar_node)
    graph.add_node("chain", chain_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        after_classify,
        {"calendar": "calendar", "chain": "chain", "retrieve": "retrieve"},
    )
    graph.add_conditional_edges("chain", after_chain, {"retrieve": "retrieve", END: END})
    graph.add_conditional_edges("calendar", after_calendar, {"retrieve": "retrieve", END: END})
    graph.add_edge("retrieve", END)
    return graph.compile()


# ---- the entry point ----


def routed(found: Answer, state: RouterState, started: float, today: date) -> RoutedAnswer:
    """The final answer as a RoutedAnswer carrying the route and the router's own numbers. Model
    calls of the router are added to the answer's token counts and cost; its latency is the whole
    request (classify, select or retrieve, render)."""
    cal = state.get("calendar") or {}
    calls = [state["classify"]] + ([cal["select"]] if cal.get("select") else [])
    ans = RoutedAnswer(
        found.text, found.abstained, found.abstain_reason, found.sources, found.citations,
        found.invalid_citations, found.search, found.prompt,
        found.prompt_tokens + sum(c["prompt_tokens"] for c in calls),
        found.completion_tokens + sum(c["completion_tokens"] for c in calls),
        found.chat_cost + sum(c["cost"] for c in calls), 0,
        found.chat_ms + round(sum(c["ms"] for c in calls)),
    )  # fmt: skip
    ans.route, ans.today = state["route"], today
    ans.row_ids = found.row_ids if isinstance(found, RoutedAnswer) else []
    ans.router = {
        "route": state["route"], "intent": state["intent"], "term_mention": state["term_mention"],
        "classify": state["classify"], "fallthrough": bool(state.get("fallthrough")),
        "chain_fallthrough": bool(state.get("chain_fallthrough")),
        **{k: v for k, v in cal.items()},
        **({"chain": state["chain"]} if state.get("chain") else {}),
    }  # fmt: skip
    ans.latency_ms = round((time.perf_counter() - started) * 1000)
    return ans


def logged_model(ans: RoutedAnswer, cfg: dict) -> str:
    """The model that wrote the answer: answer_model for a retrieval answer, else chat_model."""
    return (
        answer_model(cfg)
        if ans.route not in ("calendar", "chain", "abstain")
        else cfg["chat_model"]
    )


def log_request(conn, question: str, ans: RoutedAnswer, cfg: dict, run_id: int | None) -> None:
    """One request_logs row with the route and router numbers; question and answer are redacted."""
    retrieved = [
        {"id": s["id"], "similarity": round(s.get("similarity", 0.0), 4)} for s in ans.sources
    ]
    conn.execute(
        "INSERT INTO request_logs (run_id, question, today, retrieved, answer, abstained, "
        "abstain_reason, chat_model, prompt_tokens, completion_tokens, embedding_tokens, cost_usd, "
        "latency_ms, query_cache_hit, route, router) "
        "VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
        (
            run_id, redact(question), ans.today, json.dumps(retrieved), redact(ans.text),
            ans.abstained, ans.abstain_reason and redact(ans.abstain_reason), logged_model(ans, cfg),
            ans.prompt_tokens, ans.completion_tokens, ans.search.tokens, ans.cost,
            ans.latency_ms, ans.search.cache_hit, ans.route, json.dumps(ans.router),
        ),
    )  # fmt: skip
    conn.commit()


class Router:
    """The compiled graph with its dependencies; one instance per run."""

    def __init__(self, conn, cfg: dict, client_factory=make_client, events=None, contact=None):
        self.deps = Deps(
            conn,
            cfg,
            client_factory,
            events if events is not None else load_events(),
            contact if contact is not None else render.registrar_contact(),
        )
        self.graph = build_graph(self.deps)

    def answer(self, question: str, today: date, run_id: int | None = None, log: bool = True):
        started = time.perf_counter()
        state = self.graph.invoke({"question": question, "today": today, "run_id": run_id})
        ans = routed(state["answer"], state, started, today)
        if self.deps.cfg["router"].get("contacts", "off") == "on":
            ans.router["contact_office"] = contacts.add_contact(ans, question)
        if log:
            log_request(self.deps.conn, question, ans, self.deps.cfg, run_id)
        return ans


def answer_question(
    conn, question: str, today: date, *, cfg: dict, client_factory=make_client,
    run_id: int | None = None, router: Router | None = None,
):  # fmt: skip
    """The eval runner's entry point. router.mode "off": exactly cta.answer.answer, nothing else
    runs. "on": the graph."""
    if cfg["router"]["mode"] != "on":
        return answer(conn, question, today, cfg=cfg, client_factory=client_factory, run_id=run_id)
    router = router or Router(conn, cfg, client_factory)
    return router.answer(question, today, run_id)
