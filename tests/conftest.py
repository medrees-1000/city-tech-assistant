import uuid
from pathlib import Path

import httpx
import pytest

from cta.crawl.fetcher import Fetcher
from cta.crawl.store import RawStore
from cta.index import db

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
