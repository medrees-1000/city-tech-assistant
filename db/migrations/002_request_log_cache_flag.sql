-- Whether the question embedding came from the local cache (a cache hit hides embedding latency).
ALTER TABLE request_logs ADD COLUMN query_cache_hit boolean;
