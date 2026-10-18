#!/usr/bin/env bash
# Export ONLY the index tables (chunks with their embeddings, and the calendar table) from the running
# database, so a new server needs no re-embedding. request_logs, eval_runs and everything else are never
# exported: the dump is checked and deleted if it holds anything but these two tables.
#
#   scripts/export_index.sh backups/index-2026-10-18.dump
#
# Environment: COMPOSE_ARGS (default "-f docker-compose.yml"; on the server
#   COMPOSE_ARGS="--env-file .env.production -f docker-compose.prod.yml"), CTA_DB (database name,
# default cta). Needs the db service of that stack to be running.
set -euo pipefail

OUT="${1:?usage: scripts/export_index.sh OUT.dump}"
COMPOSE_ARGS="${COMPOSE_ARGS:--f docker-compose.yml}"  # for the production stack: "--env-file .env.production -f docker-compose.prod.yml"
DB="${CTA_DB:-cta}"
# shellcheck disable=SC2086  # the arguments are meant to be split
compose() { docker compose $COMPOSE_ARGS "$@"; }
count() { compose exec -T db psql -U cta -d "$DB" -tA -c "SELECT count(*) FROM $1"; }

mkdir -p "$(dirname "$OUT")"
compose exec -T db pg_dump -U cta -d "$DB" --format=custom --no-owner \
  --table=public.chunks --table=public.calendar_events > "$OUT"

# what the dump holds: only the two tables (and their indexes), never anything else
LIST="$(compose exec -T db pg_restore --list < "$OUT")"
if echo "$LIST" | grep -E 'TABLE( DATA)? public (request_logs|eval_runs|schema_migrations)' >/dev/null; then
  rm -f "$OUT"
  echo "refused: the dump held a table that must not be exported; it was deleted" >&2
  exit 1
fi
TABLES="$(echo "$LIST" | grep -E 'TABLE DATA public' | awk '{print $7}' | sort | tr '\n' ' ')"
[ "$TABLES" = "calendar_events chunks " ] || { rm -f "$OUT"; echo "refused: unexpected tables: $TABLES" >&2; exit 1; }

echo "exported $OUT ($(wc -c < "$OUT") bytes): chunks=$(count chunks) calendar_events=$(count calendar_events)"
