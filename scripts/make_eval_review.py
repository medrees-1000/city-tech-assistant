"""Write docs/eval-review.md from eval/questions.jsonl and the processed data.

Run: uv run python scripts/make_eval_review.py
"""

from pathlib import Path

from cta.eval.questions import load_gold_data, load_questions
from cta.eval.review import render

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    text = render(load_questions(), load_gold_data())
    (ROOT / "docs" / "eval-review.md").write_text(text, encoding="utf-8")
    print(f"{len(text)} characters written to docs/eval-review.md")


if __name__ == "__main__":
    main()
