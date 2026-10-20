"""The deployment files: what they promise is checked here, without Docker, and the index export and
restore scripts are run once for real against throwaway databases (integration, skipped without the
Docker database).

The tab icons of the page (web/app) must be valid files too: see the end of this file.
"""

import re
import shutil
import struct
import subprocess
import uuid
import xml.etree.ElementTree as ET  # noqa: S405 - our own committed file, not untrusted input

import psycopg
import pytest
import yaml

from cta.index import db
from cta.settings import ROOT

COMPOSE = yaml.safe_load((ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8"))
SERVICES = COMPOSE["services"]
ENV_EXAMPLE = (ROOT / ".env.production.example").read_text(encoding="utf-8")


def env_names(text: str) -> list[str]:
    return re.findall(r"^([A-Z][A-Z0-9_]*)=", text, re.M)


# ---- the stack ----


def test_the_production_stack_has_its_own_project_name():
    # found in the rehearsal: with no name, `up` took over the development database container
    assert COMPOSE["name"] == "cta"
    dev = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    assert COMPOSE["name"] != dev.get("name", ROOT.name)


def test_only_caddy_publishes_ports_and_only_80_and_443():
    published = {name: s.get("ports") for name, s in SERVICES.items() if s.get("ports")}
    assert set(published) == {"caddy"}
    assert sorted(published["caddy"]) == ["443:443", "80:80"]
    assert "expose" not in SERVICES["db"]


def test_postgres_is_on_the_internal_network_only():
    assert SERVICES["db"]["networks"] == ["backend"]
    assert COMPOSE["networks"]["backend"] == {"internal": True}
    for name in ("migrate", "purge"):
        assert SERVICES[name]["networks"] == ["backend"]  # no route to the internet
    assert set(SERVICES["api"]["networks"]) == {"backend", "edge"}  # it must reach OpenAI
    assert SERVICES["caddy"]["networks"] == ["edge"]  # and cannot reach the database


def test_every_service_has_a_memory_limit_and_log_rotation_and_a_restart_policy():
    log = COMPOSE["x-logging"]
    assert log["driver"] == "json-file"
    assert log["options"] == {"max-size": "10m", "max-file": "3"}
    for name, s in SERVICES.items():
        assert s.get("mem_limit"), name
        assert s.get("logging") == log, name
        assert s.get("restart") in ("unless-stopped", "no"), name
    for name in ("db", "api", "caddy", "purge"):
        assert SERVICES[name]["restart"] == "unless-stopped"
    assert SERVICES["migrate"]["restart"] == "no"


def test_memory_limits_fit_a_two_gib_server_with_swap():
    def mb(text):
        return int(text.rstrip("m"))

    total = sum(mb(s["mem_limit"]) for s in SERVICES.values())
    assert mb(SERVICES["api"]["mem_limit"]) >= 512 and mb(SERVICES["db"]["mem_limit"]) >= 256
    assert total <= 1600  # leaves about 400 MB for the system on a 2 GiB t3.small


def test_health_checks_and_start_order():
    assert SERVICES["db"]["healthcheck"]["test"][0] == "CMD-SHELL"
    assert "/health" in " ".join(SERVICES["api"]["healthcheck"]["test"])
    assert SERVICES["api"]["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
    assert SERVICES["migrate"]["depends_on"]["db"]["condition"] == "service_healthy"
    assert SERVICES["caddy"]["depends_on"]["api"]["condition"] == "service_healthy"


def test_the_purge_job_keeps_the_thirty_days_the_page_promises():
    command = " ".join(SERVICES["purge"]["command"])
    assert "cta.api.purge --days 30" in command and "sleep 86400" in command
    notice = (ROOT / "web" / "lib" / "notice.ts").read_text(encoding="utf-8")
    assert "saved for 30 days" in notice


def test_secrets_come_from_the_environment_never_from_the_file():
    text = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    assert "${POSTGRES_PASSWORD:?" in text and "${CTA_HOSTNAME:?" in text
    assert "sk-" not in text and "lsv2_" not in text
    assert SERVICES["api"]["env_file"] == ".env.production"


# ---- the variables ----


def test_the_production_example_lists_every_variable_with_no_value():
    names = env_names(ENV_EXAMPLE)
    assert len(names) == len(set(names))
    for line in ENV_EXAMPLE.splitlines():
        if re.match(r"^[A-Z][A-Z0-9_]*=", line):
            assert line.endswith("="), line  # nothing after the equals sign
    must = {"POSTGRES_PASSWORD", "OPENAI_API_KEY", "CTA_HOSTNAME", "CTA_PROXY_SECRET",
            "CTA_IP_SALT", "CTA_COMMIT", "CTA_TRACING_ENABLED", "CTA_TRACING", "LANGSMITH_API_KEY",
            "LANGSMITH_PROJECT", "CTA_MONTHLY_SPEND_CAP_USD", "CTA_API_DISABLED"}  # fmt: skip
    assert must <= set(names)


def test_every_variable_the_compose_file_and_caddyfile_read_is_in_the_example():
    used = set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", (ROOT / "docker-compose.prod.yml").read_text()))
    used |= set(re.findall(r"\{\$([A-Z][A-Z0-9_]*)", (ROOT / "Caddyfile").read_text()))
    assert used <= set(env_names(ENV_EXAMPLE)), used - set(env_names(ENV_EXAMPLE))


def test_the_vercel_variables_are_named_without_values():
    names = env_names((ROOT / "web" / ".env.example").read_text(encoding="utf-8"))
    assert names == ["API_URL", "CTA_PROXY_SECRET"]
    assert all(
        ln.endswith("=") for ln in (ROOT / "web" / ".env.example").read_text().splitlines()
        if "=" in ln and not ln.startswith("#")
    )  # fmt: skip
    vercel = yaml.safe_load((ROOT / "web" / "vercel.json").read_text(encoding="utf-8"))
    assert vercel["framework"] == "nextjs"


def test_the_secret_files_are_git_ignored():
    for name in (".env", ".env.production", ".env.rehearsal", "backups/x.dump", "a.dump"):
        done = subprocess.run(["git", "check-ignore", "-q", name], cwd=ROOT)
        assert done.returncode == 0, name
    done = subprocess.run(["git", "check-ignore", "-q", ".env.production.example"], cwd=ROOT)
    assert done.returncode == 1  # the example itself is committed


# ---- Caddy and the image ----


def test_caddy_forwards_only_the_two_page_paths_and_writes_no_access_log():
    text = (ROOT / "Caddyfile").read_text(encoding="utf-8")
    assert "path /ask /feedback" in text and "method POST" in text
    assert "reverse_proxy api:8000" in text and 'respond "Not found" 404' in text
    site = text.split("{$CTA_HOSTNAME} {")[1]
    assert not re.search(r"^\s*log\b", site, re.M)  # no access log directive in the site block
    assert "{$CTA_HOSTNAME}" in text and "admin off" in text


def test_caddys_error_log_drops_the_request_headers_and_addresses():
    # found in the rehearsal: a 502 logged the shared secret and the visitor's X-Real-Ip header
    text = (ROOT / "Caddyfile").read_text(encoding="utf-8")
    fields = ("request>headers", "request>remote_ip", "request>client_ip", "request>remote_port")
    for field in fields:
        assert f"{field} delete" in text, field
    assert "format filter" in text and "wrap json" in text


def test_the_image_runs_as_a_non_root_user_with_code_only():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "USER cta" in text and "tzdata" in text and "uv sync --frozen --no-dev" in text
    assert "COPY config" in text and "COPY db" in text
    # found in the rehearsal: tiktoken could not write its cache as the non-root user
    assert "TIKTOKEN_CACHE_DIR=/opt/tiktoken" in text and "encoding_for_model" in text
    assert "COPY data" not in text and "ENV OPENAI" not in text
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").split()
    for must in (".env", ".git", "data"):
        assert must in ignored


def test_the_vercel_proxy_matches_the_two_paths_caddy_allows():
    proxy = (ROOT / "web" / "proxy.ts").read_text(encoding="utf-8")
    assert '"/api/ask"' in proxy and '"/api/feedback"' in proxy


def test_ci_builds_the_production_image_without_pushing_it():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "docker build" in ci
    assert "docker push" not in ci and "build-push-action" not in ci and "login" not in ci


# ---- the index export and restore, run for real against throwaway databases ----


def docker_db_up() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        db.connect().close()
    except Exception:  # noqa: BLE001
        return False
    return True


@pytest.mark.integration
def test_the_index_round_trip_exports_and_restores_only_the_index_tables(tmp_path):
    if not docker_db_up():
        pytest.skip("the Docker database is not running (docker compose up -d)")
    src, dst = (f"cta_rt_{n}_{uuid.uuid4().hex[:6]}" for n in ("src", "dst"))
    admin = psycopg.connect(db.conninfo(), autocommit=True)
    base = db.conninfo()
    try:
        for name in (src, dst):
            admin.execute(f'CREATE DATABASE "{name}"')
        vec = "[" + ",".join(["0.5"] * 1536) + "]"
        with psycopg.connect(_with_db(base, src)) as c:
            db.migrate(c)
            for i in range(3):
                c.execute(
                    "INSERT INTO chunks (id, kind, source, source_id, doc_type, scope, fetched_at,"
                    " text, content_hash, meta_hash, embedding) VALUES (%s,'page','s','s','faq',"
                    "'city_tech','2026-10-18','text %s','h%s','m%s',%s::vector)",
                    (f"c{i}", i, i, i, vec),
                )
            for i in range(2):
                c.execute(
                    "INSERT INTO calendar_events (id, term, event, source_pdf, verified)"
                    " VALUES (%s,'Fall 2026','event',%s,true)", (f"e{i}", "x.pdf"),
                )  # fmt: skip
            c.execute("INSERT INTO request_logs (question, source) VALUES ('secret q', 'api')")
        with psycopg.connect(_with_db(base, dst)) as c:
            db.migrate(c)
        dump = tmp_path / "index.dump"
        env = {"COMPOSE_ARGS": "-f docker-compose.yml", "PATH": _path()}
        out = subprocess.run(["scripts/export_index.sh", str(dump)], cwd=ROOT, capture_output=True,
                             text=True, env=env | {"CTA_DB": src})  # fmt: skip
        assert out.returncode == 0, out.stderr
        assert "chunks=3 calendar_events=2" in out.stdout
        listing = subprocess.run(
            ["docker", "compose", "-f", "docker-compose.yml", "exec", "-T", "db", "pg_restore",
             "--list"], cwd=ROOT, stdin=dump.open("rb"), capture_output=True, text=True,
        ).stdout  # fmt: skip
        assert "request_logs" not in listing and "eval_runs" not in listing
        out = subprocess.run(["scripts/restore_index.sh", str(dump)], cwd=ROOT, capture_output=True,
                             text=True, env=env | {"CTA_DB": dst})  # fmt: skip
        assert out.returncode == 0, out.stderr
        assert "before: chunks=0 calendar_events=0 request_logs=0" in out.stdout
        assert "after:  chunks=3 calendar_events=2 request_logs=0" in out.stdout
        with psycopg.connect(_with_db(base, dst)) as c:
            assert c.execute("SELECT count(*) FROM request_logs").fetchone()[0] == 0
            ok = c.execute("SELECT count(*) FROM chunks WHERE embedding IS NOT NULL").fetchone()
            assert ok[0] == 3
    finally:
        for name in (src, dst):
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.close()


def test_the_scripts_refuse_a_dump_that_is_not_there_and_are_executable():
    for name in ("export_index.sh", "restore_index.sh"):
        path = ROOT / "scripts" / name
        assert path.stat().st_mode & 0o111, name
        assert "request_logs" in path.read_text(encoding="utf-8")  # the refusal list
    done = subprocess.run(["scripts/restore_index.sh", "/nonexistent.dump"], cwd=ROOT,
                          capture_output=True, text=True)  # fmt: skip
    assert done.returncode == 1 and "no such dump" in done.stderr


def _with_db(conninfo: str, name: str) -> str:
    return psycopg.conninfo.make_conninfo(conninfo, dbname=name)


def _path() -> str:
    import os

    return os.environ["PATH"]


# ---- from test_web_icons.py ----
#
# The tab icons must be valid files: a browser refuses to draw an SVG that is not well-formed XML
# (an XML comment may not hold a double hyphen; that broke the first icon). Standard library only.

APP = ROOT / "web" / "app"


def test_icon_svg_is_well_formed_xml_with_an_svg_root():
    root = ET.parse(APP / "icon.svg").getroot()  # raises ParseError on any XML error
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.attrib["viewBox"] == "0 0 64 64"


def test_icon_svg_keeps_the_design_and_has_no_text_or_image_elements():
    root = ET.parse(APP / "icon.svg").getroot()
    ns = "{http://www.w3.org/2000/svg}"
    tags = {el.tag.removeprefix(ns) for el in root.iter()}
    assert tags == {"svg", "rect", "g", "path", "circle"}
    fills = {el.attrib.get("fill") for el in root.iter() if "fill" in el.attrib}
    assert {"#007fa3", "#ffb35c"} <= fills


def test_no_comment_in_the_svg_holds_a_double_hyphen():
    text = (APP / "icon.svg").read_text(encoding="utf-8")
    for comment in re.findall(r"<!--(.*?)-->", text, re.S):
        assert "--" not in comment


def test_apple_icon_is_a_180_pixel_png():
    data = (APP / "apple-icon.png").read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    assert (width, height) == (180, 180)
