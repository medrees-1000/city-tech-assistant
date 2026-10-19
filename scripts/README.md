# Scripts

One-off and operations helpers. Run them from the repo root with `uv run python scripts/<name>.py`
unless noted. They are not part of the app and ruff does not check them.

## Operations (used by the deploy runbook)
- `smoke_live.py`: sends about 14 `/ask` requests to a running API (direct, Caddy or the Vercel page) and
  prints a pass/fail table. Run after every deploy; wait about 70 seconds between runs. Costs a few cents.
  See `docs/deploy-runbook.md` for the exact commands.
- `export_index.sh`: dumps only the index tables (chunks with embeddings, calendar) so a new server needs
  no re-embedding. Run before moving to a new server.
- `restore_index.sh`: loads such a dump into a migrated database. Run once on the new server.

## Reproduce the README numbers (no network, no cost)
- `readme_numbers.py`: prints the README and `docs/results.md` tables from the committed files in
  `eval/results/`. Run: `python3 scripts/readme_numbers.py`.
- `recompute_final.py`: recomputes the final-run headline numbers from scratch as a check.
  Run: `python3 scripts/recompute_final.py final-run`. It exits with 1 when four retrieval numbers differ
  from the stored ones, because the table-merge map is not passed (see the file's docstring).

## Build or refresh generated files
- `make_section_index.py`: rewrites `docs/section-index.md` (section ids for choosing eval gold sources)
  from `data/processed`. Run after the data is rebuilt.
- `make_eval_review.py`: writes `docs/eval-review.md` (each question with its gold sources). The committed
  copy was removed because it was out of date; run it when you need one.
- `make_manual_check_docs.py`: writes the blank manual-check sheets for programs and contacts into
  `docs/archive/`. Run when the department data is rebuilt and you want to hand-check it.
- `export_final_answers.py`: copies the stored answers of an eval run from the database to
  `eval/results/<label>-answers.jsonl`, because `request_logs` is purged after 30 days.

## Data access check
- `test_catalog_api.py`: shows that the public catalog API can be read without logging in (2 requests).
  Despite the name it is a script, not a pytest test.
