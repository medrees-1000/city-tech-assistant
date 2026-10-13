"""The FastAPI app (Phase 4). Dependencies are arguments of `create_app`, so tests can replace them.

GET /health and POST /ask. The answer comes from the existing router graph (cta.graph.build.Router)
and is only converted here (cta.api.convert); nothing of the pipeline is copied.
"""

import subprocess
import time
import uuid
from collections.abc import Callable
from datetime import date

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from cta.api import convert, requestlog, schema, topic
from cta.api.checks import require_startup
from cta.graph import render
from cta.graph.build import Router, load_events
from cta.index.db import connect as default_connect
from cta.index.embed import ApiError, make_client
from cta.settings import ROOT, load_models


def git_version() -> str:
    done = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT
    )
    return done.stdout.strip() or "unknown"


PROVIDER_MESSAGE = "The language model service failed. Try again."


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
    clock: Callable[[], date] = date.today,
    log_writer: Callable = requestlog.write,
    client_factory: Callable | None = None,
) -> FastAPI:
    cfg = cfg or load_models()
    client_factory = client_factory or make_client  # looked up at call time (tests replace it)
    if check_startup:
        require_startup(cfg, env=env, connect=connect, root=root)
    version = git_version()
    events = load_events()
    by_id = {e["id"]: e for e in events}
    url_map = convert.build_url_map(root / "data" / "processed" / "pages")
    registrar = render.registrar_contact()
    if router_factory is None:

        def router_factory(conn, cfg):
            return Router(conn, cfg, make_client, events=events, contact=registrar)

    api = cfg["api"]
    record = requestlog.Logger(
        log_writer
    )  # counts failed writes; a failed write never fails a request
    app = FastAPI(title="City Tech Assistant", version=version)

    @app.middleware("http")
    async def request_id_and_size(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex
        size = request.headers.get("content-length", "0")
        if size.isdigit() and int(size) > api["max_body_bytes"]:
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
            "status": "ok", "db": "ok", "version": version, "router": cfg["router"]["mode"],
            "log_failures": record.failures,
        }  # fmt: skip
        try:
            with connect() as conn:
                conn.execute("SELECT 1")
        except Exception:  # noqa: BLE001 - nothing from the driver is shown
            return JSONResponse({**body, "status": "degraded", "db": "down"}, status_code=503)
        return body

    @app.post("/ask", response_model=schema.AskResponse)
    def ask(body: schema.AskRequest, request: Request):
        rid = request.state.request_id
        question = body.question.strip()
        today = api["today"] or clock()
        started = time.perf_counter()

        def failed(status: str, conn, chars: int | None = None):
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
            return error(
                422, "invalid_question",
                f"The question must be 1 to {api['max_question_chars']} characters.", request,
            )  # fmt: skip
        try:
            with connect() as conn:
                try:
                    ans = router_factory(conn, cfg).answer(question, today, log=False)
                except ApiError:
                    failed("provider_error", conn)
                    return error(502, "provider_error", PROVIDER_MESSAGE, request)
                except Exception:
                    failed("internal_error", conn)
                    raise
                response = convert.to_response(
                    ans, question, cfg, today, rid, version, url_map, by_id
                )
                topic.rewrite(question, response, cfg, client_factory)
                record(conn, requestlog.success_record(response))
                return response
        except psycopg.OperationalError:
            record.failures += 1  # the database is down: this request cannot be logged
            return error(503, "unavailable", "The service is not available right now.", request)

    return app
