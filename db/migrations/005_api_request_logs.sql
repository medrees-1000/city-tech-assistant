-- Phase 4 step 5: the API writes to request_logs too. Every statement is safe to run again
-- (IF NOT EXISTS), like the migration tracker, which also records that this file ran.
-- Existing rows become source = 'eval' through the column default; the eval code keeps inserting
-- without naming the new columns and so keeps getting 'eval'.
ALTER TABLE request_logs ADD COLUMN IF NOT EXISTS request_id uuid;
ALTER TABLE request_logs ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'eval'
    CHECK (source IN ('api', 'eval'));
ALTER TABLE request_logs ADD COLUMN IF NOT EXISTS status text;          -- 'ok' or an error code
ALTER TABLE request_logs ADD COLUMN IF NOT EXISTS trace jsonb;          -- the how_found block (ids, scores, ms, tokens, cost)
ALTER TABLE request_logs ADD COLUMN IF NOT EXISTS contact_office text;  -- the office key of the contact card, if any
-- The table's timestamp column is `ts` (created in 001); it is the one the purge and the logs command filter on.
CREATE INDEX IF NOT EXISTS request_logs_ts_idx ON request_logs (ts);
CREATE UNIQUE INDEX IF NOT EXISTS request_logs_request_id_idx ON request_logs (request_id)
    WHERE request_id IS NOT NULL;
