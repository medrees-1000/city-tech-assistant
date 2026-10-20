import uuid
from pathlib import Path

import httpx
import pytest

from cta.crawl.fetcher import Fetcher, RawStore
from cta.index import db

# Where the fixtures in tests/fixtures/ came from:
# - catalog_page.json, catalog_rules.json, rule_shorthand_full.json: real answers of the catalog
#   API (saved 2026-10-11); the nested `departments` objects were trimmed. The page holds the
#   cross-listed trio EET/CET/MECH 3672, a shorthand rule (CST 4900), a course with no rule and
#   non-pilot courses; the rules cover the pilot courses only.
# - page.html, robots_disallow.txt, pages/placeholders_only.html: small hand-written fixtures.
# - pages/*.html: real pages of the 2026-10-11 crawl with only <script>/<style> blocks removed
#   (menu, banner, sidebar and footer stay, so the tests prove they are left out). Several were
#   chosen for a defect: spaces in a mailto link, an empty main div, login links, tab panes,
#   malformed tables, nested contact panels.
# - calendar/winter_2027.pdf, pdfs/*.pdf (refund calendar, Dropping and Withdrawing, Dental
#   Hygiene department PDF) and pdfs/dent_rules.json: the real files. The other PDFs are not
#   committed (data/pdfs/ is git-ignored); tests that need them skip when they are missing.
# - processed/: small samples of processed records for the chunk tests. chain_render_before_*.json
#   and chain_single_render_sha256.json: chain texts (and hashes) saved before two changes, so
#   the tests can prove what changed.
FIXTURES = Path(__file__).parent / "fixtures"
UA = "CityTechAssistantBot/0.1 (student portfolio project; contact: test@example.com)"


class FakeTime:
    """Clock and sleep that never really wait, so rate-limit tests are instant."""

    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def fake_time():
    return FakeTime()


@pytest.fixture
def make_fetcher(tmp_path, fake_time):
    """Build a Fetcher over a mocked transport. `handler(request) -> httpx.Response`."""

    def build(handler, hosts=("www.citytech.cuny.edu",)):
        client = httpx.Client(transport=httpx.MockTransport(handler))
        store = RawStore(tmp_path / "raw")
        fetcher = Fetcher(
            client, store, UA, set(hosts), clock=fake_time.clock, sleep=fake_time.sleep
        )
        return fetcher, store

    return build


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture
def conn():
    """A connection whose tables live in a throwaway schema, dropped afterwards; the real tables are
    never touched. Skips with a clear message when Postgres is not running."""
    try:
        c = db.connect()
    except Exception as e:
        pytest.skip(f"Postgres not available ({type(e).__name__}); run: docker compose up -d")
    schema = f"test_{uuid.uuid4().hex[:8]}"
    with c:
        c.execute(f"CREATE SCHEMA {schema}")
        c.execute(f"SET search_path TO {schema}, public")
        for path in db.migration_files():
            c.execute(path.read_text(encoding="utf-8"))
        c.commit()
        try:
            yield c
        finally:
            c.rollback()
            c.execute(f"DROP SCHEMA {schema} CASCADE")
            c.commit()


@pytest.fixture(autouse=True)
def no_real_model_client_in_the_api(monkeypatch):
    """The API looks its default model client up at call time; a test that forgot to inject one
    must fail loudly instead of making a paid call."""
    import cta.api.app as api_app

    def refuse():
        raise AssertionError("a test tried to create the real OpenAI client")

    monkeypatch.setattr(api_app, "make_client", refuse)


# Tests marked `needs_data` read the collected data (course records, contact records, the rules
# cache) that is git-ignored and not in a fresh clone. They skip with a reason when it is absent;
# no assertion is changed. How to build the data: docs/running.md.
ROOT = Path(__file__).resolve().parent.parent
DATA_FILES = (
    ROOT / "data" / "processed" / "courses",
    ROOT / "data" / "processed" / "contacts" / "registrar.json",
    ROOT / "data" / "processed" / "rules_cache.json",
)


def collected_data_present() -> bool:
    return all(path.exists() for path in DATA_FILES)


def pytest_collection_modifyitems(config, items):
    if collected_data_present():
        return
    skip = pytest.mark.skip(reason="needs data/processed; see docs/running.md")
    for item in items:
        if "needs_data" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="module")
def events():
    """The verified calendar rows (shared by the router, advice and contact tests)."""
    from cta.graph import build

    return build.load_events()
