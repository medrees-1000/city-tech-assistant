"""Postgres connection, migrations and status.

    uv run python -m cta.index.db migrate   # apply new db/migrations/*.sql files
    uv run python -m cta.index.db status    # tables and row counts

The password comes from .env and is never printed.
"""

import os
import sys
from pathlib import Path

import psycopg
import psycopg.conninfo
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from psycopg import sql

from cta.settings import ROOT

MIGRATIONS_DIR = ROOT / "db" / "migrations"


def conninfo(env: dict | None = None) -> str:
    """Connection string: DATABASE_URL if set, else the local compose database."""
    if env is None:
        load_dotenv(ROOT / ".env")
        env = dict(os.environ)
    url = env.get("DATABASE_URL", "").strip()
    if url:
        return url
    password = env.get("POSTGRES_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("POSTGRES_PASSWORD is not set; copy .env.example to .env and fill it")
    return psycopg.conninfo.make_conninfo(
        host="127.0.0.1", port=5432, user="cta", dbname="cta", password=password
    )


def connect(env: dict | None = None) -> psycopg.Connection:
    """Open a connection; register the vector type once the extension exists."""
    conn = psycopg.connect(conninfo(env))
    has_vector = conn.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'").fetchone()
    if has_vector:
        register_vector(conn)
    return conn


def migration_files(directory: Path = MIGRATIONS_DIR) -> list[Path]:
    """Migration files in the order they run (by file name; names start with a number)."""
    return sorted(directory.glob("*.sql"), key=lambda p: p.name)


def migrate(conn: psycopg.Connection, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply migrations not yet recorded in schema_migrations; return the names that ran."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    conn.commit()
    done = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}
    ran = []
    for path in migration_files(directory):
        if path.name in done:
            continue
        # One transaction per migration: it is applied completely or not at all.
        with conn.transaction():
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
        ran.append(path.name)
    return ran


def status(conn: psycopg.Connection) -> list[tuple[str, int]]:
    """Every table in the public schema with its row count."""
    names = [
        r[0]
        for r in conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
    ]
    return [
        (
            n,
            conn.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(n))).fetchone()[
                0
            ],
        )
        for n in names
    ]


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("migrate", "status"):
        print("usage: python -m cta.index.db migrate|status")
        return 2
    try:
        conn = connect()
    except psycopg.OperationalError:
        # The driver message can echo connection details, so print a fixed one.
        print("cannot connect to Postgres; is it running? (docker compose up -d)")
        return 1
    with conn:
        if argv[1] == "migrate":
            ran = migrate(conn)
            print("applied: " + ", ".join(ran) if ran else "nothing to apply (up to date)")
        else:
            for name, count in status(conn):
                print(f"{name:20} {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
