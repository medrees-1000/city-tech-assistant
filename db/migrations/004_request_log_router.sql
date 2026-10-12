-- Step 4a: which route answered a request (calendar, other, abstain, calendar_fallthrough) and the
-- router's own numbers (classifier and selector tokens, cost, latency, invalid ids, weekday mismatches).
ALTER TABLE request_logs ADD COLUMN route text;
ALTER TABLE request_logs ADD COLUMN router jsonb;
