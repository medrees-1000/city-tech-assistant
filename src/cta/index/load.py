"""Load chunks into Postgres, embedding only what is new or changed.

    uv run python -m cta.index.load --dry-run   # no API call, no write: counts and estimated cost
    uv run python -m cta.index.load             # prints the dry-run summary and stops
    uv run python -m cta.index.load --yes       # real run

Without --yes nothing is changed (even metadata-only edits and deletions), so a command never
surprises you. The whole write is one transaction.
"""

import subprocess
import sys
from dataclasses import dataclass, field

from cta.index import chunks as chunk_builder
from cta.index.db import connect
from cta.index.embed import ApiError, embed_texts, make_client
from cta.settings import cost_usd, load_models

COLUMNS = (
    "id", "kind", "source", "source_id", "doc_type", "department", "scope", "term", "terms",
    "fetched_at", "last_updated", "heading_path", "heading_url", "merged_section_ids", "text",
    "content_hash", "meta_hash",
)  # fmt: skip


@dataclass
class Plan:
    new: list[dict] = field(default_factory=list)
    changed: list[dict] = field(default_factory=list)  # content_hash or embedding model differs
    meta_only: list[dict] = field(default_factory=list)  # only meta_hash differs
    unchanged: list[dict] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)  # ids in the database, no longer built

    @property
    def to_embed(self) -> list[dict]:
        return self.new + self.changed

    @property
    def has_writes(self) -> bool:
        return bool(self.to_embed or self.meta_only or self.stale)


def make_plan(chunks: list[dict], existing: dict[str, tuple], model: str) -> Plan:
    """Compare built chunks with database rows {id: (content_hash, meta_hash, embedding_model)}."""
    plan = Plan()
    for c in chunks:
        row = existing.get(c["id"])
        if row is None:
            plan.new.append(c)
        elif row[0] != c["content_hash"] or row[2] != model:
            plan.changed.append(c)
        elif row[1] != c["meta_hash"]:
            plan.meta_only.append(c)
        else:
            plan.unchanged.append(c)
    built = {c["id"] for c in chunks}
    plan.stale = sorted(set(existing) - built)
    return plan


def existing_rows(conn) -> dict[str, tuple]:
    rows = conn.execute("SELECT id, content_hash, meta_hash, embedding_model FROM chunks")
    return {r[0]: (r[1], r[2], r[3]) for r in rows}


def estimate(plan: Plan, count, cfg: dict) -> tuple[int, float]:
    tokens = sum(count(c["text"]) for c in plan.to_embed)
    return tokens, cost_usd(cfg, cfg["embedding_model"], tokens)


def summary(plan: Plan, tokens: int, cost: float, cfg: dict) -> str:
    return "\n".join(
        [
            f"new {len(plan.new)}, changed {len(plan.changed)}, "
            f"metadata-only {len(plan.meta_only)}, unchanged {len(plan.unchanged)}, "
            f"stale {len(plan.stale)}",
            f"to embed: {len(plan.to_embed)} chunks, about {tokens} tokens, estimated "
            f"${cost:.5f} ({cfg['embedding_model']})",
        ]
    )


def apply_plan(conn, plan: Plan, vectors: list[list[float]], cfg: dict) -> None:
    """Upsert, update metadata and delete stale rows in one transaction."""
    cols = ", ".join(COLUMNS)
    marks = ", ".join(["%s"] * len(COLUMNS))
    with conn.transaction():
        for c, vector in zip(plan.to_embed, vectors, strict=True):
            sets = ", ".join(f"{k} = EXCLUDED.{k}" for k in COLUMNS[1:])
            conn.execute(
                f"INSERT INTO chunks ({cols}, embedding, embedding_model, updated_at) "
                f"VALUES ({marks}, %s, %s, now()) ON CONFLICT (id) DO UPDATE SET {sets}, "
                "embedding = EXCLUDED.embedding, embedding_model = EXCLUDED.embedding_model, "
                "updated_at = now()",
                [c[k] for k in COLUMNS] + [vector, cfg["embedding_model"]],
            )
        for c in plan.meta_only:
            sets = ", ".join(
                f"{k} = %s" for k in COLUMNS if k not in ("id", "text", "content_hash")
            )
            conn.execute(
                f"UPDATE chunks SET {sets}, updated_at = now() WHERE id = %s",
                [c[k] for k in COLUMNS if k not in ("id", "text", "content_hash")] + [c["id"]],
            )
        if plan.stale:
            conn.execute("DELETE FROM chunks WHERE id = ANY(%s)", (plan.stale,))


def self_check(conn) -> str:
    """The nearest neighbour of one stored chunk's own embedding must be that chunk."""
    row = conn.execute(
        "SELECT a.id, (SELECT b.id FROM chunks b WHERE b.embedding IS NOT NULL "
        "ORDER BY b.embedding <=> a.embedding LIMIT 1) "
        "FROM chunks a WHERE a.embedding IS NOT NULL ORDER BY a.id LIMIT 1"
    ).fetchone()
    if row is None:
        return "self-check: no embedded rows"
    return f"self-check: {row[0]} -> nearest {row[1]} ({'OK' if row[0] == row[1] else 'FAILED'})"


def report(conn, tokens: int, cost: float) -> str:
    total = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
    nulls = conn.execute("SELECT count(*) FROM chunks WHERE embedding IS NULL").fetchone()[0]
    return "\n".join(
        [
            f"rows in chunks: {total}; rows with NULL embedding: {nulls}",
            f"API tokens: {tokens}; real cost: ${cost:.5f}",
            self_check(conn),
        ]
    )


def validate_passes() -> bool:
    """`python -m cta.validate` must exit 0 (nothing is indexed until the checks pass)."""
    done = subprocess.run([sys.executable, "-m", "cta.validate"], capture_output=True, text=True)
    return done.returncode == 0


def run(
    conn, chunks, cfg, count, client_factory, yes, dry_run, validate=validate_passes, out=print
):
    """Returns the exit code."""
    if not validate():
        out("refused: `python -m cta.validate` fails; fix the data first (nothing was changed)")
        return 1
    plan = make_plan(chunks, existing_rows(conn), cfg["embedding_model"])
    tokens, cost = estimate(plan, count, cfg)
    out(summary(plan, tokens, cost, cfg))
    if dry_run:
        out("dry run: no API call, nothing written")
        return 0
    if plan.has_writes and not yes:
        out("nothing was changed; run again with --yes to apply")
        return 0
    cap = cfg["eval"]["max_cost_usd"]
    if cost > cap:
        out(f"refused: estimated ${cost:.4f} is above eval.max_cost_usd ${cap}")
        return 1
    vectors, real_tokens = [], 0
    if plan.to_embed:
        vectors, real_tokens = embed_texts(
            client_factory(),
            cfg["embedding_model"],
            [c["text"] for c in plan.to_embed],
            cfg["embedding_dimensions"],
        )
    if plan.has_writes:
        apply_plan(conn, plan, vectors, cfg)
        conn.commit()  # apply_plan is one (sub)transaction; this makes it durable
    out(report(conn, real_tokens, cost_usd(cfg, cfg["embedding_model"], real_tokens)))
    return 0


def main(argv: list[str]) -> int:
    flags = set(argv[1:])
    if not flags <= {"--dry-run", "--yes"}:
        print("usage: python -m cta.index.load [--dry-run] [--yes]")
        return 2
    cfg, count = load_models(), chunk_builder.token_counter()
    try:
        chunks = chunk_builder.build_chunks(cfg=cfg, count=count)
        with connect() as conn:
            return run(
                conn, chunks, cfg, count, make_client, "--yes" in flags, "--dry-run" in flags
            )
    except (ValueError, ApiError) as e:
        print(f"failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
