"""The FastAPI app (Phase 4). Dependencies are arguments of `create_app`, so tests can replace them.

Step 2: GET /health. POST /ask comes in step 3.
"""

import subprocess
from collections.abc import Callable

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from cta.api.checks import require_startup
from cta.index.db import connect as default_connect
from cta.settings import ROOT, load_models


def git_version() -> str:
    done = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT
    )
    return done.stdout.strip() or "unknown"


def create_app(
    cfg: dict | None = None,
    connect: Callable = default_connect,
    env: dict | None = None,
    root=ROOT,
    check_startup: bool = True,
) -> FastAPI:
    cfg = cfg or load_models()
    if check_startup:
        require_startup(cfg, env=env, connect=connect, root=root)
    version = git_version()
    app = FastAPI(title="City Tech Assistant", version=version)

    @app.get("/health")
    def health():
        body = {"status": "ok", "db": "ok", "version": version, "router": cfg["router"]["mode"]}
        try:
            with connect() as conn:
                conn.execute("SELECT 1")
        except Exception:  # noqa: BLE001 - nothing from the driver is shown
            return JSONResponse({**body, "status": "degraded", "db": "down"}, status_code=503)
        return body

    return app
