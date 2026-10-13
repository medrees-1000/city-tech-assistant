"""The FastAPI app (Phase 4). Dependencies are arguments of `create_app`, so tests can replace them.

GET /health and POST /ask. The answer comes from the existing router graph (cta.graph.build.Router)
and is only converted here (cta.api.convert); nothing of the pipeline is copied.
"""

import subprocess
import uuid
from collections.abc import Callable
from datetime import date

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from cta.api import convert, schema
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
) -> FastAPI:
    cfg = cfg or load_models()
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
        body = {"status": "ok", "db": "ok", "version": version, "router": cfg["router"]["mode"]}
        try:
            with connect() as conn:
                conn.execute("SELECT 1")
        except Exception:  # noqa: BLE001 - nothing from the driver is shown
            return JSONResponse({**body, "status": "degraded", "db": "down"}, status_code=503)
        return body

    @app.post("/ask", response_model=schema.AskResponse)
    def ask(body: schema.AskRequest, request: Request):
        question = body.question.strip()
        if not 1 <= len(question) <= api["max_question_chars"]:
            return error(
                422, "invalid_question",
                f"The question must be 1 to {api['max_question_chars']} characters.", request,
            )  # fmt: skip
        today = api["today"] or clock()
        try:
            with connect() as conn:
                ans = router_factory(conn, cfg).answer(question, today, log=False)
        except ApiError:
            return error(
                502, "provider_error", "The language model service failed. Try again.", request
            )
        except psycopg.OperationalError:
            return error(503, "unavailable", "The service is not available right now.", request)
        return convert.to_response(
            ans, question, cfg, today, request.state.request_id, version, url_map, by_id
        )

    return app
