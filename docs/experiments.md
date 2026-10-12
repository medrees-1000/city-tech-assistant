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

### Step 1b, hybrid search with a BM25 keyword side (written 2026-10-12, before any BM25 code or result)

**Why a second try.** Experiment 1 was rejected because Postgres `ts_rank` has no inverse document frequency and no length normalisation, so common
words and long chunks dominated the keyword list. BM25 weighs rare terms by idf and normalises by chunk length. This is a different keyword scorer, the
same fusion. The first try (`retrieval.mode: hybrid`, `ts_rank`) stays in the repository, off, so its result can be reproduced and a third variant can reuse
the pieces; it is not deleted because the rejection is a finding, not a mistake.

**Constants, fixed now and not tuned afterwards:** BM25 `k1 = 1.2`, `b = 0.75`; `idf = ln(1 + (N - df + 0.5) / (df + 0.5))`; candidate lists of 20 each
(vector top 20 plus BM25 top 20); reciprocal rank fusion `k = 60`; ties by id; query lexemes = the lexemes of `to_tsvector('english', question)`.
If the numbers look wrong, the next step is a new, separately pre-registered experiment, not an edit of these.

**Keep rule (the same as step 1).** On the 30 retrieval-scored dev questions, compared with `baseline-dev-60` (reproduced by `vector-v0-dev`):
keep if MRR **or** recall@5 improves by at least 0.01 **and** neither drops by more than 0.02. Name every question whose first relevant rank got
better or worse. The chain-tagged row (n = 3) is reported separately and is not part of the rule. A kept result is not run through the paid
answer-level run in step 1b; that is done together with step 2. The default switch to `hybrid_bm25` would be a separate commit, only if the rule says keep.

**Same caveat as before:** with 30 scored questions one question moves a mean by about 0.03; the rule guards against regressions and does not test significance.

## Experiment 1b: hybrid search with a BM25 keyword side, 2026-10-12 — REJECTED (narrowly, by the rule as written)

**Change.** `retrieval.mode: hybrid_bm25` (config switch; default stays `vector`). Vector top 20 plus BM25 top 20, reciprocal rank fusion (k = 60), ties by
id. BM25 is computed in Python (`cta.index.bm25`, standard library): Postgres only supplies the lexemes and the per-chunk term counts from `chunks.tsv`;
`k1 = 1.2`, `b = 0.75`, `idf = ln(1 + (N - df + 0.5) / (df + 0.5))`, built once per process (N = 619 chunks, average length 94.6, 5,152 lexemes). Constants
and the keep rule were written and committed before any BM25 code (`e74a3ab`) and were not touched afterwards. An empty query falls back to vector only; results gain
`bm25_rank`; the abstain threshold stays on the best vector cosine similarity. The tsvector's 256-positions-per-lexeme cap does not matter here: the most frequent
lexeme in any chunk occurs 85 times, the largest chunk is 6,868 characters and the longest document has 804 indexed positions. No paid call was made.

**Measurement.** `run_retrieval --split dev --label hybrid-bm25-dev --mode hybrid_bm25` (40 dev questions searched, 30 scored, query vectors cached, cost $0),
compared with `vector-v0-dev` (= `baseline-dev-60`) and, for reference, with `hybrid-v1-dev` (experiment 1).

| Metric (n = 30) | vector | hybrid (ts_rank) | hybrid_bm25 | bm25 vs vector |
|---|---|---|---|---|
| MRR | 0.789 | 0.710 | 0.766 | **-0.023** |
| recall@5 | 0.775 | 0.743 | 0.803 | **+0.028** |
| recall@10 | 0.828 | 0.805 | 0.888 | +0.060 |
| hit rate @1 / @3 / @5 / @10 | 0.700 / 0.867 / 0.900 / 0.933 | 0.600 / 0.800 / 0.833 / 0.900 | 0.633 / 0.900 / 0.900 / 0.967 | -0.067 / +0.033 / 0 / +0.033 |
| recall@1 / @3 | 0.488 / 0.735 | 0.421 / 0.649 | 0.471 / 0.749 | -0.017 / +0.014 |
| chain row (n = 3): recall@5 / recall@10 / MRR | 0.500 / 0.533 / 0.833 | 0.600 / 0.633 / 0.833 | 0.533 / 0.633 / 0.833 | +0.033 / +0.100 / 0 |
| search time, median / p95 | 15.8 / 18.0 ms | 17.6 / 20.8 ms | 15.8 / 16.9 ms | none |

By type, MRR before to after: lookup 0.691 to 0.760 (n = 14), multi_chunk 0.938 to 0.875 (n = 8), ambiguous 0.750 to 0.417 (n = 2), unanswerable 1.000 to 0.750 (n = 2),
time_sensitive 0.750 unchanged (n = 4).

**Questions that changed (first relevant rank, miss = not in the top 10).** Better (4): q21 2 to 1, q52 miss to 1, q53 5 to 2, q56 7 to 6.
Worse (6): q01 1 to 2, q06 2 to 7, q24 1 to 2, q47 1 to 2, q49 2 to 3, q59 1 to 2. Unchanged: 20, including q15 (miss to miss). Against experiment 1 (ts_rank), BM25
improved 8 questions and worsened 2 (q47, q49).

**The five questions asked about.**
- q21 (EET 3672): vector 2, BM25 1. The code lexeme `3672` is rare (in 9 chunks, idf 4.18) and decides it.
- q52 (expire): vector 15, **BM25 1**. `expir` occurs in exactly one chunk (idf 6.02), the gold FAQ; the other query lexemes are common (`program` idf 0.53, `prerequisit` 0.96).
  After fusion it is rank 1 (was a miss). This is the clean case BM25 was meant for.
- q15 (student hours): vector 103, **BM25 207** (score 2.43). Query lexemes `depart` (df 284, idf 0.78), `student` (327, 0.64), `technolog`, `electr`, `engin`, `hour`. The gold page is a short
  table; the EET program chunks repeat "electrical engineering technology" many times and score 13. BM25 cannot know that "Electrical Engineering Technology department" names the
  department and not the topic; unchanged miss.
- q56 (EET internships): vector 7, BM25 5; fused 6 (better by one rank). Generic EET pages (chair 19.5, overview 17.6) outscore the list page (15.8) on the many department words.
- q01 (apply for graduation): vector 1 (`#2`), BM25 13 (`#2`) and 35 (`#1`); fused rank 2 (worse by one). The words `citi` and `tech` (City Tech) are in 92 and 214 chunks, and other pages
  (`readmission#4` 9.2) outscore the right page.

**Decision (rule as written): REJECT for retrieval.** recall@5 improved by 0.028 (more than 0.01) but MRR dropped by 0.023, which is more than the allowed 0.02. It is a narrow miss and I
am not rounding it: the constants and the rule were fixed beforehand. The paid answer-level run was not done and the default stays `vector`.

**What the result says.** BM25 helps in the lower ranks (recall@10 +0.060, hit rate @10 +0.033, one miss rescued) and costs a little at the top (hit rate @1 -0.067; six questions lose one
to five positions, four of them only one). Equal-weight fusion moves a correct vector rank 1 down when a BM25 list puts another chunk first. The pattern suggests a keyword-and-vector
candidate set (good at finding the right chunk somewhere in the top 10) feeding a **reranker** (step 3) that fixes the order, rather than the fusion deciding the order itself. Not tested.

**Caveats.** n = 30 (3 chain, 2 ambiguous, 2 unanswerable): one question moves the means by about 0.03, so MRR -0.023 is smaller than one question's worth of noise.
The explanation above was read off dev ranks. Rubric v3 (below) was written in the same step but not used here (no judge call).

**Open follow-ups (each needs its own pre-registered rule; none started):** a vector-weighted fusion; BM25 only as candidate generator for the reranker experiment; a department-name
filter (step 2) that would address q15 and q56, which BM25 cannot.

### Rubric v3 (code only, 2026-10-12)
`RUBRIC_VERSION = 3`: faithfulness is judged only against the numbered sources shown, never outside knowledge; "the sources do not contain X" is faithful if X is absent from
those sources, and a "no" if X is in them. Correctness and the special gold rules are unchanged. Stored in every run config. **The next answer-level run will also re-judge the stored
`baseline-dev-60` answers under v3** (`--rejudge baseline-dev-60`, judge calls only) so the comparison is like for like; the v2 numbers in `baseline-dev-60.json` stay as recorded.
Reason: see `docs/decisions.md` (the q22 and q40 findings).

### Step 2a, department filter on retrieval (written 2026-10-12, before any filter code, config or result)

**Change under test.** `retrieval.dept_filter: on` (config switch, default `off`). If the question names a department (by alias or by a course code), candidate
chunks whose `scope` is `department` and whose `department` is not among the detected ids are dropped. Chunks with scope `cuny` or `city_tech` always stay. If no
department is detected, nothing changes. It works with every retrieval mode; the measurement for the keep rule uses `mode: vector`.

**Keep rule (the same as steps 1 and 1b).** On the 30 retrieval-scored dev questions, compared with `baseline-dev-60` (reproduced by `vector-v0-dev`): keep if MRR **or**
recall@5 improves by at least 0.01 **and** neither drops by more than 0.02. Name every question whose first relevant rank got better or worse. The chain-tagged row (n = 3)
is reported separately and is not part of the rule. A kept result is not run through the paid answer-level run in step 2a. Switching the default to `on` would be a separate
commit, only if the rule says keep.

**No tuning constants.** The filter has none. The aliases and course prefixes in `config/departments.yaml` are written from the catalog data (distinct course-code prefix
per department id in the database) and the project notes (CLAUDE.md: the catalog calls EET "Electrical Engineering Technology"; handle both names) **before** the run, and are
**not edited after seeing results**. If a result shows a missing or wrong alias, that is a finding for the log and a new, separately pre-registered experiment, not an edit.

**Declared in advance:** "ETET" is included as an alias of EET because it is common student shorthand (the department pages themselves print "ETET Office Hours"). It also
appears in dev question q15's gold page, so a gain on q15 cannot be taken as independent evidence for it; the test split must confirm it later (not run in this step).
Short aliases ("Math", "CST") can match inside other uses of the word; every dev question where a department was detected is listed in the report so false matches can be read.

**Same caveat as before:** with 30 scored questions one question moves a mean by about 0.03; the rule guards against regressions and does not test significance. The filter can
only change the result for questions where a department is detected.

## Experiment 2a: department filter on retrieval, 2026-10-12 — REJECTED (no effect)

**Change.** `retrieval.dept_filter: on` (config switch, default `off`; `CTA_DEPT_FILTER` or `--dept-filter` override; works with every retrieval mode). `cta.index.departments`
detects the departments a question names, from the aliases and course-code prefixes in `config/departments.yaml` (written and committed before the run, `cd78f89`, not edited
afterwards; prefixes read from the 197 course chunks: CST, MST, DPT -> CST-NYT; MAT, MEDU -> MATH-NYT; EET, TCET -> EET-NYT; DEN -> DENT-NYT; no prefix belongs to more than one
department; cross-listed CET and MECH are not mapped). With at least one department detected, candidate chunks whose `scope` is `department` and whose `department` is not detected
are dropped before any ranking is cut; scopes `cuny` and `city_tech` always stay; with none detected nothing changes. The abstain threshold stays on the best vector cosine
similarity, computed after the filter (it can only be equal or lower, and differs only when the single best chunk in the index belongs to a department the question does not name).
Results gain `dept_filter_applied` and `detected_departments`. Rule and "no tuning constants" statement: pre-registered in `3e0448a`.

**How the fields are stored (checked in the database before writing the rule).**

| Chunk type | scope | department | Effect of the rule |
|---|---|---|---|
| department web pages, program pages, department FAQs (413 section chunks of the four) | department | the department id | filtered |
| per-department contact chunks (4) | department | the department id | filtered |
| **course chunks (197)** | **city_tech** | **the department id** | **never filtered: scope is city_tech.** This is the one chunk type that does not fit the intent |
| office contacts, central pages (aid, policy, howto, calendar, advisement staff list) | city_tech | none | always stay |
| CUNY-wide documents | cuny | none | always stay |

**Measurement.** `run_retrieval --split dev --mode vector --dept-filter on --label dept-filter-dev`; 40 dev questions searched, 30 scored; cost $0 (cached vectors). Compared with `vector-v0-dev`
(= `baseline-dev-60`).

| Metric (n = 30) | vector | + department filter | change |
|---|---|---|---|
| MRR | 0.789 | 0.789 | 0.000 |
| recall@5 | 0.775 | 0.775 | 0.000 |
| recall@10 | 0.828 | 0.837 | +0.008 |
| hit rate @1 / @3 / @5 / @10 | 0.700 / 0.867 / 0.900 / 0.933 | identical | 0 |
| chain row (n = 3) | all metrics identical | | 0 |

**No first relevant rank changed (improved 0, worsened 0, unchanged 30).** Only two questions' top-10 lists changed at all: q06 (the Mathematics degrees page left the list, the CST degrees page
entered; gold rank stayed 2) and q42 (three CST program chunks left, three MAT course chunks entered; gold rank stayed 1). The small recall@10 difference comes from one of them.

**Detection report (dev questions only).** A department was detected in 17 of the 40 dev questions and in 14 of the 30 retrieval-scored ones. In all 14 scored questions the detected department is
also the department of the gold sources (q39 names CST 3602; its gold includes MAT courses of the chain, still a match; the three other detected questions, q27, q28 and q45, are abstain
questions with no gold). **No detected department differs from the gold department and no false match was seen** (checked by reading all 17 questions: "Dental Hygiene", "Computer Systems
Technology", "math", "MAT 1190CO", "EET 3672", "MAT 2675" and so on). q15 and q56 are both detected as EET-NYT and both unchanged (q15 stays a miss, q56 stays rank 7).

**Why it did nothing.** For the questions that name a department, pages of *other* departments almost never reach the top 10 in the first place. What outranks the gold chunk is inside the
named department (q15: EET program chunks; q56: EET overview and chair pages) or is a course chunk, which the rule cannot drop by scope. Cross-department leakage is not the problem in this data;
the problem is ranking inside the right department.

**Reference only (not part of the keep rule, not pre-registered): the same filter with `hybrid_bm25`** (`dept-filter-bm25-dev`).
- Against `vector-v0-dev`: MRR 0.789 to 0.771 (-0.018), recall@5 0.775 to 0.803 (+0.028), recall@10 0.828 to 0.895 (+0.067), hit rate @1 0.700 to 0.633; chain row recall@10 0.533 to 0.700 (n = 3).
  Better: q05 3 to 2, q21 2 to 1, q52 miss to 1, q53 5 to 2, q56 7 to 6. Worse: q01, q06, q24, q47, q49, q59 (one to five places).
- Against `hybrid-bm25-dev` (the filter's own effect on BM25): MRR +0.006, recall@5 0.000, recall@10 +0.007; one question changed (q05 3 to 2).
- The rule applied to this combination would say keep (MRR -0.018 is inside the limit), but the combination was **not pre-registered**, the only thing separating it from the rejected step 1b is one question
  (q05), and I am not treating it as a decision. What it shows for the reranker step: with BM25 and the filter the top-10 candidate set contains more gold sources (recall@10 0.895 against 0.828 for vector
  search, chain row 0.700 against 0.533) while the top-1 position is slightly worse. That is the shape a reranker is for; it is a hypothesis for step 3, not a result.

**Decision (pre-registered rule): REJECT.** MRR and recall@5 did not improve by 0.01. The default stays `off`. Code, config and tests stay in the repository, off.

**Caveats.** n = 30 (14 with a detected department). "ETET" was declared in advance as an alias and also appears in q15's gold page, so q15 cannot confirm it; q15 did not change anyway. The test split has not
been touched and would have to confirm any alias before the filter is used. The explanation above was read off dev ranks.

**Open follow-ups (each would need its own pre-registered rule; none started):** also filter course chunks by their `department` field even though their scope is `city_tech`; use the detected department as a
boost instead of a filter; use it as a feature of the step 3 reranker.

### Step 3, LLM reranker (written 2026-10-12, before any reranker code, prompt or result)

**Step 0 count (no code beyond a query, dev split, from the question text).** 13 of the 40 dev questions name a term or a relative term ("Fall 2026", "Winter 2027", "Spring 2027", "Summer 2027",
"this fall", "this semester", "next spring"): q09, q12, q13, q14, q27, q28, q31, q33, q34, q36, q37, q44, q45. Only 3 are retrieval-scored (q09, q13, q14) and all 3 already rank their gold source at **1**.
The other 10 are calendar-only, abstain or CLARIFY questions (no scorable gold section). So on dev a term filter has nothing to fix: no term-naming scored question ranks below 1. Step 2b is **not worth building
now**; the 3 questions cannot show a gain, and a regression could not be told from noise. Not built.

**Change under test.** `retrieval.rerank: off | pool_a | pool_b` (config switch, default `off`, quoted). The first stage fetches a candidate pool; one chat call per question scores each candidate 0 to 10; the
candidates are sorted by score and the top k go to the answerer. Variants, fixed now:
- **Pool A:** `mode: vector`, no department filter, top **20**.
- **Pool B:** `mode: hybrid_bm25`, `dept_filter: on`, top **30**.
- Rerank model = `chat_model` from `config/models.yaml` (`gpt-6-luna`), temperature 0, `reasoning_effort: none`, JSON output (`response_format` json_object).
- The text sent for each candidate is cut to its **first 400 tokens** (tiktoken, same encoding as the chunker), with its source and heading. 400 is fixed and untuned.
- Scores: a JSON object, candidate number -> number from 0 to 10. Sorted by score descending; equal scores keep the first-stage order. If the reply is not valid JSON, or any candidate has a missing or invalid
  score (not a number from 0 to 10), or the call fails, the **whole question keeps the first-stage order**; such calls are counted as failed and reported, never hidden.
- The abstain threshold stays on the top vector cosine similarity of the first-stage retrieval (not on rerank scores, which are not similarities). No change to the answer prompt, threshold, models, chunks, embeddings.

**Prompt.** Written once, in `src/cta/index/rerank.py`, and committed before the first paid call. It is **not edited after seeing results**. A second prompt would be a new experiment with its own entry.

**Keep rule (per variant).** On the 30 retrieval-scored dev questions, compared with `baseline-dev-60` (reproduced by `vector-v0-dev`): keep if MRR **or** recall@5 improves by at least 0.01 **and** neither drops
by more than 0.02. Name every question whose first relevant rank got better or worse. The chain-tagged row (n = 3) is reported separately and is not part of the rule. **If both variants satisfy the rule, keep the
one with the higher MRR** and say so. Both variants are reported whatever happens. Default switch only in a separate commit, only if a variant is kept; no paid answer-level run in this step.

**Also reported, not part of the rule:** the pool's own recall (share of gold sources inside the pool = the upper bound for the reranker), failed or fallback calls, total cost, median and p95 rerank latency, and
q15, q52, q56, q01, q06, q21 one by one.

**Spend limit for the whole step: $0.25.** A call whose token-counted cost estimate would push a run over its allowance is refused before it is made.

**Caveats written in advance.** n = 30 (one question moves a mean by about 0.03); the rule guards against regressions, not significance. The reranker cannot help a question whose gold is outside the pool (q01 and
q15 were misses at 10; the pool is larger, so they may now be inside). The same model reranks and answers, which is a choice made for cost and simplicity, not a claim it is the best reranker.

## Experiment 3: LLM reranker, 2026-10-12 — Pool A KEPT, Pool B also meets the rule but has the lower MRR

**Change.** `retrieval.rerank: off | pool_a | pool_b` (default `off` at this commit; `CTA_RERANK` or `--rerank` override). Code, prompt and tests: `774890e` (committed before the first paid call; the prompt in
`src/cta/index/rerank.py` is unedited since). One chat call per question to `gpt-6-luna` (temperature 0, reasoning none, JSON), each candidate cut to its first 400 tokens, scores 0 to 10, sorted by score with ties and any
unusable reply falling back to the first-stage order. Rule and variants pre-registered in `8c379c4`. Measurement: `run_retrieval --split dev --rerank pool_a|pool_b`, labels `rerank-a-dev` and `rerank-b-dev`; compared with
`vector-v0-dev` (= `baseline-dev-60`). Test split not touched. (`compare` prints "mode vector" for both because the saved `retrieval_mode` field is the base mode; the pool is in each file's `config.retrieval.rerank`.)

| Metric (n = 30) | baseline (vector) | Pool A: vector top 20 | Pool B: BM25 + dept filter top 30 |
|---|---|---|---|
| MRR | 0.789 | **0.925** (+0.136) | 0.904 (+0.114) |
| recall@5 | 0.775 | **0.897** (+0.122) | 0.883 (+0.108) |
| recall@1 / @3 | 0.488 / 0.735 | 0.671 / 0.880 | 0.638 / 0.860 |
| recall@10 | 0.828 | 0.905 | 0.903 |
| hit rate @1 / @3 / @5 / @10 | 0.700 / 0.867 / 0.900 / 0.933 | 0.900 / 0.933 / 0.967 / 0.967 | 0.867 / 0.933 / 0.933 / 0.967 |
| chain row (n = 3) MRR / recall@5 / recall@10 | 0.833 / 0.500 / 0.533 | 1.000 / 0.633 / 0.633 | 1.000 / 0.667 / 0.700 |
| pool recall (upper bound), all / chain row | | 0.912 / 0.700 | 0.912 / 0.700 |
| rerank calls, failed or fallback | | 40, **0 failed** | 40, **0 failed** |
| rerank cost (40 questions, dev) | | $0.0206 (187,863 in / 3,636 out tokens) | $0.0295 (269,326 in / 5,179 out) |
| rerank API latency median / p95 | | 1,635 / 2,305 ms | 1,862 / 2,333 ms |

By type, MRR before to after (Pool A / Pool B): lookup (14) 0.691 to 0.911 / 0.901; multi_chunk (8) 0.938 to 1.000 / 1.000; ambiguous (2) 0.750 to 1.000 / 0.750; time_sensitive (4) 0.750 to 0.750 / 0.750; unanswerable (2) 1.000 to 1.000.

**Questions (first relevant rank, baseline to reranked).**
- Pool A: improved 7 — q05 3 to 1, q21 2 to 1, q22 2 to 1, q49 2 to 1, q52 miss to 1, q53 5 to 2, q56 7 to 1. Worsened 1 — **q06 2 to 4**. Unchanged 22.
- Pool B: the same 7 improved; worsened 2 — **q06 2 to 9**, **q24 1 to 2**. Unchanged 21.
- The ones asked for: q15 stays a miss in both (pool recall 0 for q15: the gold `student-hours` section is in neither pool, so no reranker can reach it); q52 miss to 1 (its gold was at position 15 of Pool A, outside the old top 10);
  q56 7 to 1 (position 7 of the pool); q01 stays 1 (but pool recall for q01 is 0.5: its second gold section, `applying-graduation#1`, is in neither pool); q06 gets worse (see below); q21 2 to 1.

**Why q06 got worse.** Its first gold (the CST degrees page, section 2) was at pool position 2 for Pool A (12 and 16 for the other sections); the model scored the CST overview, the department home page and the student-resources page above it
(ranks 1 to 3 after reranking). I read the ranks only; I have not re-read the reranker's scores, and I did not touch the prompt. The overview pages are about the same topic, which is exactly what rule 1 of the prompt tells the model not to
reward, so this is a model judgement call, not a malfunction: no failed calls.

**Decision (pre-registered rule).** Both variants satisfy it (MRR and recall@5 each improved by far more than 0.01; neither dropped). **Both satisfy the rule, so the one with the higher MRR is kept: Pool A (0.925 against 0.904).**
Pool B is also reported as a pass. Pool A is also the simpler one (the baseline's own vector search, no BM25, no department filter) and cheaper ($0.0206 against $0.0295 for 40 questions).

**Cost and latency.** Pool A adds about $0.0005 per question (one call of about 4,700 input tokens) and a median of 1.6 s per question (retrieval alone was about 16 ms). The cost of the answer is unchanged. That is the price of this
gain and is not free: the answer-level run, not run here, is what shows whether better ranks give better answers.

**What this does not show.** n = 30, three of them chain questions; the rule guards against regressions and does not test significance. Several of the gains (q56 7 to 1, q52 miss to 1) come from gold that was already in the pool; the pool recall of 0.912
is an upper bound. The same model reranks and answers. Dev questions were used to choose between two pre-registered variants; the prompt was not tuned on dev. The test split is untouched and has to confirm this. The abstain threshold still reads the first
stage's best cosine similarity: with Pool A (vector, no filter) that is identical to the baseline's, so abstention decisions are unchanged.

**Open follow-ups (each would be its own experiment):** a second prompt; a bigger pool or a different cut for the chunk text; showing the reranker the neighbouring sections (q01, q06); the answer-level run (first re-judge `baseline-dev-60` under rubric v3).

### Step 3b, answer-level check of the reranker (written 2026-10-12, before any paid call of this step)

**Question.** Does the reranker (`retrieval.rerank: pool_a`, kept in experiment 3 on retrieval metrics only) hold up at the answer level, with the noise of the answerer and the judge measured? If not, the default goes back to `off`.

**Design, fixed now.**
- **Arm OFF** = `retrieval.rerank: off` (the old vector-only system). **Arm ON** = `retrieval.rerank: pool_a`. All 40 dev questions; answers generated with the unchanged settings (`gpt-6-luna`, temperature 0.1, top_p 0.3, k = 5,
  abstain threshold 0.59, `eval.today` 2026-10-11); every verdict judged by `gpt-5.6-terra` under **rubric v3**. Test split not touched. Answer prompt, threshold, models, chunks, embeddings, reranker prompt and settings unchanged.
- **3 runs per arm.** OFF run 1 is the stored `baseline-dev-60` answers re-judged under v3 (no regeneration; saved as `eval/results/baseline-dev-60-v3.json`, the v2 file untouched; this is "off-run1"), plus two fresh
  runs `off-run2`, `off-run3`. ON: three fresh runs `on-run1`, `on-run2`, `on-run3`. Each ON run makes its own fresh reranker calls (its own cache file `data/cache/rerank-<label>.json`), so reranker noise is part of the ON noise and the
  reranker's real cost and latency are measured in every ON run.
- **Judge noise.** `judge-repeat` = `on-run1`'s stored answers judged a second time (same answers, same rubric, same judge); the number of verdicts that differ is reported.
- **The answerer receives the reranked top 5 in arm ON**; the sources it received are shown for three example questions (q06, q56, q52, chosen as the worsened, a large-gain and a rescued-from-outside-top-10 case).

**Rule, on the mean of the 3 runs per arm** (shares as defined by `aggregate` in `cta.eval.run_answers`): keep `pool_a` as the default only if **all** of
- (a) **correct share** (normal-gold questions, n = 26) does not fall by more than one question's worth: ON mean >= OFF mean - 1/26;
- (b) **faithfulness "yes" share** (same questions) does not fall: ON mean >= OFF mean;
- (c) **abstention accuracy** (ABSTAIN-gold questions answered with "ABSTAIN:") does not fall (ON mean >= OFF mean) **and** the wrongly-abstained count (answerable questions that abstained, mean count per run) does not rise (ON <= OFF);
- (d) **citation validity** does not fall: the citation rate (answers with at least one valid [n]) ON >= OFF **and** the mean number of invalid citations per run ON <= OFF.
Otherwise the default goes back to `off` in its own commit. The comparisons are exact (no rounding); the rule is strict on purpose, so a tiny fall in (b), (c) or (d) means revert even if the retrieval gain is real; the log will say what was
lost. The rule does not weigh latency or cost (reported only: the reranker adds a call per question).

**Noise.** For each question and for each of correctness and faithfulness (ordinal: incorrect < partial < correct; no < partly < yes), the verdicts of its 3 runs are listed per arm. A question is **stable in an arm** if its verdict is the
same in all 3 runs of that arm. A **real change** is a question that is stable in both arms and has different verdicts between the arms (so it differs in the same direction in 3 of 3 pairings, which satisfies "at least 2 of 3"). A question
where ON and OFF differ in the same direction in at least 2 of the 3 pairings (run i against run i) but which is not stable in both arms is a **leaning** question; leaning, and every other question with any variation inside an arm, is
listed as **unstable** and is not counted as a change.

**Spend limit for the whole step: $2.50** (including the v3 re-judge, the five fresh runs, the judge repeat and the reranker calls). The per-run cap in `config/models.yaml` (`eval.max_cost_usd: 1.0`) is unchanged. Each run stops itself
before it would exceed the remaining allowance and says so (`--budget`).

**Caveats written in advance.** n is small (26 judged questions, 4 abstain, 2 no-advice, 8 not supported yet), so one question is about 4 points of a share; the same model reranks and answers; judge verdicts are not perfect (the
faithfulness grade is known to be lenient, and the judge repeat measures only its self-consistency, not its correctness); three runs per arm bound the noise roughly and do not remove it.
