#!/usr/bin/env python3
"""TEMPORARY (docs/decisions.md, visitor_tag): read the API's /ask log lines on stdin and print, for
the visitor key and for each candidate address header, how many distinct tags it produced and how
often each appeared. One stable visitor shows 1 distinct tag for the header that identifies them.

    docker compose --env-file .env.production -f docker-compose.prod.yml logs --no-log-prefix --since 20m api \
        | uv run python scripts/tag_counts.py
"""

import json
import sys
from collections import Counter


def counts(lines) -> dict[str, Counter]:
    out: dict[str, Counter] = {}
    for line in lines:
        start = line.find('{"event": "ask"')
        if start < 0:
            continue
        row = json.loads(line[start:])
        tags = {
            "visitor_key (used by the limiter)": row.get("visitor_tag"),
            **row.get("addr_tags", {}),
        }
        for name, tag in tags.items():
            out.setdefault(name, Counter())[tag or "missing"] += 1
    return out


def main() -> None:
    for name, c in counts(sys.stdin).items():
        distinct = len([t for t in c if t != "missing"])
        print(f"{name}: {distinct} distinct  {dict(c.most_common())}")


if __name__ == "__main__":
    main()
