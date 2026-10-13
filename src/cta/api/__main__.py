"""Start the local API: uv run python -m cta.api  (127.0.0.1 only; see /health and /docs)."""

import argparse
import sys

import uvicorn

from cta.api.checks import startup_problems
from cta.settings import load_models

HOST = "127.0.0.1"  # local only until logging and guardrails are in (docs/phase4-plan.md)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m cta.api")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args(argv[1:])
    problems = startup_problems(load_models())
    if problems:
        print("the API cannot start:\n  - " + "\n  - ".join(problems))
        return 2
    uvicorn.run("cta.api.app:create_app", factory=True, host=HOST, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
