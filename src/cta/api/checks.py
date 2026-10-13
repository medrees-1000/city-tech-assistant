"""Startup checks of the API: it refuses to start when any of these fails (docs/phase4-plan.md).

`startup_problems` returns one message per failed check; an empty list means the API may start.
The database check prints a fixed message because a driver error can contain connection details.
"""

import os
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv

from cta.index.db import connect as default_connect
from cta.index.db import migration_files
from cta.settings import ROOT, enabled_tracing


class StartupError(RuntimeError):
    """The API cannot start; the message lists every failed check."""


def file_problems(root: Path) -> list[str]:
    needed = [
        root / "config" / "contacts.yaml",
        root / "data" / "calendar" / "calendar_events.json",
    ]
    out = [f"missing file: {p.relative_to(root)}" for p in needed if not p.exists()]
    courses = root / "data" / "processed" / "courses"
    if not courses.exists() or not any(courses.rglob("*.json")):
        out.append("missing data: data/processed/courses (the chain tool reads it)")
    return out


def database_problems(connect: Callable) -> list[str]:
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
            applied = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
    except Exception:  # noqa: BLE001 - the driver message can contain connection details
        return ["database not reachable, or schema_migrations missing (run: docker compose up -d)"]
    missing = [p.name for p in migration_files() if p.name not in applied]
    return [f"migrations not applied: {', '.join(missing)}"] if missing else []


def startup_problems(
    cfg: dict, env: dict | None = None, connect: Callable = default_connect, root: Path = ROOT
) -> list[str]:
    if env is None:
        load_dotenv(root / ".env")
        env = dict(os.environ)
    problems = []
    if on := enabled_tracing(env):
        problems.append(
            f"tracing is enabled ({', '.join(on)}); unset it: the API must not send text out"
        )
    for key in ("mode", "contacts"):
        if cfg["router"].get(key) != "on":
            problems.append(f"router.{key} must be on (the API contract needs routes and contacts)")
    if not env.get("OPENAI_API_KEY", "").strip():
        problems.append("OPENAI_API_KEY is not set")
    problems += file_problems(root)
    problems += database_problems(connect)
    return problems


def require_startup(cfg: dict, **kw) -> None:
    problems = startup_problems(cfg, **kw)
    if problems:
        raise StartupError("the API cannot start:\n  - " + "\n  - ".join(problems))
