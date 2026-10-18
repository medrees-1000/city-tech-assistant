"""Start the local API: uv run python -m cta.api  (127.0.0.1 only; see /health and /docs)."""

import argparse
import os
import sys

import uvicorn

from cta.api.checks import startup_problems
from cta.settings import load_models

# 127.0.0.1 unless the container sets CTA_API_HOST=0.0.0.0 (docker-compose.prod.yml; the port is
# then reachable only from the other containers, never published to the host)
HOST = os.environ.get("CTA_API_HOST", "").strip() or "127.0.0.1"


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m cta.api")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args(argv[1:])
    problems = startup_problems(load_models())
    if problems:
        print("the API cannot start:\n  - " + "\n  - ".join(problems))
        return 2
    # access_log=False: uvicorn's access log would print every client address to the terminal
    # proxy_headers=False: the visitor address comes only from the shared-secret check in
    # cta.api.guard, never from uvicorn's own forwarded-header handling
    uvicorn.run("cta.api.app:create_app", factory=True, host=HOST, port=args.port,
                access_log=False, proxy_headers=False)  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
