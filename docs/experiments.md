# Experiments (Phase 3)

One entry per experiment, newest last. Protocol: `docs/phase3-plan.md`. Comparison file for dev:
`eval/results/baseline-dev-60.json` (the frozen system on the 40 dev questions; 30 of them are retrieval-scored). Each entry has
the change, the config switch, the metric deltas, cost and latency deltas, the questions that got better or worse, the decision, and
the caveats. A rejected experiment is still logged. The test split is never used to decide.

## Decision rules (written before the run they apply to)

### Step 1, hybrid search (written 2026-10-12, before any hybrid result was computed)

**Retrieval stage** (`run_retrieval --split dev`, 30 retrieval-scored dev questions, vector-only is `baseline-dev-60`):
- **Keep hybrid** if MRR **or** recall@5 improves by at least 0.01 **and** neither of the two drops by more than 0.02.
- Every question whose first relevant rank got better or worse is named (rank before to rank after; "miss" means not in the top 10).
- The chain-tagged row (n = 3) is reported separately and is not part of the rule: it is too small to decide anything.
- Other metrics (recall and hit rate at 1, 3, 10; by type) are reported, not part of the rule.

**Answer stage** (only if retrieval is kept; full answer and judge run on dev, label `hybrid-v1-dev-answers`):
- The change is kept for answers if correctness (normal gold) does not drop by more than one question, faithfulness does not drop by
  more than one question, wrongly abstained does not rise by more than one question, and abstention accuracy does not fall.
- Latency is reported (chat call and retrieval time separately); it is not a keep or reject criterion unless retrieval time grows
  by more than 100 ms at the median.

**Default switch:** `retrieval.mode` becomes `hybrid` by default only if both stages are kept, in a separate commit.

Caveat written in advance: with 30 scored questions one question moves a mean by about 0.03, so a change of 0.01 to 0.02 is below
what the set can resolve. The rule is a guard against obvious regressions, not a significance test.

## Experiment 1: hybrid search (keyword plus vector), 2026-10-12 — REJECTED

**Change.** `retrieval.mode: hybrid` (config switch, default `vector`; override with `CTA_RETRIEVAL_MODE` or `--mode`). Vector top 20 plus
keyword top 20, merged by reciprocal rank fusion (k = 60, ties by id), then the top k. Keyword side: migration 003 made `chunks.tsv` a generated
column (`to_tsvector('english', text)`) with a GIN index; the query is an OR of the question's lexemes, ranked with `ts_rank`. Empty keyword
query (all stop words) falls back to vector only. Results keep every field and add `vector_rank` and `keyword_rank`; `similarity` stays the
cosine. The abstain threshold uses the best **vector** cosine similarity in both modes (`Search.top_vector_similarity`), never the fused score.
Nothing else changed: chunks, embeddings, prompt, threshold, models and rubric are as in the baseline. `python -m cta.index.load --dry-run`
still reports 0 changes after the migration.

**What `english` does to codes** (tested): "EET 3672" gives the lexemes `eet` and `3672`; "MAT 1275CO" gives `mat` and `1275co` (lowercased, whole,
not stemmed; `1275` and `1275co` are different lexemes); a code written without a space ("EET3212") is one lexeme and does not match "EET 3212";
"66-67" splits into `66` and `-67`. Stop words (what, are, the, for) are dropped and ordinary words are stemmed (prerequisites gives `prerequisit`).

**What `ts_rank` cannot do.** It scores by how often and where the query words occur in a chunk. It does not weigh rare words more than common
ones (no inverse document frequency), so "student" counts as much as "3672", and it does not normalise by chunk length, so long chunks with many
common words rank high.

**Measurement.** Retrieval only (`run_retrieval --split dev`, 40 dev questions searched, 30 scored; query vectors cached, cost $0). Vector run
`vector-v0-dev` reproduces `baseline-dev-60` exactly; hybrid run `hybrid-v1-dev`; comparison with `python -m cta.eval.compare`.

| Metric (n = 30) | vector | hybrid | change |
|---|---|---|---|
| MRR | 0.789 | 0.710 | -0.079 |
| recall@5 | 0.775 | 0.743 | -0.032 |
| recall@1 / @3 / @10 | 0.488 / 0.735 / 0.828 | 0.421 / 0.649 / 0.805 | -0.067 / -0.086 / -0.023 |
| hit rate @1 / @3 / @5 / @10 | 0.700 / 0.867 / 0.900 / 0.933 | 0.600 / 0.800 / 0.833 / 0.900 | -0.100 / -0.067 / -0.067 / -0.033 |
| chain row (n = 3): MRR / recall@5 / recall@10 | 0.833 / 0.500 / 0.533 | 0.833 / 0.600 / 0.633 | 0 / +0.100 / +0.100 |

By type: lookup MRR 0.691 to 0.570 (n = 14); multi_chunk 0.938 to 0.875 (n = 8); ambiguous 0.750 to 0.667 (n = 2); time_sensitive and
unanswerable unchanged. Search time per question: median 15.8 to 17.6 ms, p95 18.0 to 20.8 ms (+1.8 ms median).

**Questions that changed (first relevant rank, miss = not in the top 10).** Better (3): q21 2 to 1, q49 2 to 1, q53 5 to 2.
Worse (8): q01 1 to 6, q04 1 to 2, q05 3 to 5, q06 2 to 9, q24 1 to 3, q42 1 to 2, q56 7 to miss, q59 1 to 2. Unchanged: 19, including q15 (miss to miss) and
q52 (miss to miss).

| Question | vector rank of the gold | keyword rank of the gold | Reading |
|---|---|---|---|
| q21 (EET 3672) | 2 | 1 | the code lexeme `3672` works: the one clean win |
| q01 | 1 (`#2`), 48 (`#1`) | 43, 66 | lexemes `citi`, `tech`, `appli`, `graduat` match everywhere; the right page is outranked |
| q15 (student hours) | 103 | beyond 200 | the page matches `student` and `hour`, but ts_rank puts large generic chunks first |
| q52 | 15 | 128 | same |
| q56 | 7 | 30 | long generic pages (chair, welcome) win on common words |
| q06 | 12, 2, 188, 16 | 119, 75, none, none | "computer systems technology" matches every CST chunk |

**Decision (pre-registered rule, written before the run).** MRR -0.079 and recall@5 -0.032: no improvement of 0.01 and a drop of more than 0.02.
**REJECT for retrieval.** The answer-level run was not done (the rule runs it only if retrieval is kept) and the default stays `vector`.
The code, the generated column and the switch stay in the repository, off by default.

**Why it failed (for the next experiment, not tuned here).** The keyword list is dominated by words that appear in many chunks of this corpus
(city, tech, student, department, the department names) and by long chunks. Fusing it with a good vector list at equal weight pulls those
noisy chunks into the top 5. Only questions with a rare, exact token (a course code) gain.

**Caveats.** n = 30 retrieval-scored questions (3 chain): one question moves a mean by about 0.03, so small differences are not resolvable;
the direction (8 worse, 3 better, MRR down 0.08) is clear enough for the rule. The dev set was used to design nothing in this experiment (the
rule and the configuration were fixed first), but the explanation above was read off dev ranks.

**Possible follow-ups (each would be its own experiment with its own pre-registered rule, not started):** (a) keyword side restricted to rare
lexemes, for example only lexemes with a low document frequency or only codes, computed from the index; (b) a weighted fusion that favours the
vector list; (c) a document-frequency weighted keyword score (BM25 style) computed in Python over the 619 chunks.
