"""Write docs/section-index.md: every indexable section, for choosing eval gold_sources.

Run: uv run python scripts/make_section_index.py
"""

import json
from pathlib import Path

from cta.index.section_index import course_counts, load_rows, render

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    processed = ROOT / "data" / "processed"
    rows, left_out = load_rows(processed)
    events = json.loads((ROOT / "data" / "calendar" / "calendar_events.json").read_text("utf-8"))
    text = render(rows, left_out, events, course_counts(processed))
    (ROOT / "docs" / "section-index.md").write_text(text, encoding="utf-8")
    print(f"{len(rows)} sections written to docs/section-index.md")


if __name__ == "__main__":
    main()
