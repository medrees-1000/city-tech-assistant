from pathlib import Path

import httpx
import pytest

from cta.crawl.fetcher import Fetcher
from cta.crawl.store import RawStore

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
