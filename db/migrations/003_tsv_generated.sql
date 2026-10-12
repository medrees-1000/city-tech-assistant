-- Phase 3, step 1 (hybrid search): chunks.tsv becomes a generated column over the embedded text, with
-- the 'english' text search configuration, plus a GIN index. The loader never writes tsv; Postgres
-- keeps it in step with `text`, so a changed chunk updates its keyword index automatically.
--
-- What 'english' does: lowercases, drops stop words (what, are, the, for, ...), stems ordinary words
-- (prerequisites -> prerequisit). Course codes survive: "EET 3672" -> 'eet' '3672', "MAT 1275CO" ->
-- 'mat' '1275co' (letters and digits are kept whole, not stemmed). A code written without a space
-- ("EET3212") is one lexeme and does not match "EET 3212"; "66-67" splits into '66' and '-67'.
ALTER TABLE chunks DROP COLUMN tsv;
ALTER TABLE chunks ADD COLUMN tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED;
CREATE INDEX chunks_tsv_idx ON chunks USING GIN (tsv);
