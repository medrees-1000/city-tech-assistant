"""Turn the router's RoutedAnswer into the API response (docs/phase4-plan.md, section 1).

This module only reads fields: routing, abstaining, contact choice and rendering stay in the graph.
"""

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlparse

from cta.answer import THRESHOLD_ABSTAIN
from cta.api import schema
from cta.graph import contact as contacts
from cta.settings import ROOT

PUBLIC_HOST = "www.citytech.cuny.edu"
MARKER = "ABSTAIN:"
EXCERPT_CHARS = 300
CHAIN_KEYS = ("extraction", "code", "detail", "course_count", "truncated", "unexpanded",
              "no_record", "no_record_codes")  # fmt: skip
ANSWER_ROUTES = ("other", "chain", "calendar_fallthrough", "chain_fallthrough", "advice")
CHAIN_CODES = ("chain_no_record", "chain_outside_departments")
OWN_CODES = ("calendar_", *CHAIN_CODES)  # codes the graph itself sets for its two tools


def build_url_map(pages_dir: Path = ROOT / "data" / "processed" / "pages") -> dict[str, str]:
    """File name -> public URL, only for PDFs that a collected page of the City Tech site links."""
    out: dict[str, str] = {}
    for path in sorted(pages_dir.glob("*/*.json")):
        for link in json.loads(path.read_text(encoding="utf-8")).get("pdf_links", []):
            url = urlparse(link["url"])
            if url.scheme == "https" and url.netloc == PUBLIC_HOST:
                out.setdefault(unquote(Path(url.path).name), link["url"])
    return out


def public_route(ans) -> str:
    if ans.route == "abstain":
        return "chain" if ans.abstain_reason in CHAIN_CODES else "calendar"
    known = {"calendar": "calendar", "chain": "chain", "clarify": "clarify"}
    return known.get(ans.route, "retrieve")


PERSONAL_ACCOUNT_TEXT = (
    "I can't see personal account information such as holds, balances or grades."
)


def abstain_code(reason: str | None, question: str = "", table: dict | None = None) -> str | None:
    """A short code for an abstention, never the model's sentence. A retrieval abstention on a
    question about the student's own account data ("my gpa", "my financial aid status" ...; a
    possessive plus an office noun alone is not enough) is "personal_account"; calendar and chain
    abstentions keep their own codes."""
    if reason is None:
        return None
    if reason.startswith(OWN_CODES):
        return reason
    if contacts.personal_account_cue(question, table or contacts.load_contacts()):
        return "personal_account"
    return reason if reason == "below_threshold" else "model"


def excerpt(text: str) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    return flat if len(flat) <= EXCERPT_CHARS else flat[:EXCERPT_CHARS].rstrip() + "..."


def citation(n: int, chunk: dict, cited: bool, url_map: dict, events: dict) -> schema.Citation:
    """One numbered source: a web page uses its own URL; a file gets one only if a page links it."""
    source = chunk.get("source") or ""
    kind = chunk.get("kind")
    url = file = None
    if kind == "calendar":
        pdf = (events.get(chunk["id"]) or {}).get("source_pdf")
        file = Path(pdf).name if pdf else None
    elif source.startswith("https://"):
        url = source
    elif kind != "course" and source:
        file = Path(source).name
    if file:
        url = url_map.get(file)
    title = chunk.get("heading_path") or chunk["id"]
    if kind == "course":
        title = f"City Tech course catalog: {title}"
    return schema.Citation(
        n=n, id=chunk["id"], title=title, url=url, file=file,
        doc_type="calendar" if kind == "calendar" else chunk.get("doc_type"),
        term=chunk.get("term") or (chunk.get("terms") or [None])[0],
        last_updated=chunk.get("last_updated"), excerpt=excerpt(chunk.get("text", "")),
        cited=cited,
    )  # fmt: skip


def contact_card(key: str, table: dict) -> schema.Contact:
    entry = table["offices"][key]
    emails = [
        {"address": e, "for": None}
        if isinstance(e, str)
        else {"address": e["address"], "for": e["for"]}
        for e in entry["emails"]
    ]
    return schema.Contact(
        office=key, name=entry["name"], emails=emails, phones=list(entry["phones"]),
        note=entry.get("also"),
    )  # fmt: skip


def pool_title(chunk: dict) -> str | None:
    title = chunk.get("heading_path") or None
    return (
        f"City Tech course catalog: {title}" if title and chunk.get("kind") == "course" else title
    )


def retrieved_block(search, k: int) -> list[schema.RetrievedChunk]:
    """The candidate pool in first-stage order, with the reranker's score and final rank."""
    if search is None or not search.results:
        return []
    pool = search.pool or search.results
    rr = search.rerank
    final = {i: pos for pos, i in enumerate(rr.order, 1)} if rr and not rr.failed else {}
    out = []
    for i, c in enumerate(pool):
        if search.pool:
            pos = final.get(i)
        else:
            pos = i + 1
        score = rr.scores[i] if rr and not rr.failed and i < len(rr.scores) else None
        out.append(
            schema.RetrievedChunk(
                id=c["id"],
                title=pool_title(c),
                first_stage_rank=c.get("rank", i + 1),
                similarity=c.get("similarity"),
                rerank_score=score,
                final_rank=pos,
                sent_to_answerer=bool(pos and pos <= k),
            )  # fmt: skip
        )
    return out


def how_found(ans, cfg: dict, near_miss: bool | None = None) -> schema.HowFound:
    router, search = ans.router, ans.search
    classify = router["classify"]
    select = (router.get("select") or {}) if router.get("select") else {}
    chain = router.get("chain")
    rr = search.rerank if search else None
    answer_ms = max(0.0, ans.chat_ms - classify["ms"] - select.get("ms", 0.0))
    retrieval_ms = (
        (search.retrieval_ms - (rr.ms if rr else 0.0)) if search and search.results else None
    )
    cost_search = search.cost if search else 0.0
    answer_cost = ans.chat_cost - classify["cost"] - select.get("cost", 0.0)
    return schema.HowFound(
        near_miss=bool(ans.near_miss) if near_miss is None else near_miss,
        rewrite=router.get("rewrite"),
        route_detail=router["route"], intent=router.get("intent"),
        top_vector_similarity=search.top_vector_similarity if search else None,
        abstain_threshold=cfg["answer"]["abstain_threshold"],
        retrieved=retrieved_block(search, cfg["answer"]["k"]),
        calendar={k: router[k] for k in ("term_status", "term", "selector_version", "pool_size",
                                          "selected", "weekday_mismatches", "invalid_ids")
                  if k in router} or None,
        chain={k: chain[k] for k in CHAIN_KEYS if k in chain} if chain else None,
        stages_ms={
            "classify": classify["ms"], "select": select.get("ms"),
            "retrieval": retrieval_ms, "rerank": rr.ms if rr else None,
            "walk": chain.get("walk_ms") if chain else None,
            "answer": round(answer_ms, 1) if ans.route in ANSWER_ROUTES else None,
            "topic": None,
            "total": float(ans.latency_ms),
        },
        tokens={
            "prompt": ans.prompt_tokens, "completion": ans.completion_tokens,
            "embedding": search.tokens if search else 0,
            "rerank_prompt": rr.prompt_tokens if rr else 0,
            "rerank_completion": rr.completion_tokens if rr else 0,
            "topic_prompt": 0, "topic_completion": 0,
        },
        cost_usd={
            "classify": classify["cost"], "select": select.get("cost", 0.0),
            "embedding": cost_search, "rerank": rr.cost if rr else 0.0,
            "answer": round(max(0.0, answer_cost), 8), "topic": 0.0, "total": ans.cost,
        },
        cache_hits={"embedding": bool(search and search.cache_hit),
                    "rerank": bool(rr and rr.cache_hit)},
    )  # fmt: skip


def to_response(ans, question: str, cfg: dict, today: date, request_id: str, version: str,
                url_map: dict, events: dict, table: dict | None = None):  # fmt: skip
    """The /ask response for a RoutedAnswer. The contact sentence the graph appended is removed
    from the text (the contact card carries it); the ABSTAIN: marker is removed too."""
    table = table or contacts.load_contacts()
    key = ans.router.get("contact_office") if ans.abstained else None
    text = ans.text.strip()
    if key:
        text = text.removesuffix(contacts.contact_line(key, table)).rstrip()
    if ans.abstained:
        text = text.removeprefix(MARKER).strip()
    code = abstain_code(ans.abstain_reason, question, table)
    # a near-miss never applies to a personal-account refusal: the API relabels such an abstention,
    # so its closest pages and citations are dropped and the plain text stays (as before the helper)
    near_miss = bool(ans.near_miss) and code != "personal_account"
    if ans.near_miss and not near_miss:
        text = THRESHOLD_ABSTAIN.removeprefix(MARKER).strip()
    if code == "personal_account":  # tester round 2, T09: say plainly why (the contact card stays)
        text = PERSONAL_ACCOUNT_TEXT
    kind = (
        "abstain" if ans.abstained
        else "clarify" if ans.route == "clarify"
        else "not_announced" if ans.router.get("tba_rows")
        else "answer"
    )  # fmt: skip
    cited = set(ans.citations)
    return schema.AskResponse(
        request_id=request_id, question=question, answer=text, answer_type=kind,
        abstained=ans.abstained, abstain_reason=code,
        route=public_route(ans),
        citations=[]
        # an abstention cites nothing (the retrieved chunks are in how_found) unless it is a
        # near-miss, whose two closest pages are its citations
        if ans.abstained and not near_miss
        else [citation(n, c, n in cited, url_map, events) for n, c in enumerate(ans.sources, 1)],
        contact=contact_card(key, table) if key else None,
        how_found=how_found(ans, cfg, near_miss),
        meta=schema.Meta(today=today.isoformat(), version=version, model=cfg["chat_model"]),
    )  # fmt: skip


def guardrail_response(
    reason: str,
    text: str,
    question: str,
    cfg: dict,
    today: date,
    request_id: str,
    version: str,
    ms: float,
) -> schema.AskResponse:
    """A fixed reply of a guardrail as a normal answer: no sources, no card, no abstention. The
    reason is in how_found.route_detail. `text` and `question` never hold what was blocked."""
    zero_tokens = {
        k: 0
        for k in (
            "prompt",
            "completion",
            "embedding",
            "rerank_prompt",
            "rerank_completion",
            "topic_prompt",
            "topic_completion",
        )
    }
    steps = ("classify", "select", "retrieval", "rerank", "walk", "answer", "topic")
    hf = schema.HowFound(
        route_detail=reason, intent=None, top_vector_similarity=None,
        abstain_threshold=cfg["answer"]["abstain_threshold"], retrieved=[], calendar=None,
        chain=None, stages_ms={**{k: None for k in steps}, "total": round(ms, 1)},
        tokens=zero_tokens, cost_usd={k: 0.0 for k in (*steps, "embedding", "total")},
        cache_hits={"embedding": False, "rerank": False},
    )  # fmt: skip
    return schema.AskResponse(
        request_id=request_id, question=question, answer=text, answer_type="guardrail",
        abstained=False, abstain_reason=None, route="guardrail", citations=[], contact=None,
        how_found=hf, meta=schema.Meta(today=today.isoformat(), version=version,
                                       model=cfg["chat_model"]),
    )  # fmt: skip
