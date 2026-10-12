# Decisions

Short notes on choices that are not obvious from the code. Newest last.

## Term tags on sections (Oct 11, 2026)

- Every section has `terms`, a list that may be empty. An entry is an explicit term name: Summer I,
  Summer II, Summer, Fall, Winter or Spring followed by a 4-digit year ("Fall 2026"; "Summer Session I
  2026" is stored as "Summer I 2026"). `term` is the single entry when `terms` has exactly one, else null.
- Terms are read only from the section's heading path (its parents' headings and its own heading) and the
  header row of its tables (a table title such as "Summer 2026 Advisement Schedule"). Never from body text
  and never from dates: "Summer 2026 refunds begin July 17, 2026" in a paragraph tags nothing.
- A season with no year ("Fall Refund Date", "Year 1 Fall", "Fall and Spring") is not a term.
- **Refund calendar rule (the only exception).** The refund calendar PDF has the heading "Summer 2026, Fall
  2026, and Spring 2027 Refund Schedule", which names three terms. For that document only, a heading that
  starts with a season and no year takes the one term of that season named in that heading:
  - "Fall Book Advance Refund Dates" and "Fall Refund Date" -> Fall 2026
  - "Spring Book Advance Refund Dates" and "Spring Refund Date" -> Spring 2027
  - the main schedule table section (the heading itself) -> Summer 2026, Fall 2026, Spring 2027
  Such sections carry `terms_source` saying so. If the schedule heading named no term (or two) for a season,
  the section gets none. Nothing else is resolved this way.
- Refund pages (`refund_pages` in `config/sources.yaml`) also store `covered_terms`, every term their
  headings and tables name, and `seasons_without_year`, the season names they use without a year. The
  coverage is what the page prints; it is not assumed from the page's purpose.

## Phase 3 answer rule: terms on retrieved sections

If none of the terms tagged on a retrieved section matches the term the question is about (or the current
term when none is named), the answer states the term printed on the source (for example "this page lists
Fall 2024 hours") or abstains with the office contact. Term filtering is soft: a section with no terms is
never excluded.

## Database setup (Oct 12, 2026)

- Image `pgvector/pgvector:0.8.7-pg17`: Postgres 17 (current major with long support left) and the newest
  pgvector tag listed on Docker Hub on this date. The tag is pinned so a pull never changes the database
  version. Moving to a newer tag is a deliberate edit of `docker-compose.yml`.
- The container publishes `127.0.0.1:5432` only. A host Postgres was already using 5432; the owner stopped it.
- `schema_migrations` is created by `cta.index.db migrate`, not by a migration file (a migration could not
  record itself before its own table exists). Each migration runs in one transaction with its record, so a
  failed one leaves nothing half-applied. Migration files are applied in file-name order and never edited after
  they have run; a schema change is a new numbered file.
- The vector column is `vector(1536)`. Changing the embedding model to one with other dimensions needs a new
  migration and a full re-embed.
- Connection errors print a fixed message, because the driver message can contain connection details.

## Chunk builder (Oct 12, 2026)

- Counts match the plan: 619 chunks (413 section, 197 course, 9 contact), 121 sections merged into a parent.
  Exact tokens (cl100k_base, the encoding of text-embedding-3-small): 136,297 in total, max 2,138 per chunk,
  so nothing needs splitting and the one-time embedding cost is about $0.0027.
- A merged chunk takes the id of the parent section; the table sections are listed in `merged_section_ids`, so
  eval labels at section level still resolve. Section ids count all sections of the record, including
  `embed: false` ones, so they match `docs/section-index.md`.
- A merged chunk's `terms` is the union of the parent's and the merged tables' terms (a table titled "Fall 2026
  Payment Due Dates" under a general heading makes the chunk a Fall 2026 chunk); `term` is the single entry,
  else null. Terms still come only from headings and table titles.
- Course prerequisites: `text` rules are embedded as printed. A shorthand rule (40 courses, e.g.
  `PRE_CST1100`) is embedded as printed with the note "shorthand as printed in the catalog, not expanded":
  never guessed. A course with no rule says "none listed in the catalog".
- Contact chunks use every panel of the owner record (address, email, hours) and cite the first source page of
  that owner. Departments are named from the course records (`department_name`); offices as "<Name> office".
- `content_hash` = sha256(text + embedding model + dimensions); `meta_hash` = sha256 of the id and the
  metadata fields in sorted-key JSON. Tokens are counted with tiktoken; the encoding file is cached in
  `.cache/tiktoken` (git-ignored).

## Embedding loader (Oct 12, 2026)

- The loader needs `--yes` for any write, not only for embedding: without it, metadata-only updates and stale
  deletions are previewed too. A run with nothing to change prints the report and needs no flag.
- The OpenAI client is created with `max_retries=0`; `cta.index.embed` retries itself (3 retries, waits of 1, 2
  and 4 seconds, only for 429, 5xx and connection errors) so the rule is in our code and tested. Error messages
  never contain the key.
- The cost shown before a run is the tiktoken estimate; the cost printed after is from the API's reported
  usage. On the first load they were equal (136,297 tokens).
- `openai` 3.x depends on `httpx2` (the pydantic-org successor of httpx, openai requires it since 3.0.0 of
  2026-08-12). It is a transitive dependency and not named in `pyproject.toml`.
- Loader tests run in a throwaway schema (created and dropped per test), because the loader really commits.

## Calendar loader (Oct 12, 2026)

- Same rules as the chunk loader: `--yes` for any write, nothing written in a dry run, one transaction, rows no
  longer in the file are deleted. The integrity checks run after the load and only report; a mismatch is listed
  and the exit code is 1, nothing is corrected silently.
- Weekday check: the first name in `weekday_raw` must be the weekday of `date_start`, and for a range such as
  "Friday-Sunday" the second must be the weekday of `date_end`.
- Year check: the term decides the year (Winter 2027: December is 2026, January is 2027), **unless the PDF
  printed a year in `date_raw`, which decides.** The first version of the check had no such exception and
  flagged `fall-2026-055` ("College Closed", `date_raw` "January 01, 2027", a Friday): a Fall 2026 row that is
  correctly in 2027 because the Fall calendar runs to January 1. The data was right; the check was too blunt.
- Tests that used to assume the real `chunks` table was empty now compare its row count and latest
  `updated_at` before and after.

## Search and the query cache (Oct 12, 2026)

- `search()` is the vector-only baseline: exact cosine scan over all 619 chunks, no filters, ties broken by id.
  Similarity is `1 - cosine distance`.
- The query-embedding cache (`data/cache/query_embeddings.json`, git-ignored) is keyed by sha256(model + "\n" +
  exact question), so a model change never reuses a vector and the question text is not stored in the file. It
  is for speed and repeatable eval runs, not for answers. A cached vector of the wrong size is ignored, and a
  missing or corrupt file is an empty cache. Writes go through a temporary file.
- Downsides: (1) an edited question (even one space) misses the cache, which is correct but costs a call;
  (2) the cache never expires, so it must be deleted by hand if the embedding model is changed *in place* under
  the same name (OpenAI does not do that for a named model, but it is the one case the key cannot see);
  (3) it grows by about 12 KB per distinct question (1,536 numbers), fine for eval sets, not for production
  traffic; (4) a hit hides latency, so latency measurements must say whether the cache was used; (5) it is a
  plain file with no locking, so two processes writing at once can lose an entry (harmless here).
- Sanity check, top 1 similarity (dev questions; test questions were not used):
  q04 0.754 (right section), q12 0.542 (the calendar is not chunked, so it finds the academic-calendar page),
  q21 0.675 but the right course `catalog:EET 3672` was rank 2 (0.650) behind `catalog:EET 2261`, q27 (seats,
  unanswerable) 0.540, made-up on-topic refund question 0.702, made-up off-topic "How do I apply to
  Architectural Technology?" **0.623**.
  The off-topic question scores *higher* than the answerable calendar question (0.542) and than q27 (0.540),
  because the data has an "Architectural Technology" advisor heading (`virtual-advisors#2`, 0.623) that matches
  the words. So top-1 similarity alone will not separate off-topic from answerable cleanly: answerable questions
  here ranged 0.54 to 0.75 and unanswerable ones 0.54 to 0.62. Background for step 8; no threshold chosen.

## Baseline retrieval metrics, dev (Oct 12, 2026)

Vector only, exact cosine, k = 10 retrieved once, no filters; 17 of 20 dev questions scored (q12 has only a
calendar gold source; q27 and q28 are unanswerable with no gold). The test split was not run.

| k | recall | precision | hit rate |
|---|---|---|---|
| 1 | 0.549 | 0.706 | 0.706 |
| 3 | 0.838 | 0.392 | 0.941 |
| 5 | 0.838 | 0.235 | 0.941 |
| 10 | 0.838 | 0.118 | 0.941 |

MRR 0.814. n is 17 overall and 1 to 7 per type or department, so the breakdowns show direction only.
Precision@k is low by construction: most questions have one gold source, so it cannot exceed 1/k.

What the weak spots look like (read from ranks, nothing tuned):
- The one miss (q15, EET student hours): the gold chunk is a table of names and times titled "ETET Office Hours
  (Student Hours) Fall 2024", not in the top 30; the question says "Electrical Engineering Technology" and the
  EET program chunks win.
- Recall stays at 0.838 from k = 3 to 10: the missing gold sources are the ones the question's wording does not
  describe: q01 `applying-graduation#1` ("Check Your Degree Audit", the question is about applying), q06
  `CST-NYT/degrees#3` (a 261-character Data Science/BS chunk; `#1` ranks 12 and `#4` ranks 16 behind the
  department overview), q16 `grade-policies#1` (rank 14; the question has two parts).
- Rank 2 or 3 instead of 1: q21 (`catalog:EET 3672` behind `catalog:EET 2261`: course codes embed weakly), q22
  (a math FAQ section outranks the `catalog:MAT 2675` record), q05 and q06 (department overview chunks outrank
  the specific page).
These are inputs for Phase 3 (hybrid search for codes and names, department filter, reranker), not Phase 2 fixes.

## Chat model settings (checked Oct 12, 2026)

One real call to `gpt-6-luna` (Chat Completions) with `temperature` 0.1, `top_p` 0.3 and `reasoning_effort`
"none" and the prompt "Reply with the single word: ok": all three parameters were accepted without an error (reply
"ok", 13 prompt tokens, 4 completion tokens, 0 reasoning tokens). "Accepted" means the API raised no error; it does
not prove the model uses temperature or top_p. `max_completion_tokens` (600) was added to the answer call and was
also accepted in the first real answers. Settings live in `config/models.yaml` under `answer`.

## Abstain rule and prompt (Oct 12, 2026)

- Top-1 similarity of every dev question (answerable = the 17 scored questions): lowest answerable is q24 0.591,
  then q15 0.606, q18 0.635, q22 0.658; unanswerable in the baseline: q27 0.540, q12 0.542 (calendar, not chunked),
  q28 0.595. **Threshold 0.59**, just below the lowest answerable score, so it blocks no answerable dev question.
- It separates very little: it stops 2 of the 3 dev questions the baseline cannot answer (q27, q12), not q28
  (0.595) and not the made-up off-topic question (0.623). The model's own "ABSTAIN:" line is the second line of
  defence (it caught the off-topic one). Chosen on dev only; it is not to be changed after looking at test.
- A threshold abstain returns the fixed text "ABSTAIN: I could not find this in the City Tech sources I have." and
  names no office (the plan had said to name the best contact; changed by the owner for step 8). Contact
  suggestions are left to the model's own abstain sentence, and only if a source names one.
- Prompt: system message = static instructions; user message = numbered sources (id, source, heading, terms, last
  updated, text), then "Today's date" and the question last. Text in sources is declared to be data.
- Citation check: reported only (invalid numbers are printed and counted), not enforced.
- Cost is computed from the API's reported usage at the full input price (no cached-input discount), so it is an
  upper bound. `--dry-run` estimates the prompt with tiktoken (an approximation for this model) and assumes 300
  output tokens; it still embeds the question (about $0.0000002) because retrieval needs the vector.
- `request_logs`: question and answer are passed through `cta.redact` before the insert; `query_cache_hit` records
  whether the question vector came from the cache (a hit hides embedding latency, so `latency_ms` is only
  comparable between rows with the same flag). Migration `002` adds the column.

## First answers (Oct 12, 2026; not yet judged, step 9 measures them)

Six requests, $0.0009 in total, all query embeddings were cache hits. q27 (seats) was stopped by the threshold
with no chat call. q04 answered "66-67 credits [1]". q13 listed the four Fall 2026 payment-due ranges [1]. q16
answered the aid part and said the sources do not state the grade after Sept 17 (its sources also include
`pdf/dropping-withdrawing-fall-2026#4`, `#6`). q24 (ambiguous) answered 60 and 120 credits without asking which
degree, citing [1][2]. The made-up off-topic question got a model "ABSTAIN:" (top-1 0.623 passed the threshold).
No invalid citations. Obvious problems noticed: the model writes markdown bold in some answers; a course
description in `catalog:EET 4112` contains the raw HTML entity `&rsquo;` (a Phase 1 cleaning gap, not fixed here).

## HTML entities in catalog text (Oct 12, 2026)

A scan of all processed JSON found entities in exactly 4 records, all course records (doc type `catalog_course`) of
the EET department: `&rsquo;` in EET 3222 and EET 4112, `&amp;` in EET 4202 and EET 4212. No page, PDF, contact or
department record had any. Decoded with `html.unescape` in `cta.crawl.catalog.to_record` (title, description,
prerequisite text, department name) and rebuilt with `python -m cta.crawl.catalog --from-raw` (no network). New
validate area `entities` fails on any remaining `&name;` or `&#123;` in `data/processed`. The loader re-embedded 4
chunks (614 tokens, $0.00001). Dev retrieval re-run as `baseline-retrieval-dev-v2`: no metric moved (the retrieved
lists differ only in lower ranks of q21). `baseline-retrieval-dev` stays the comparison point.

## Judge and answer-run rules (Oct 12, 2026)

- Judge model `gpt-5.6-terra`. Probed: `temperature` 0 is rejected with default reasoning ("Only the default (1)
  value is supported"), but accepted with `reasoning_effort: none`; JSON response format is accepted. The judge
  runs at temperature 0 with reasoning off (`judge:` in `config/models.yaml`). It sees the question, the gold
  answer, the answer text and the exact numbered sources the answerer was shown, never the model name or any
  reasoning. A reply that is not valid JSON is retried once, then the question is recorded as "judge failed".
- Gold rules: `ABSTAIN` gold needs no judge (correct if the answer starts with "ABSTAIN:"); `CLARIFY` gold is not
  judged and counts as "not supported yet"; `NO ADVICE` gold is judged only on "gives advice yes/no"; a question
  whose gold sources are all calendar events is judged but reported separately as "not supported yet".
- Correctness and faithfulness shares use the questions with a normal gold answer (n = 15 on dev). The NO ADVICE
  question, the ABSTAIN questions and the "not supported yet" ones are reported on their own lines.
- Failure label, one per question that is not fully correct, by the earliest failing stage: not supported yet;
  abstention error (an ABSTAIN-gold question that was answered); retrieval miss (no scorable gold source in the
  top 10); ranking miss (some in the top 10, none in the top 5); abstention error (it abstained); generation error.
  With several gold sources, "in the top k" means at least one is. A gold answer that explicitly allows abstaining
  (q15) is left to the judge.
- Latency: "total" is the whole `answer()` call (retrieval plus chat), judge time is not included; the chat call
  is timed alone. Every dev query embedding was a cache hit, so no embedding latency is in these numbers. Cost per
  request is answer plus judge; the answer cost is an upper bound (no cached-input discount).
- Judge-check selection rule (fixed before the run, written in `docs/judge-check.md`): up to 2 with faithfulness
  partly/no, then partial/incorrect in id order until 4, then correct in id order until 8. This run had no
  faithfulness "partly" or "no", so it picked q01, q04, q12, q15 (not correct) and q03, q05, q06, q08 (correct).

## Dev baseline, answers (Oct 12, 2026, run `baseline-dev`; not yet checked by the owner)

Retrieval is identical to `baseline-retrieval-dev` (hit rate 0.941 @3/5/10, recall 0.838, MRR 0.814, n = 17).
Answers: correctness on normal gold n = 15: correct 0.67, partial 0.27 (4 of 15), incorrect 0.07; faithfulness n =
15: yes 1.00; NO ADVICE n = 1 correct; abstention accuracy 2/2 (q27 by the threshold, q28 by the model); wrongly
abstained 1 of 16 answerable (q15); citation rate 16/16, 0 invalid citations; 0 judge failures. Cost $0.087 for
20 requests ($0.0039 answers + $0.083 judge); latency median 1,179 ms, p95 2,351 ms (n = 20); chat call alone
median 1,201 ms, p95 2,447 ms (n = 18). Failure labels: generation error 4 (q01, q04, q16, q22), retrieval miss 1
(q15), not supported yet 2 (q12 calendar, q24 CLARIFY).
Things to look at (not conclusions): the partial grades are mostly "omits detail that the gold answer lists but the
question did not ask for" (q04 asked only for credits); that may be the judge being strict about gold completeness.
q15's gold allows abstaining, the judge still graded it incorrect, and its label is "retrieval miss" because the
gold chunk is not in the top 10. q22 is a chained-prerequisite question: the plan lists those as "not supported
yet", but the rule used here labels it generation error (the owner's rule for this step names only calendar-only
and CLARIFY).

## Judge rubric v2, labels, and the freeze (Oct 12, 2026)

- The owner checked 8 dev verdicts (`docs/judge-check.md`). Rubric v1 agreed on correctness 6/8 and faithfulness 7/8:
  the judge was too strict on gold facts the question did not ask for (q04), graded q15 incorrect where the owner
  said partial, and missed that q03's "No." goes beyond the source.
- **Rubric v2** (`src/cta/eval/rubric.py`, `RUBRIC_VERSION = 2`, stored in every run's config): gold facts the
  question does not ask for are not required; faithfulness "partly" means any inference beyond the sources. The
  special gold rules are unchanged. Re-judged from the stored answers with no new answer or embedding calls
  (`baseline-dev-judge-v2`, $0.083): correctness on normal gold n = 15 went from correct 0.67 / partial 0.27 /
  incorrect 0.07 to 0.80 / 0.13 / 0.07 (q04 and q16 became correct); faithfulness stayed yes 1.00 (n = 15).
  Agreement with the owner on the 8 items is now correctness 7/8, faithfulness 7/8. The remaining disagreements
  are q15 (judge incorrect, owner partial) and q03 faithfulness (judge yes, owner partly): the judge's
  faithfulness grade is probably too lenient about inferences. Not tuned further; this is a known limit of the
  baseline's faithfulness number.
- **Failure-label rule v2:** retrieval miss if ANY scorable gold source is missing from the top 10; ranking miss if
  any is missing from the top 5; generation error otherwise; abstention error and "not supported yet" as before.
  Dev labels with it: retrieval miss 2 (q01: `applying-graduation#1` never retrieved; q15), generation error 0
  after q22's relabel, not supported yet 2 (q12 calendar, q24 CLARIFY), not supported yet (chained prerequisite) 1
  (q22).
- **q22 (chained prerequisite):** the only gold source `catalog:MAT 2675` is at rank 2, and its record says
  "Prerequisites of MAT 1575 AND MAT 2580". The model repeated that. The gold answer needs the next levels: MAT 1575
  is at rank 6, MAT 2580 is not in the top 10, MAT 1475 and MAT 1375 are in the top 5 but the model had no instruction
  or tool to follow the chain. The missing pieces are the deeper prerequisite courses, so it is labelled "not
  supported yet (chained prerequisite)". The rule is fixed for q20 and q22, the two questions Phase 1 built as
  prerequisite trees; q20 is not in the dev split and was not looked at. A `--relabel` command recomputes labels
  from stored verdicts with no API call.
- **FROZEN** from commit `08cc8df` (the code and rubric) until after the test run: the answer prompt, abstain
  threshold 0.59, k = 5, models (`text-embedding-3-small`, `gpt-6-luna`, judge `gpt-5.6-terra`), answer and
  judge settings, rubric v2, and the failure-label rules. Nothing is changed after seeing the test results.

## Test run and what it showed (Oct 12, 2026)

Run once as `baseline-final` (`--split test --final`), with everything frozen at `08cc8df` and nothing changed afterwards.
10 test questions, estimated $0.035, real $0.028. Retrieval n = 5 scored: hit rate 0.800 @1, 1.000 @5/@10, recall 0.507
@1, 0.933 @10, MRR 0.850. Correctness on normal gold n = 5: correct 0.60, partial 0.40; faithfulness n = 5: yes 1.00;
abstention accuracy 3/3; wrongly abstained 0 of 5; citation rate 5/5, 0 invalid citations. Labels: retrieval miss 1 (q07),
not supported yet 2 (q11 calendar, q23 CLARIFY), chained prerequisite 1 (q20). Details, the five most instructive
failures and the Phase 3 mapping are in `docs/baseline-findings.md`. The test split is too small (and only 5 questions
are retrieval-scored) to say whether dev and test differ.
Notes: `baseline.json` is the dev rubric-v2 run, the comparison point for dev experiments; `baseline-final.json` is
the test record and is not for tuning. The eval_runs row for `baseline-dev-judge-v2` shows git commit `88bbb08` (the
code at the time of the re-judge); its labels were later recomputed by `--relabel`, which is noted in its config.

## Eval growth: CLARIFY scoring, chain row, tags (Oct 12, 2026; Phase 3 step 0b)

- **CLARIFY scoring rule** (applies to q23, q24, q49 and q50; implemented in Phase 3 step 5, not before): a question with a
  CLARIFY gold passes if the answer asks the clarifying question, OR answers every branch correctly with sources. It fails if
  it gives one answer as if it applied to all branches. q49 ("CLARIFY OR BOTH") and q50 ("CLARIFY OR STATE THE TERM") spell
  this out in their gold text. Until step 5 the judge keeps treating CLARIFY questions as "not supported yet".
- **Chain row:** questions tagged `chain` (q20, q22, q39, q40, q41) are also reported on their own retrieval row. The "all" row is
  unchanged (it stays comparable with the baseline); the chain row is added next to it, so the effect of the Phase 3 prerequisite
  tool is visible without moving the headline numbers.
- **`tags` field:** eval questions may carry an optional `tags` list (for example `["chain"]`); `cta.validate` accepts it, checks
  that it is a list of non-empty strings, and now rejects any other unknown field. Documented in CLAUDE.md and
  `docs/data-validation.md`. `eval/questions.jsonl` is not edited yet: new questions and tags are added in a later step after
  the owner approves the candidates.

## The 60-question set and the new dev baseline (Oct 12, 2026; Phase 3 step 0c)

- q31 to q60 (reviewed by the owner, drafts from `scripts/make_eval_candidates.py`) were merged into `eval/questions.jsonl`: 60
  questions, 40 dev and 20 test, ids unique, every gold source resolves to a chunk or a verified calendar event. The first 30 rows are
  unchanged except for one added field: `tags: ["chain"]` on q20 and q22 (no other field of any existing row was touched). New rows
  with a chain tag: q39, q40, q41. q53 is the single question "What happens to my TAP if my major is still undeclared?" (lookup).
- The system is the frozen one: `git diff --stat 08cc8df..HEAD` for `src/cta/index/search.py`, `src/cta/answer.py` and
  `config/models.yaml` is empty.
- Run `baseline-dev-60` (40 dev questions) is the comparison file for the Phase 3 experiments. `baseline.json` (20 questions) is kept as the
  Phase 2 record.
- Eval runner: questions tagged `chain` are reported on their own retrieval row and answer block; the "all" row is unchanged and still
  contains them.
- The "not supported yet (chained prerequisite)" label now follows the `chain` tag instead of a list of ids in the code. This changed the label of q39
  and q40 in the first printout of `baseline-dev-60` (retrieval miss to chained prerequisite); labels were recomputed with `--relabel`.
  Metrics were not affected.
- Known scoring limit: a NO ADVICE gold passes when the answer abstains (q47 on dev). Fixing it belongs with the CLARIFY scoring in step 5;
  until then NO ADVICE results are read with that caveat.

## Hybrid search code stays, switched off (Oct 12, 2026; Phase 3 step 1)

- Experiment 1 was rejected by the rule written beforehand (`docs/experiments.md`). Default `retrieval.mode` stays `vector`, so the frozen baseline is
  reproduced exactly (the vector run matches `baseline-dev-60`).
- Kept in the repository, off by default: migration 003 (`chunks.tsv` generated column with the `english` configuration, GIN index; the loader never
  writes it and `load --dry-run` still shows 0 changes), `retrieval.mode` with `CTA_RETRIEVAL_MODE`, `--mode` on the search and eval commands, reciprocal rank
  fusion, `cta.eval.compare` (applies the rule), retrieval time recorded per question. A further hybrid variant can reuse all of it.
- The abstain threshold is applied to `Search.top_vector_similarity` (the best cosine in the vector list) in both modes. In vector mode this is the same value as
  before (the top-1 similarity), so the threshold decisions and all baseline numbers are unchanged.

## Judge rubric v3 and the BM25 code (Oct 12, 2026; Phase 3 step 1b)

- **Rubric v3 (faithfulness only).** In `baseline-dev-60` two chain answers (q22, q40) were graded faithfulness "no". In both the model said the sources do not
  state some prerequisite (MAT 1575 and 2580 for q22, CST 1201 for q40), and in both those courses were not among the five numbered sources shown, so the statement was
  true. The judge called it "unsupported" (q40) or "contradicted" by other chunks (q22), and in q40 it also said CST 1204's prerequisites were wrong although the shown source
  states them. v3 says: judge only against the numbered sources shown, never outside knowledge; a statement that the sources lack X is faithful when X is absent from those
  sources (and a "no" when X is there). "partly" and "no" otherwise keep their v2 meaning. Correctness and the special gold rules are unchanged. The version is stored in every run config. The next
  answer-level run re-judges the stored `baseline-dev-60` answers under v3 first, so the comparison is like for like; nothing was re-judged in this step (no paid call).
- **BM25 code stays, off by default.** `cta.index.bm25`, `retrieval.mode: hybrid_bm25`, the `bm25_rank` field and the in-process index are kept in the repository like the ts_rank hybrid
  mode; experiment 1b was rejected by the rule as written (MRR -0.023 against a limit of -0.02). Both can be reused by the reranker experiment.

## Department filter code stays, switched off (Oct 12, 2026; Phase 3 step 2a)

- Experiment 2a was rejected by the rule written beforehand (no first-relevant rank changed). `retrieval.dept_filter` stays `"off"` (quoted in YAML because a bare `off` is a boolean).
- Kept, off: `config/departments.yaml` (aliases and prefixes written before the run, from the catalog data and project notes, not edited after results), `cta.index.departments`, the filter in
  `cta.index.search` (all three retrieval modes), `--dept-filter` and `CTA_DEPT_FILTER`.
- Data fact: course chunks have scope `city_tech` (with the department id in `department`), so the scope-based rule never filters them. Filtering them by their department field would be a different,
  separately pre-registered experiment.
- The abstain threshold reads the best vector cosine similarity after the filter; with the filter off, or with no department detected, it is the same value as before.

## Spend limit raised for step 3b only (Oct 12, 2026)

- `eval.max_cost_usd` stays at $1.00 per run. For Phase 3 step 3b alone, the owner set a total allowance of **$2.50**, because the step repeats the same 40-question run several times to measure noise (three runs per arm, a
  judge repeat and a v3 re-judge; one judged run costs about $0.16, mostly the judge). `run_answers --budget` takes the total allowance and subtracts what the step's earlier runs already cost (the labels listed in the code); a run refuses
  to start if its estimate does not fit and stops by itself, before the next question, if the running cost would pass it. Other steps keep the old limits.

## Reranker kept after the answer-level check (Oct 12, 2026; Phase 3 step 3b)

- `retrieval.rerank: pool_a` stays the default: the pre-registered four-part rule passed (`docs/experiments.md`, experiment 3b). `CTA_RERANK=off` / `--rerank off` reproduces the old system; answer-level runs must pass `--rerank` explicitly when
  they want a particular arm. Each answer-level run with the reranker on writes its own reranker score cache (`data/cache/rerank-<label>.json`, not committed), so its reranker cost and latency are real, and a re-judge of an ON run needs that file.
- A stored run is re-judged with the reranker setting it had (`eval_runs.config.retrieval.rerank`, "off" for runs made before the switch), never the current default.
- Rubric v3 did not change the q22 and q40 faithfulness verdicts; it moved three other verdicts (q01, q52, q56) on identical answers. The v3 rubric stays in use; the owner checks `docs/judge-check-v3.md` by hand.
- The step's $2.50 allowance is the only departure from the $1.00 per-run cap (see above); about $1.22 was spent.
