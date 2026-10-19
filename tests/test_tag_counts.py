"""scripts/tag_counts.py: distinct tags per candidate header, from the API's /ask log lines."""

import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "tag_counts", Path(__file__).resolve().parents[1] / "scripts" / "tag_counts.py"
)
tag_counts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tag_counts)


def line(tag, real, visitor):
    row = {
        "event": "ask",
        "visitor_tag": tag,
        "addr_tags": {"x-real-ip": real, "x-cta-visitor": visitor},
    }
    return "2026-10-19T12:00:00.1Z " + json.dumps(row)


def test_counts_distinct_tags_per_header_and_skips_other_lines():
    out = tag_counts.counts([
        line("aaaaaa", "111111", "222222"), "INFO: something else",
        line("bbbbbb", "333333", "222222"), line("aaaaaa", None, "222222"),
    ])  # fmt: skip
    assert out["visitor_key (used by the limiter)"] == {"aaaaaa": 2, "bbbbbb": 1}
    assert out["x-cta-visitor"] == {"222222": 3}
    assert out["x-real-ip"] == {"111111": 1, "333333": 1, "missing": 1}
