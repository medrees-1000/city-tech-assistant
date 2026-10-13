-- Phase 4: thumbs up or down on an API answer. Safe to run again (IF NOT EXISTS).
-- A vote is only 'up' or 'down'; no text and no identifier is stored with it. The vote lives in
-- the request's own row, so the purge command removes it together with the row.
ALTER TABLE request_logs ADD COLUMN IF NOT EXISTS feedback text CHECK (feedback IN ('up', 'down'));
ALTER TABLE request_logs ADD COLUMN IF NOT EXISTS feedback_at timestamptz;
CREATE INDEX IF NOT EXISTS request_logs_feedback_idx ON request_logs (feedback)
    WHERE feedback IS NOT NULL;
