#!/usr/bin/env bash
# Restore the index tables from a dump made by export_index.sh into a database that has been migrated
# (the migrate service of the production stack does that on every start). It replaces chunks and
# calendar_events only; request_logs and the rest are not touched. Prints the row counts before and after.
#
#   scripts/restore_index.sh backups/index-2026-10-18.dump
#
# Environment: COMPOSE_FILE (default docker-compose.yml), ENV_FILE (optional), CTA_DB (default cta).
set -euo pipefail

DUMP="${1:?usage: scripts/restore_index.sh DUMP}"
[ -s "$DUMP" ] || { echo "no such dump: $DUMP" >&2; exit 1; }
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
DB="${CTA_DB:-cta}"
compose() { docker compose ${ENV_FILE:+--env-file "$ENV_FILE"} -f "$COMPOSE_FILE" "$@"; }
count() { compose exec -T db psql -U cta -d "$DB" -tA -c "SELECT count(*) FROM $1" 2>/dev/null || echo "none"; }

LIST="$(compose exec -T db pg_restore --list < "$DUMP")"
if echo "$LIST" | grep -E 'TABLE( DATA)? public (request_logs|eval_runs|schema_migrations)' >/dev/null; then
  echo "refused: this dump holds a table that is not an index table" >&2
  exit 1
fi

echo "before: chunks=$(count chunks) calendar_events=$(count calendar_events) request_logs=$(count request_logs)"
compose exec -T db pg_restore -U cta -d "$DB" --clean --if-exists --no-owner --exit-on-error < "$DUMP"
echo "after:  chunks=$(count chunks) calendar_events=$(count calendar_events) request_logs=$(count request_logs)"
