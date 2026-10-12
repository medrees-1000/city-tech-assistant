-- Phase 2 schema. Applied once by `python -m cta.index.db migrate`.
-- No vector index: with a few hundred rows an exact cosine scan is fast and exact (see docs/phase2-plan.md).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE chunks (
    id                text PRIMARY KEY,      -- section id, "catalog:<CODE>", "contact:<owner>"
    kind              text NOT NULL,         -- section | course | contact
    source            text NOT NULL,         -- source_url or source_file
    source_id         text NOT NULL,
    doc_type          text NOT NULL,
    department        text,
    scope             text NOT NULL,
    term              text,
    terms             text[] NOT NULL DEFAULT '{}',
    fetched_at        text NOT NULL,
    last_updated      text,
    heading_path      text,
    heading_url       text,
    merged_section_ids text[] NOT NULL DEFAULT '{}',
    text              text NOT NULL,         -- exactly what is embedded
    content_hash      text NOT NULL,         -- sha256(text + embedding_model + dimensions)
    meta_hash         text NOT NULL,         -- sha256(metadata json)
    embedding         vector(1536),
    embedding_model   text,
    tsv               tsvector,              -- NULL in Phase 2 (Phase 3: hybrid search)
    updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE calendar_events (
    id                text PRIMARY KEY,
    term              text NOT NULL,
    event             text NOT NULL,
    date_start        date,
    date_end          date,
    date_raw          text,
    weekday_raw       text,
    applies_to        text,
    source_pdf        text NOT NULL,
    source_page       int,
    pdf_last_updated  date,
    verified          boolean NOT NULL,
    verified_by       text,
    verified_on       date,
    notes             text
);

CREATE TABLE eval_runs (
    id          serial PRIMARY KEY,
    run_at      timestamptz NOT NULL DEFAULT now(),
    label       text,
    git_commit  text,
    split       text,
    config      jsonb,
    metrics     jsonb,
    per_question jsonb,
    cost        jsonb
);

CREATE TABLE request_logs (
    id               bigserial PRIMARY KEY,
    ts               timestamptz NOT NULL DEFAULT now(),
    run_id           int REFERENCES eval_runs (id),
    question         text NOT NULL,          -- always passed through cta.redact.redact first
    today            date,
    retrieved        jsonb,                  -- chunk ids and scores
    answer           text,
    abstained        boolean,
    abstain_reason   text,
    chat_model       text,
    prompt_tokens    int,
    completion_tokens int,
    embedding_tokens int,
    cost_usd         numeric,
    latency_ms       int
);
