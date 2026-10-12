# Phase 2 plan: chunk, embed, vector-only baseline

**Where we are (2026-10-12):** steps 1 to 7 done. The baseline retrieval numbers on dev are saved
(`eval/results/baseline-retrieval-dev.json`, label `baseline-retrieval-dev`, also in `eval_runs`). The test split has
not been run (`--split test` is refused without `--final`; only step 9 uses it). Next is step 8 (prompt, abstain
threshold from dev scores, `request_logs`, first answers; this is the first step that calls the chat model, so show
the cost estimate first). A new session: read this file, `config/models.yaml`, `docs/decisions.md`, then continue
at the first step not marked done.

Original status: plan only (2026-10-11). No code, no installs, no containers started. Everything here is for the owner
to approve or change. Scope is CLAUDE.md Phase 2: "chunk, embed, vector-only RAG; record metrics". Not in scope:
hybrid search, reranker, term filtering, LangGraph, FastAPI, UI (Phases 3 and 4).

Numbers below come from the data on disk today (534 embedded sections, 197 courses, 9 contact owners).

## a) Chunking spec

One chunk kind per row of the `chunks` table:

| Kind | Source | One chunk per | Count |
|---|---|---|---|
| section | pages, PDFs, departments: records with `index: true`, sections not `embed: false` | embedded section, after `merge_tables_into_parents` | 413 (534 sections; 121 table sections merge into their parent) |
| course | `data/processed/courses/**` (197 records) | course record | 197 |
| contact | `data/processed/contacts/*.json` | owner (4 departments, 5 offices) | 9 |
| | calendar events | **not chunked**: answered from the `calendar_events` table | 0 |
| | | **Total** | **619** |

**Text to embed**
- section: heading path (parents + heading, " > ") + blank line + body markdown. A merged table keeps its own
  heading, as `merge_tables_into_parents` already does.
- course: `CODE - Title`, credits, department, description, "Prerequisites: <resolved text>", and the programs
  that list it (from the course record). Cross-listed courses are separate chunks, never merged.
- contact: owner name (for example "Bursar"), then the CONTACT US block (address, room, phone, email) and the
  hours, as printed. This makes "what is the bursar's phone" retrievable. The page-level contact blocks stay
  `embed: false` (they are not chunked per page); the per-owner record is the only contact source. The PDF
  "Chair" blocks stay out.
- Metadata is not part of the embedded text.

**Metadata per chunk** (Data rules): `source` (source_url or source_file), `doc_type`, `department` (null allowed),
`scope`, `term` and `terms`, `fetched_at` or file date, `last_updated` (null allowed), plus `kind`,
`source_id` (section id, `catalog:<CODE>`, or `contact:<owner>`), `merged_section_ids` (so eval labels at section
level still match a merged chunk), `heading_path`, `heading_url`. Contact chunks get doc_type `contacts`, scope
`city_tech` (offices) or `department`. Course chunks get doc_type `catalog_course`, scope `city_tech`, source
`catalog_course`, department from the record, date = the course record's `fetched_at`.

**Size.** The largest section is 5,387 characters; after merging tables the largest chunk is **6,868 characters**
(the EET root page "Welcome ..." section, with an advisement table merged in). Median 578, 95th percentile
3,762; no chunk over 8,000 characters. That is about 1,700 to 2,300 tokens, well under the 8,191-token input
limit of `text-embedding-3-small` (I will confirm the limit on the model page in step 3). **No chunk needs
splitting.** I will not split. Safeguard: the loader counts tokens (tiktoken) and fails, instead of silently
truncating, if a chunk is over `max_chunk_tokens` (default 6,000). If that ever happens, the proposal is to split
at block boundaries (paragraphs, list, table row groups) into parts of about 1,500 tokens, repeat the heading
path at the top of each part, give ids `<id>~part2`, and keep the metadata.

Known limitation, not a Phase 2 task: the 115 program chunks include large degree-map tables (up to 6.3k
characters) that embed poorly. Phase 3 can look at them; Phase 2 reports how they retrieve.

## b) Schema, Docker, loading

`docker-compose.yml` is empty today (tracked, 0 bytes). Plan: one service `db`, image `pgvector/pgvector`
(a pinned Postgres 17 tag, confirmed when I write it), port bound to `127.0.0.1:5432`, a named volume, password
from `.env`, a healthcheck. No other services in Phase 2.

Schema files in `db/migrations/001_init.sql`, applied by `uv run python -m cta.index.db migrate` (plain SQL, no
Alembic; a `schema_version` table).

```
chunks
  id text primary key              -- stable: section id, "catalog:<CODE>", "contact:<owner>"
  kind text                        -- section | course | contact
  source text, source_id text, doc_type text, department text, scope text
  term text, terms text[], fetched_at text, last_updated text
  heading_path text, heading_url text, merged_section_ids text[]
  text text                        -- exactly what is embedded
  content_hash text                -- sha256(text + embedding_model + dimensions)
  meta_hash text                   -- sha256(metadata json), so metadata edits do not re-embed
  embedding vector(1536)           -- dimension follows the model; see below
  embedding_model text
  tsv tsvector                     -- left NULL in Phase 2 (Phase 3: hybrid search)
  updated_at timestamptz
calendar_events                    -- the calendar_events.json fields, one row per event
  id text primary key, term, event, date_start date null, date_end date null, date_raw, weekday_raw,
  applies_to, source_pdf, source_page, pdf_last_updated date, verified bool, verified_by, verified_on, notes
eval_runs
  id serial primary key, run_at timestamptz, label text, git_commit text, split text,
  config jsonb (models, k values, today, threshold), metrics jsonb, per_question jsonb, cost jsonb
request_logs
  id bigserial primary key, ts timestamptz, run_id int null references eval_runs, question text,
  today date, retrieved jsonb (chunk ids and scores), answer text, abstained bool, abstain_reason text,
  chat_model text, prompt_tokens int, completion_tokens int, embedding_tokens int, cost_usd numeric,
  latency_ms int
```

**Personal data in logs.** `cta.redact.redact()` (written in step 1, tested) replaces emails, SSN-like numbers,
phone numbers and 8-digit CUNY EMPLIDs with `[EMAIL]`, `[SSN]`, `[PHONE]`, `[ID]`. Every place that stores a
question (`request_logs.question`, `eval_runs.per_question`, result files) must call it first; the same text is
then what the model sees only if the caller chooses, but the stored copy is always redacted.

No vector index in Phase 2: with 619 rows an exact cosine scan is instant and gives exact recall for the
baseline. An HNSW index is a Phase 3 or 4 decision. The vector column is tied to the model's dimension
(1536 for the proposed model); the loader refuses to mix models and re-embeds everything if the configured model
or dimension changed.

**Loading** (`uv run python -m cta.index.load`, `--dry-run` first): (1) build all chunks from `data/processed`
with a pure function (no database, fully unit-tested); (2) compare `content_hash` with the table; embed only
new or changed chunks, in batches; (3) update metadata when only `meta_hash` changed; (4) delete chunks that no
longer exist; (5) report counts: new, re-embedded, metadata-only, deleted, unchanged, tokens, cost.
`calendar_events` is reloaded in one transaction from `load_events_for_indexing`, which already refuses to load
if any event is unverified. The loader also refuses to run unless the validation command passes.

## c) Models, tokens, cost

**Counted today** (tiktoken is not installed and I was told not to install anything, so tokens are estimated from
characters): 619 chunks, 565,287 characters = **about 141,000 tokens at 4 characters per token, 188,000 at 3**
(markdown tables and codes are denser). Step 3 adds tiktoken and replaces the estimate with an exact count
before anything is sent.

**Models (checked 2026-10-12; approved change: do not rely on memory).** Pages read on 2026-10-12, none of which
prints its own date: `developers.openai.com/api/docs/pricing` (newest entry mentioned: July 30, 2026),
`.../models`, `.../models/gpt-6-luna`, `.../models/gpt-5.6-terra`, `.../guides/embeddings`, and
`.../deprecations` (newest entry 2026-10-01). `platform.openai.com/docs/*` now redirects there. Prices are USD per
1M tokens, standard tier.

| Role | Model | Price (in / cached / out) | Input limit | Note |
|---|---|---|---|---|
| Embedding (pick) | `text-embedding-3-small` | $0.02 / - / - | 8,192 tokens, 1,536 dims | not deprecated; no newer embedding model on the pages |
| Embedding (alt.) | `text-embedding-3-large` | $0.13 | 8,192, 3,072 dims | 6.5x the cost; only if retrieval is weak |
| Answers (pick) | `gpt-6-luna` | $0.10 / $0.01 / $0.50 | 1.05M context, 128K output | the models page lists it as the efficient high-volume model; cheaper than gpt-4o-mini |
| Judge (pick) | `gpt-5.6-terra` | $2.00 / $0.20 / $12.00 | 1.05M, 128K output | "balances intelligence and cost", mini tier of the earlier GPT-5 family; a different and stronger model than the answer model |
| Not chosen | `gpt-4o-mini` | $0.15 / $0.075 / $0.60 | | still listed and not deprecated, but older; only kept in the price table |
| Not chosen | `gpt-4.1-mini` | $0.40 / $0.10 / $1.60 | | not deprecated; `gpt-4.1-nano` shuts down 2026-10-23 and `gpt-5-mini-2025-08-07` on 2026-12-11 (both avoided) |
| Not chosen | `gpt-6.1-sol` | $2.00 / $0.10 / $10.00 | | on the pricing page only; I did not read its model page, so it is a candidate judge, not a pick |

Open point for step 8: the Luna and Terra model pages list `reasoning.effort` and do not say whether `temperature`
and `top_p` are accepted. The config keeps 0.1 / 0.3 and `reasoning_effort: none`, marked "not confirmed"; step 8
checks with one real call before relying on them, and records the result in `docs/decisions.md`.

**Cost with the picks** (embedding unchanged: 141k to 188k tokens, about $0.003 to $0.004 once):

| What | Cost |
|---|---|
| One answer, k=5 (about 2,200 in, 250 out) on `gpt-6-luna` | about $0.0003 |
| Dev answers (20 questions) | about $0.006 |
| Judge, about 16 answers x 2 calls x 3k tokens in, 300 out, on `gpt-5.6-terra` | about $0.20 |
| Whole baseline (embed, retrieval, dev answers, judge, 8 reviewed verdicts included) | **under $0.35**, well under `eval.max_cost_usd` ($1) |

**Swapping** (nothing hard-coded): `config/models.yaml` holds the defaults (embedding model, chat model, judge model, temperature, top_p,
`max_chunk_tokens`, a price table with dimensions per model, `eval.max_cost_usd`; written in step 1); `.env`
overrides with `CTA_EMBEDDING_MODEL`, `CTA_CHAT_MODEL`, `CTA_JUDGE_MODEL`; secrets only in `.env`:
`OPENAI_API_KEY`, `POSTGRES_PASSWORD` (and `DATABASE_URL` if the defaults do not fit). `.env.example` lists the
keys without values. Loaded by `cta.settings` (existing module). Models not in the price table are refused, so
a swap needs a price entry and cost is never shown as zero by accident.

## d) Baseline retrieval and answers

- Retrieval: embed the question, `ORDER BY embedding <=> query LIMIT k` over all chunks of all kinds. Cosine
  similarity, **no filters**, k in {1, 3, 5, 10}. Retrieve 10 once and slice for the smaller k.
- Answers use k = 5 (config), one model call per question.
- **Prompt layout (for provider prompt caching later):** static instructions first, then the numbered sources,
  then today's date and the question last. Nothing that changes per request goes before the sources.
- Prompt rules (CLAUDE.md "Answer behavior"): answer only from the numbered sources; cite the source URL or file
  after every factual claim; today's date is in the prompt (config `eval.today` = 2026-10-11 for
  reproducible runs, real date otherwise); if the sources do not cover the question, say "I don't know" and give
  the office contact from the sources; no advice or judgment (state the rules and the deadline); when a source
  states a term, say which term it is (the Phase 3 term rule in `docs/decisions.md` comes later; the baseline
  only passes `terms` along in the source header); calendar questions are not answerable in the baseline (no
  calendar tool until Phase 3), and that is recorded, not hidden. `temperature` 0.1 and `top_p` 0.3 (if the model accepts them; see the open point above).
- Abstain rule, one parameter: if the top-1 cosine similarity is below `abstain_threshold`, do not call the chat
  model; return a fixed "I don't know" message plus the contact from the best-scoring contact chunk (one extra
  query restricted to `kind = 'contact'`, used only for this message). The threshold is chosen once by reading
  the top-1 score distribution of answerable vs unanswerable questions on **dev only**, written down in
  `docs/decisions.md`, and not changed after seeing test.

## e) Eval runner (`uv run python -m cta.eval.run`)

| Metric | Questions | Notes |
|---|---|---|
| recall@k, precision@k, hit rate@k, MRR (k = 1, 3, 5, 10) | the 22 questions whose gold sources include sections or courses (q01-q10, q13-q22, q24, q30) | section-level labels: a chunk counts when its `source_id` or `merged_section_ids` contains the gold id; calendar gold sources are not scored by retrieval (not chunked), so q11 and q12 are excluded and q09 and q10 are scored on their page source only |
| abstention accuracy | q25-q29 (expected ABSTAIN): rule-based (the threshold fired, or the answer starts "I don't know") | also reports false abstentions on answerable questions |
| clarify and no-advice behavior | q23, q24 (CLARIFY) and q30 (NO ADVICE) | LLM-judged against the instruction in `gold_answer`, with the abstain rows |
| answer correctness, faithfulness | **dev split only**, answerable questions with a written gold answer | LLM-judged: correctness against `gold_answer`, faithfulness against the retrieved chunks |
| cost per request, latency | every request | from the API usage fields and a timer |

- **Judge:** a different and stronger model than the answer model (`judge_model`). In step 9 I print 8 judge
  verdicts (question, gold answer, answer, verdict, reason) for the owner to check by hand, and log how many the
  owner agrees with in `docs/validation-log.md`; the judge numbers are reported with that agreement rate.
- **Failure labels (step 9):** every failed question gets exactly one of: `retrieval miss` (gold source not in
  the top 10), `ranking miss` (in the top 10 but not in the top 5 used for the answer), `generation error` (gold
  source in the top 5 but the answer is wrong or unfaithful), `abstention error` (abstained when it should have
  answered, or answered when it should have abstained), `not supported yet` (calendar and prerequisite-chain
  questions; Phase 3 tools). The counts per label go in the results table.
- Splits: retrieval metrics are computed for dev and test separately and both are saved, but every decision (k,
  threshold, prompt) uses dev only. The 10 test questions are run for answers once, at the end of Phase 2, only
  when the owner says so.
- **Cost shown before running**: `--dry-run` prints the number of API calls, estimated tokens and dollars from the
  config prices; a real run needs `--yes` and aborts if the estimate exceeds `eval.max_cost_usd` (default $1).
  Retrieval-only runs cost only the question embeddings (30 questions, a fraction of a cent) and need no
  confirmation.
- Output: `eval/results/<run_id>.json` (config, per-question retrieved ids and scores, answers, judge verdicts,
  metrics, cost) and a short `eval/results/<run_id>.md` summary, both committed; the same row goes to
  `eval_runs`, and each request to `request_logs`. The accepted baseline is copied to
  `eval/results/baseline.json`.
- Comparison: `uv run python -m cta.eval.compare eval/results/baseline.json eval/results/<run>.json` prints every
  metric with its change, and per question which gold sections were gained or lost. One change per run, as
  CLAUDE.md requires. No CI gate yet (Phase 4).

## f) Dependencies and manual setup

New dependencies (each added in the step that needs it, with the reason):
- `psycopg[binary]` (v3): the Postgres driver. Boring, maintained, no compiler needed.
- `pgvector` (Python package): registers the vector type with psycopg; about 20 lines of code otherwise.
- `openai`: the official client for embeddings and chat; gives retries, typed usage fields (needed for the
  cost logs). `httpx` could do it by hand, but retries and usage parsing are not worth rewriting.
- `tiktoken`: exact token counts for cost and for the `max_chunk_tokens` guard.

Not added now: LangChain, LangGraph, FastAPI, numpy, Alembic, a test-container library. Database tests use the
Docker database and are skipped when it is not running; everything else (chunking, hashing, metrics, prompt
building) is plain functions tested without a database or network.

Needed from the owner, by hand:
1. Docker is available (checked below). Start it when I ask; I will not start containers on my own.
2. `OPENAI_API_KEY` in `.env`, and a **spending cap** on the OpenAI project (a monthly budget of a few dollars
   is plenty; the whole baseline is estimated under $0.15).
3. `POSTGRES_PASSWORD` in `.env` (any local value) and port 5432 free on localhost.
4. Approve or change: the two models, `max_cost_usd`, and the pinned pgvector image tag.

Environment check (2026-10-11): `docker --version` is 29.3.1, `docker compose version` is v5.1.1, the daemon
answers (`docker info` server 29.3.1). One old exited container exists from another project; nothing was started
or changed.

## g) Ordered steps (one commit per step; what I show after each)

1. **DONE (132ffb7). Config and settings.** `config/models.yaml`, `.env.example` keys, settings loader with env overrides and
   a price table, tests. Show: the resolved config (secrets hidden).
2. **DONE (fb7b842). Docker and schema.** Fill `docker-compose.yml`, `db/migrations/001_init.sql`, `cta.index.db migrate`,
   tests that run when the database is up. You start the container. Show: `docker compose ps`, the table list.
3. **DONE (aaab39e). Chunk builder (no network).** Pure functions for the three chunk kinds, hashes, `--dry-run` report; add
   tiktoken. Show: chunk counts per kind and doc_type, exact token total, the 10 longest chunks, three sample
   chunks of each kind, the cost estimate.
4. **DONE (a878e8c). Embedding client and loader.** Embed and upsert, hash-based skip, delete. Needs your key and approval of
   the exact cost shown by the dry run. Show: counts, tokens, dollars; a second run that re-embeds 0.
5. **DONE (b1be84f). Calendar loader.** `calendar_events` table from the verified file. Show: row counts per term and a few
   queries (SAP deadlines, the TBA row).
6. **DONE (0066e19). Retrieval.** `cta.eval.retrieve` and a `search` command (no chat model). Show: top 5 with scores for six
   sample questions, including one unanswerable and one calendar question.
7. **DONE (674648d). Retrieval metrics.** The runner without any LLM call, results saved, baseline retrieval numbers on dev and
   test. Show: the metric table by k, per-question hits and misses, and the top-1 score distribution that
   informs the abstain threshold.
8. **Answers, abstain rule, logs.** Prompt, threshold (decision recorded in `docs/decisions.md`), `request_logs`.
   Show: answers for four dev questions, with citations, an abstention, and the cost lines.
9. **LLM-judged metrics and the baseline run.** Dry run with the cost, then (with your yes) the dev run; save the
   baseline, write the `docs/validation-log.md` entry, README-ready results table. Show: all metrics, the
   failures with their retrieved chunks, and what I think the main weakness is. Then stop; Phase 3 starts from
   the baseline numbers.

Each step runs `ruff`, `pytest` and `python -m cta.validate` before its commit. When a step is finished,
its line above is marked DONE with the commit hash, and "Where we are" at the top is updated.

Step 1 (done 2026-10-12): `config/models.yaml`, `cta.settings.load_models` / `secret_status` / `cost_usd`,
`.env.example` keys, `cta.redact`, tests (`tests/test_settings_models.py`). Commit: 132ffb7.

Step 2 (done 2026-10-12): image `pgvector/pgvector:0.8.7-pg17`, `db/migrations/001_init.sql`, `cta.index.db` (`migrate`,
`status`), `tests/test_db.py` (2 integration tests, skipped when Postgres is down). Commit: fb7b842. The plan's
`schema_version` table is named `schema_migrations` (owner request). Dependencies added: `psycopg[binary]`, `pgvector`.

Step 3 (done 2026-10-12): `cta.index.chunks` (`--stats`, `--write`), `tests/test_chunks.py`, fixtures under
`tests/fixtures/processed/`. 619 chunks as planned (413 section, 197 course, 9 contact), 136,297 tokens, max 2,138,
$0.0027 to embed; all gold sources resolve. Dependency added: `tiktoken`. Commit: aaab39e.

Step 4 (done 2026-10-12): `cta.index.embed` (batches of 64, 3 retries on 429/5xx/connection errors, dimension check,
real token usage), `cta.index.load` (`--dry-run`, `--yes`, cost cap, validation gate, one transaction),
`tests/test_embed_load.py` (fake client, throwaway schema). Dependency added: `openai` (brings `httpx2`, which
openai requires itself since 3.0.0). First real load: 619 new, 136,297 tokens, $0.00273, 0 NULL embeddings,
self-check OK; second run: 619 unchanged, 0 embedded. Commit: a878e8c.

Step 5 (done 2026-10-12): `cta.index.load_calendar` (`--dry-run`, `--yes`; reads the file only through
`load_events_for_indexing`), integrity checks, `tests/test_load_calendar.py`; the throwaway-schema fixture moved to
`tests/conftest.py`. 136 rows (Fall 2026 55, Winter 2027 26, Spring 2027 55), 0 integrity problems, 1 TBA row
(spring-2027-055, "87th Commencement Ceremony", date NULL, `date_raw` "TBA"). Second run: 136 unchanged.
Commit: b1be84f.

Step 6 (done 2026-10-12): `cta.index.search` (`search()`, cache, command), `tests/test_search.py`. Sanity check on 4
dev questions (q04, q12, q21, q27) and 2 made-up ones: see `docs/decisions.md`. Commit: 0066e19.

Step 7 (done 2026-10-12): `cta.eval.metrics` (pure), `cta.eval.run_retrieval`, `tests/test_metrics.py`. Dev baseline
retrieval: 20 dev questions, 17 scored (q12 calendar-only, q27 and q28 no gold source excluded). Hit rate 0.706 @1,
0.941 @3/@5/@10; recall 0.549 @1, 0.838 @3/@5/@10; MRR 0.814. One miss in the top 10 (q15). Commit: 674648d.

## Roadmap after the baseline (no code; Phase 3 and later)

Each experiment changes one thing and is compared with `eval/results/baseline.json` (dev only; test is not used
for tuning).

1. Hybrid search: fill `tsv` (Postgres full-text) and fuse with the vector ranking by reciprocal rank fusion.
2. Term and department filters (soft term rule from `docs/decisions.md`; department filter only when the
   question names one).
3. A reranker over the top 20 to 30.
4. A router with tools: calendar lookup, prerequisite chain, contacts, program credits. This clears most of the
   `not supported yet` failures.
5. Guardrails: input scope check, personal-data handling, indirect prompt injection (retrieved text is data),
   and an output citation check (every cited source must be one of the retrieved chunks).
6. LangSmith tracing alongside our own `request_logs` (not instead of them).
7. Caching: an embedding cache and an exact response cache keyed by question + date + data version. No semantic
   cache (a near-match could return a wrong-term answer).
8. HNSW index decision, only when row count or latency justifies it (619 rows today: exact scan is fine).

## Decisions I need from you

- OK with `text-embedding-3-small` and `gpt-4o-mini` (judge the same, set separately)?
- Contact chunks as described (one per owner, doc_type `contacts`)?
- Retrieval metrics scored on section and course gold sources only, calendar-gold questions left to the Phase 3
  calendar tool?
- Answers at k = 5, retrieval metrics at k in {1, 3, 5, 10}?
