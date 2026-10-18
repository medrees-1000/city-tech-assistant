"""The FastAPI app (Phase 4). Dependencies are arguments of `create_app`, so tests can replace them.

GET /health and POST /ask. The answer comes from the existing router graph (cta.graph.build.Router)
and is only converted here (cta.api.convert); nothing of the pipeline is copied.
"""

import asyncio
import os
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from contextlib import ExitStack, asynccontextmanager
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from cta.api import convert, hygiene, language, requestlog, schema, screen, topic, tracing
from cta.api import guard as guard_mod
from cta.api.checks import require_startup
from cta.graph import render
from cta.graph.build import Router, load_events
from cta.index.db import connect as default_connect
from cta.index.embed import ApiError, make_client, retry_limit
from cta.settings import ROOT, config_version, load_models


def git_version() -> str:
    """The commit this code was built from: CTA_COMMIT (set when the image is built, where there is
    no .git folder), else git, else "unknown"."""
    baked = os.environ.get("CTA_COMMIT", "").strip()
    if baked:
        return baked[:12]
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT
        )
    except OSError:  # no git program in the image
        return "unknown"
    return done.stdout.strip() or "unknown"


NEW_YORK = ZoneInfo("America/New_York")


def today_new_york(now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> date:
    """Today's date in New York (City Tech's time), not UTC: at 22:30 on Oct 18 in New York it is
    already Oct 19 in UTC, and "today" in a student's question means the 18th."""
    return now().astimezone(NEW_YORK).date()


PROVIDER_MESSAGE = "The language model service failed. Try again."
UNAVAILABLE_MESSAGE = "The service is not available right now."


def error(status: int, code: str, message: str, request: Request) -> JSONResponse:
    body = {"error": {"code": code, "message": message}}
    rid = request.state.request_id
    return JSONResponse(
        body | {"request_id": rid}, status_code=status, headers={"X-Request-ID": rid}
    )


def create_app(
    cfg: dict | None = None,
    connect: Callable = default_connect,
    env: dict | None = None,
    root=ROOT,
    check_startup: bool = True,
    router_factory: Callable | None = None,
    clock: Callable[[], date] = today_new_york,
    log_writer: Callable = requestlog.write,
    feedback_writer: Callable = requestlog.write_feedback,
    client_factory: Callable | None = None,
) -> FastAPI:
    cfg = cfg or load_models()
    guards = cfg["guardrails"]

    def timed_client():  # the API's own calls stop after model_call_timeout_s (the eval's do not)
        client = make_client(timeout=guards["model_call_timeout_s"])
        return tracer.wrap(client) if tracer else client  # recorded only inside a traced request

    client_factory = client_factory or timed_client  # looked up at call time (tests replace it)
    if check_startup:
        require_startup(cfg, env=env, connect=connect, root=root)
    # Optional developer tracing (off unless the config flag, CTA_TRACING=on and the key are set);
    # built after the startup checks, so a refused start never builds a client
    tracer = tracing.Tracing.from_settings(cfg, env)
    version = git_version()
    cfg_version = config_version(cfg)
    trace_meta = {"commit": version, "config_version": cfg_version,
                  "rescue": cfg["answer"].get("rescue", "off")}  # fmt: skip
    events = load_events()
    by_id = {e["id"]: e for e in events}
    url_map = convert.build_url_map(root / "data" / "processed" / "pages")
    registrar = render.registrar_contact()
    if router_factory is None:

        def router_factory(conn, cfg):
            return Router(conn, cfg, timed_client, events=events, contact=registrar)

    api = cfg["api"]
    shown_settings = {  # key settings only: no secret and nothing a student typed
        "chat_model": cfg["chat_model"], "embedding_model": cfg["embedding_model"],
        "rescue": cfg["answer"].get("rescue", "off"),
        "abstain_threshold": cfg["answer"]["abstain_threshold"],
        "language_step": guards["language_step"], "non_english": guards["non_english"],
        "rate_per_minute": guards["rate_per_minute"], "rate_per_day": guards["rate_per_day"],
        "tracing": tracer is not None, "today_zone": "America/New_York",
    }  # fmt: skip
    feedback_failures = [0]  # a failed vote write is counted here and shown in /health
    if env is None:  # the real process: the environment, with .env for local runs
        load_dotenv(root / ".env")
    secrets_env = dict(os.environ) if env is None else env
    guard = guard_mod.Guard(
        guards, root=root, proxy_secret=secrets_env.get("CTA_PROXY_SECRET", "").strip(),
        ip_salt=secrets_env.get("CTA_IP_SALT", "").strip(),
    )  # fmt: skip
    # counts failed writes; a failed write never fails a request, and its cost still counts for
    # the daily cap (tester round 2, T13)
    record = requestlog.Logger(log_writer, on_lost=guard.add_unlogged)

    @asynccontextmanager
    async def lifespan(_app):
        yield
        if tracer:  # do not lose the last queued traces when the API stops
            tracer.flush()

    app = FastAPI(title="City Tech Assistant", version=version, lifespan=lifespan)
    app.state.guard = guard  # tests read the counters and the salt through this
    app.state.cfg = cfg

    @app.middleware("http")
    async def request_id_and_size(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        size = request.headers.get("content-length", "0")
        health_check = request.url.path == "/health" and request.method == "GET"
        if not health_check and not guard.proxy_ok(request):
            guard.proxy_rejected += 1  # a count only: nothing about the sender is kept
            response = error(403, "forbidden", "Not available.", request)
        elif size.isdigit() and int(size) > api["max_body_bytes"]:
            response = error(413, "too_large", "The request is too large.", request)
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError):
        return error(422, "invalid_request", "The request body is not valid.", request)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        codes = {404: "not_found", 405: "method_not_allowed"}
        return error(
            exc.status_code, codes.get(exc.status_code, "http_error"), "Not available.", request
        )

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        return error(500, "internal_error", "Something went wrong on our side.", request)

    @app.get("/health")
    def health():
        body = {
            "status": "ok", "db": "ok", "version": version, "config_version": cfg_version,
            "router": cfg["router"]["mode"], "settings": shown_settings,
            "log_failures": record.failures, "feedback_failures": feedback_failures[0],
            **guard.health(connect),
        }  # fmt: skip
        try:
            with connect() as conn:
                conn.execute("SELECT 1")
        except Exception:  # noqa: BLE001 - nothing from the driver is shown
            return JSONResponse({**body, "status": "degraded", "db": "down"}, status_code=503)
        return body

    def block(reason: str, question: str, rid: str, today: date, started: float,
              text: str | None = None, status: str | None = None, cost: float | None = 0.0,
              text_blocked: bool = False, lang: language.Language | None = None):  # fmt: skip
        """Answer with a guardrail's fixed reply (a normal assistant message) and log one row."""
        ms = (time.perf_counter() - started) * 1000
        shown = "" if text_blocked else question
        resp = convert.guardrail_response(reason, text or guard_mod.TEXTS[reason], shown, cfg,
                                          today, rid, version, ms)  # fmt: skip
        chars = len(question) if text_blocked else None
        if lang is not None:  # a block after the language step: its call is part of the cost
            language.add_to_response(resp, lang)
            cost = (cost or 0.0) + (lang.call.cost if lang.call else 0.0)
        rec = requestlog.blocked_record(resp, reason, status, text_blocked, chars, cost)
        try:
            with connect() as conn:
                record(conn, rec)
        except Exception:  # noqa: BLE001 - a row that cannot be written never fails the reply
            record.failures += 1
            record.lost(rec)
        return resp

    def serve(question: str, rid: str, today: date, started: float, abandoned: threading.Event,
              note: str | None = None):  # fmt: skip
        """The pipeline for one question (the body of /ask before step 7)."""
        retry_limit.set(guards["model_retries"])  # the API retries less than the eval does

        def failed(status: str, conn, chars: int | None = None):
            if abandoned.is_set():
                return  # the request already got its timeout reply and row
            ms = (time.perf_counter() - started) * 1000
            text = "" if chars is not None else question
            record(
                conn,
                requestlog.error_record(rid, status, text, today, cfg["chat_model"], ms, chars),
            )

        if not 1 <= len(question) <= api["max_question_chars"]:
            try:  # no question text is stored for a rejected question, only its length
                with connect() as conn:
                    failed("invalid_question", conn, chars=len(question))
            except Exception:  # noqa: BLE001
                record.failures += 1
            return JSONResponse(
                {"error": {"code": "invalid_question", "message": "The question must be 1 to "
                           f"{api['max_question_chars']} characters."}, "request_id": rid},
                status_code=422, headers={"X-Request-ID": rid},
            )  # fmt: skip
        lang = language.Language(english=question)
        if guards[
            "language_step"
        ]:  # one small call, only for a question that does not look English
            lang = language.detect(question, cfg, client_factory)
        router_text, lang_note, details = question, None, False
        scrubbed_translation = False
        if lang.code != "en":
            # every screen runs again on the English translation: the screens are English-only
            verdict = screen.screen(lang.english, guards)
            if verdict.reason:
                guard.blocked[verdict.reason] += 1
                lang.english = ""  # a blocked message's translation is not stored: no student text
                text = f"{lang.note}\n\n{screen.reply(verdict.reason, guards)}"
                return block(verdict.reason, question, rid, today, started, text, None, 0.0,
                             True, lang)  # fmt: skip
            router_text, lang_note, details = verdict.question, lang.note, verdict.removed_details
            lang.english = router_text  # the scrubbed translation is what is stored and shown
            scrubbed_translation = verdict.scrubbed
            if guards["non_english"] == "english_only":
                # option 3: the screens above ran on the translation; now a fixed English notice, no
                # retrieval, no answer. If the original needed scrubbing, the scrubbed translation
                # is what gets logged.
                guard.blocked["non_english"] += 1
                shown = router_text if scrubbed_translation else question
                text = f"{lang.note}\n\n{language.NON_ENGLISH_REPLY}"
                return block(
                    "non_english", shown, rid, today, started, text, None, 0.0, False, lang
                )
        try:
            with connect() as conn, ExitStack() as stack:
                # the trace starts here: after the scrub and every guardrail, with the scrubbed text
                trace = (
                    stack.enter_context(tracer.request(router_text, rid, trace_meta))
                    if tracer
                    else None
                )
                try:
                    ans = router_factory(conn, cfg).answer(router_text, today, log=False)
                except ApiError:
                    failed("provider_error", conn)
                    return JSONResponse(
                        {"error": {"code": "provider_error", "message": PROVIDER_MESSAGE},
                         "request_id": rid}, status_code=502, headers={"X-Request-ID": rid},
                    )  # fmt: skip
                except Exception:
                    failed("internal_error", conn)
                    raise
                response = convert.to_response(
                    ans, router_text, cfg, today, rid, version, url_map, by_id
                )
                # as typed (redacted); if the translation needed scrubbing (a name or number the
                # original's wording hid) the scrubbed translation is stored instead
                response.question = router_text if scrubbed_translation else question
                topic.rewrite(router_text, response, cfg, client_factory)
                language.add_to_response(response, lang)
                # lines at the start of the answer: the language note (in the student's language),
                # then the note that personal details were removed, then the answer
                lines = [lang_note] if lang_note else []
                if note or details:
                    lines.append(screen.PERSONAL_NOTE)
                if lines:
                    response.answer = "\n\n".join([*lines, response.answer])
                net_distress = response.abstained and screen.names_self_harm(response.answer)
                net_leak = screen.leaks_key(response.answer)
                if trace:  # a reply the output nets turn into a safety reply is not recorded
                    (trace.withhold if net_distress or net_leak else trace.finish)(response)
                if net_distress:
                    guard.blocked["distress"] += 1  # the topic sentence must never echo it
                    return block("distress", question, rid, today, started,
                                 screen.reply("distress", guards), None,
                                 response.how_found.cost_usd["total"], True)  # fmt: skip
                if net_leak:  # never return a key-shaped answer
                    guard.blocked["output"] += 1
                    return block("output", question, rid, today, started,
                                 screen.reply("output", guards), None,
                                 response.how_found.cost_usd["total"])  # fmt: skip
                if not abandoned.is_set():
                    record(conn, requestlog.success_record(response))
                return response
        except psycopg.OperationalError:
            record.failures += 1  # the database is down: this request cannot be logged
            return JSONResponse(
                {"error": {"code": "unavailable", "message": UNAVAILABLE_MESSAGE},
                 "request_id": rid}, status_code=503, headers={"X-Request-ID": rid},
            )  # fmt: skip

    @app.post("/ask", response_model=schema.AskResponse)
    async def ask(body: schema.AskRequest, request: Request):
        rid = request.state.request_id
        question = hygiene.normalize(body.question)  # before any screen, redaction or log
        today = api["today"] or clock()
        started = time.perf_counter()
        reason = await run_in_threadpool(guard.stage1, request, connect)
        if reason:
            return await run_in_threadpool(block, reason, question, rid, today, started)
        verdict = screen.screen(question, guards)
        if verdict.reason:  # a fixed reply; the text is not stored, only its length
            guard.blocked[verdict.reason] += 1
            text = screen.reply(verdict.reason, guards)
            return await run_in_threadpool(
                block, verdict.reason, question, rid, today, started, text, None, 0.0, True
            )
        guard.redacted += verdict.scrubbed
        note = screen.PERSONAL_NOTE if verdict.removed_details else None
        question = verdict.question  # what the model and the log see: emails, numbers, names gone
        # The monthly cap comes after the regex safety screen above, so a student in distress still
        # gets the 988 reply at the cap; every other route needs a model call and is paused.
        if await run_in_threadpool(guard.over_monthly_cap, connect):
            text = guard_mod.paused_text()
            return await run_in_threadpool(
                block, "monthly_cap", question, rid, today, started, text
            )
        abandoned = threading.Event()
        try:
            return await asyncio.wait_for(
                run_in_threadpool(serve, question, rid, today, started, abandoned, note),
                timeout=guards["request_timeout_s"],
            )
        except TimeoutError:
            abandoned.set()  # the worker finishes in the background, but writes no second row
            guard.blocked["timeout"] += 1
            return await run_in_threadpool(
                block, "timeout", question, rid, today, started, None, "timeout", None
            )

    @app.post("/feedback", response_model=schema.FeedbackResponse)
    def feedback(body: schema.FeedbackRequest, request: Request):
        try:
            rid = uuid.UUID(body.request_id.strip()).hex  # the id format the API returns
        except ValueError:
            return error(404, "not_found", "No such request.", request)
        try:
            with connect() as conn:
                found = feedback_writer(conn, rid, body.vote)
        except Exception:  # noqa: BLE001 - nothing from the driver is shown
            feedback_failures[0] += 1
            return error(503, "unavailable", "The vote could not be saved right now.", request)
        if not found:
            return error(404, "not_found", "No such request.", request)
        return schema.FeedbackResponse(request_id=rid, vote=body.vote)

    return app
