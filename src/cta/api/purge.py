"""Delete old API request logs: uv run python -m cta.api.purge --days 30 [--dry-run]

Only rows with source = 'api' are ever deleted; eval-run rows are never touched.
"""

import argparse
import sys

from cta.index.db import connect

WHERE = "source = 'api' AND ts < now() - make_interval(days => %s)"


def purge(conn, days: int, dry_run: bool = False) -> int:
    """The number of API rows older than `days` days; they are deleted unless dry_run."""
    count = conn.execute(f"SELECT count(*) FROM request_logs WHERE {WHERE}", (days,)).fetchone()[0]
    if not dry_run:
        conn.execute(f"DELETE FROM request_logs WHERE {WHERE}", (days,))
        conn.commit()
    return count


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m cta.api.purge")
    p.add_argument("--days", type=int, required=True, help="delete API rows older than this")
    p.add_argument("--dry-run", action="store_true", help="only show how many would be deleted")
    args = p.parse_args(argv[1:])
    if args.days < 1:
        print("--days must be at least 1")
        return 2
    with connect() as conn:
        count = purge(conn, args.days, args.dry_run)
    prefix = "dry run: " if args.dry_run else ""
    verb = "would be deleted" if args.dry_run else "deleted"
    print(
        f"{prefix}{count} API rows older than {args.days} days {verb} (eval rows are never touched)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
