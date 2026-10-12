import pytest

from cta.index import db


def test_conninfo_builds_local_default():
    info = db.conninfo({"POSTGRES_PASSWORD": "abc123"})
    assert "host=127.0.0.1" in info and "port=5432" in info and "user=cta" in info


def test_conninfo_prefers_database_url():
    assert db.conninfo({"DATABASE_URL": "postgresql://x@h/d", "POSTGRES_PASSWORD": "p"}) == (
        "postgresql://x@h/d"
    )


def test_conninfo_without_password_fails_without_leaking():
    with pytest.raises(RuntimeError, match="POSTGRES_PASSWORD"):
        db.conninfo({})


def test_migration_files_are_ordered(tmp_path):
    for name in ("010_b.sql", "002_a.sql", "001_init.sql", "notes.txt"):
        (tmp_path / name).write_text("select 1;")
    assert [p.name for p in db.migration_files(tmp_path)] == [
        "001_init.sql",
        "002_a.sql",
        "010_b.sql",
    ]


def test_real_migrations_start_with_init():
    names = [p.name for p in db.migration_files()]
    assert names[0] == "001_init.sql"
    assert all(n[:3].isdigit() for n in names)


# ---- integration: need the Docker database (docker compose up -d) ----


@pytest.fixture
def conn():
    try:
        c = db.connect()
    except Exception as e:  # not running, no password, etc.
        pytest.skip(f"Postgres not available ({type(e).__name__}); run: docker compose up -d")
    with c:
        yield c


@pytest.mark.integration
def test_migrate_is_safe_to_repeat(conn):
    db.migrate(conn)
    assert db.migrate(conn) == []
    tables = {name for name, _ in db.status(conn)}
    assert {"chunks", "calendar_events", "eval_runs", "request_logs", "schema_migrations"} <= tables


@pytest.mark.integration
def test_vector_column_is_1536(conn):
    db.migrate(conn)
    row = conn.execute(
        "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
        "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
    ).fetchone()
    assert row[0] == "vector(1536)"
