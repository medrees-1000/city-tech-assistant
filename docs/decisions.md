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

## LangGraph for the router (Oct 12, 2026; step 4a)

- **Added:** `langgraph==1.2.14`, pinned exactly in `pyproject.toml` and `uv.lock`. **Reason:** a graph with explicit nodes and conditional edges for the router (classify, calendar, retrieve, and the calendar-to-retrieve fall-through of amendment 1); steps 4b (prerequisite chain) and 4c (contact lookup) add tool nodes to the same graph; the LangSmith client it brings is what the step 6 tracing uses.
  Retrieval, evaluation and the data pipeline stay hand-built (framework policy in `docs/phase3-plan.md`). The owner decided this on Oct 12 after seeing the dependency tree, which is larger than `langchain-core` plus small pure-Python packages (the alternative was a hand-written router).
- **The 18 new packages** (all installed by `uv add langgraph==1.2.14`): `distro 1.9.0`, `jsonpatch 1.35`, `jsonpointer 3.2.1`, `langchain-core 1.6.10`, `langchain-protocol 0.0.19`, `langgraph 1.2.14`, `langgraph-checkpoint 4.2.0`, `langgraph-prebuilt 1.1.0`, `langgraph-sdk 0.4.6`, `langsmith 0.14.7`, `orjson 3.13.0`,
  `ormsgpack 1.12.2`, `requests-toolbelt 1.0.0`, `tenacity 9.2.1`, `uuid-utils 0.17.1`, `websockets 16.1.1`, `xxhash 4.0.1`, `zstandard 0.25.0`. Compiled ones: `orjson`, `ormsgpack`, `xxhash`, `uuid-utils`, `zstandard` (and `pydantic-core`, already present). Already installed and now also used: `pydantic`, `httpx2`, `requests`, `anyio`, `pyyaml`, `packaging`, `httpx`, `typing-extensions`.
- **Safeguards.** (a) Tracing stays off: `cta.settings.enabled_tracing` / `refuse_tracing` check `LANGSMITH_TRACING`, `LANGSMITH_TRACING_V2`, `LANGCHAIN_TRACING_V2`, `LANGCHAIN_TRACING` (true, 1 or yes); a test asserts none is enabled in the test environment and that importing `cta.graph` and `langgraph.graph` makes no network call (a subprocess with sockets disabled).
  (b) `run_retrieval` and `run_answers` refuse to start (exit 2, message on screen) if either is enabled. (c) Nothing in the code enables tracing; when step 6 does, it will see only redacted text.

## Calendar questions merged; question sets and comparability (Oct 12, 2026; Phase 3 step 4a-1)

- **Merged.** 14 owner-approved calendar questions (q61 to q69, q71 to q75; `eval/questions.jsonl` is append-only, no existing row changed) with the tag `calendar`: 8 dev (q61 q63 q64 q65 q67 q68 q71 q75) and 6 test (q62 q66 q69 q72 q73 q74). The ids come from the candidate file; **q70 was dropped by the owner** and the id stays unused. Gold answers are built mechanically from the calendar rows
  (`scripts/make_calendar_candidates.py`, appended by `scripts/merge_calendar_questions.py`); q72 is `ABSTAIN` with the Registrar contact in the note; q74 is type `ambiguous` with the existing CLARIFY rule (it passes if it asks which kind of drop, or lists every branch correctly with sources), written like q24 and q49 ("CLARIFY OR ALL BRANCHES: ... Facts: ..."); q75 keeps the three rows
  -046, -045, -047. `eval.today` stays 2026-10-11 (the "assumed term" sentence in the gold says so). For an unnamed "College Closed" row the gold says "College Closed" and never names a holiday (none of the merged questions needs such a row).
- **Why q70 is dropped (the TBA question).** Its gold row (`spring-2027-055`, date TBA) is the same as q11 (test); a dev copy would make the test case easy. The TBA rule (a null date means "not announced", plus the Registrar contact) must be covered by unit tests in step 4a, and **q11 is the end-to-end check in the test split.**
- **Independent PDF check** (`docs/calendar-candidates.md`): every gold row of the 14 questions, plus the two Sunday rows, was compared with its PDF from page images read by eye (pdfplumber `page.to_image`; no new dependency, `pdftoppm` is not installed). All 22 rows matched; marked "checked by Claude Code, owner spot-check pending", not "owner verified". The two Sunday rows (`winter-2027-003`, `-019`) are printed as Sundays in the PDF itself.
- **Counts now.** Dev 48 (40 old + 8 new), test 26 (20 old + 6 new), 74 questions. The 14 new questions are calendar-only gold, so none is retrieval-scored: **the 30 retrieval-scored dev questions and all retrieval numbers are unchanged.** Only answer-level runs see the new questions.
- **What `baseline-dev-60` covers.** The 40 dev questions: q01 q03 q04 q05 q06 q08 q09 q12 q13 q14 q15 q16 q18 q19 q21 q22 q24 q27 q28 q30 q31 q33 q34 q36 q37 q39 q40 q42 q44 q45 q47 q49 q51 q52 q53 q54 q56 q57 q58 q59 (30 retrieval-scored). It is not re-run; later dev runs on the 48 are compared with it on the 40 common ids.
- **Comparability, minimum added.** (a) Every run config (`eval_runs.config`) and results file records `question_ids` (sorted) and `question_ids_hash`. (b) `cta.eval.compare` and `cta.eval.answer_compare` compare on the common ids only when two runs cover different questions and say so in their output (the retrieval compare then shows MRR and hit rates from first ranks and does not apply the keep rule, because recall needs one question set; the answer compare recomputes every aggregate from the records of the common ids).
  (c) `run_retrieval` and `run_answers` gained `--ids q01,q02` and `--tag calendar` (they did not exist; an id outside the split is an error). (d) A re-judge or relabel of a stored run now takes only the questions that run answered (it would have failed on the new ones).
- **Test split.** The 6 new test questions are run once at the Phase 3 milestone together with the old test questions, never before; no test results were looked at in this step.

## Router: calendar tool details (Oct 12, 2026; step 4a)

- **Calendar rows are read from `data/calendar/calendar_events.json`** through `load_events_for_indexing` (the same function that fills the `calendar_events` table, so unverified rows are refused), not from the table: the router needs no database for the calendar and the tests do not depend on table contents.
- **Interpretations of the pre-registered term rules, fixed before any run:** "summer" with no year and a season with no running or future term (for example "fall" asked after the Fall 2026 term ended) are unsupported labels (searched in the row text; no match: abstain), not the current term; "autumn" means fall; a year alone that is in a calendar term ("2026", "2027") is "no season named" and resolves to the current term, any other year ("2028")
  is unsupported. The current term is the term in session today (between its "Start of ..." and "End of ..." rows), else the next to start. A failed or unusable classifier reply sends the question to the old pipeline (route `other`) and is counted.
- **Calendar-only scoring** (`calendar_scoring: 1` in run configs, always on with `router.mode: "on"`, optional with `--calendar-scoring`) is deterministic: correct = returned row ids equal the gold ids, partial = a non-empty proper subset, incorrect otherwise (a returned row outside the gold set is a "wrong date stated"; no rows returned means it was not answered by the calendar). New failure labels: `calendar wrong row`, `calendar missed` (also partial, not routed, fell through), `calendar abstained` (the calendar route abstained).
  Other labels and the old "not supported yet" behaviour for calendar-only gold are unchanged with scoring off. `cta.eval.run_answers` goes through the graph only with `router.mode: "on"`; with `"off"` it calls `answer` exactly as before.
- **Logging:** migration 004 adds `request_logs.route` and `request_logs.router` (jsonb) because no existing column can hold them; the router writes one row per request (question and answer redacted), the retrieve route no longer writes its own row inside the router (it calls `answer(log=False)`).

## Router stays off after experiment 4a (Oct 12, 2026)

- The pre-registered rule failed on (a) (10 of 13 calendar-only dev questions correct in every run, mean 10 against 11 required) and (b) (a returned row outside the gold set in every run), so `router.mode` stays `"off"`. Everything stays in the repository, off: `cta.graph` (state, terms, classify, select, render, build), `router.mode` and `CTA_ROUTER_MODE`, migration 004 (`request_logs.route`, `router`), `run_answers --router/--calendar-scoring/--budget-labels`, `cta.eval.router_report`.
- The graph, its prompts and the term rules are not edited to chase the failures; the two causes (rows of another term's calendar, same-date duplicate rows) are logged in `docs/experiments.md` as separate follow-ups. Whether q63's gold should list `winter-2027-005` is the owner's decision about the gold, not about this result.

## Calendar gold refinement: acceptable extras and scoring v2 (Oct 12, 2026; Phase 3 step 4a-2, part 1)

- **Why.** After the 4a run (REJECT, which stands unchanged) the two same-date cases q33 and q63 showed that the exact-rows rule penalises rows that say the same thing in different words ("Classes begin" and "Start of ... term"). The owner asked for a refinement of the gold, not of the 4a result; the re-run in part 2 is a fresh experiment with its own pre-registration.
- **New optional question field `calendar_acceptable_extra`** (a list of calendar row ids): rows that may appear in the answer to a calendar-only question without penalty. The loader checks that it is a list of non-empty strings, that no id is also a gold source, that each id is a verified calendar event, and that the question's gold sources are all calendar rows. `eval/questions.jsonl` is **not changed yet**: changes are applied only after the owner has marked `docs/calendar-same-date.md`
  and replied "continue"; every changed question will then be logged here with before and after, with the reason "owner decision after the 4a run; the 4a result is not changed; the re-run is a fresh experiment".
- **Criterion for an acceptable extra (fixed):** yes only if the row's event text means the same thing as the gold row's event (same event, different wording). Proposals were written from event texts and questions only, not from router output. Owner recommendation, pre-filled and not applied: q33 `spring-2027-007` required, `spring-2027-006` an acceptable extra (today both required); q63 `winter-2027-004` required, `winter-2027-005` an acceptable extra.
- **Scoring v2 (`calendar_scoring: 2`).** The gold sources are the required rows. Correct = every required id returned and every returned id in required or extras; partial = a non-empty proper subset of the required ids with nothing outside required and extras; incorrect = any returned id outside both (a "wrong row stated"), an abstention, or no rows. Scoring v1 (exact rows, `calendar_scoring: 1`) stays available and is the default with `--router on`; every calendar-only record stores both verdicts
  (`calendar_v1`, `calendar_v2`) whichever one decides, so every run can be reported under both (`run_answers --calendar-scoring 1|2`).
- **Information only:** `docs/calendar-same-date.md` re-scores the three stored 4a runs under v2 with just the two pre-filled changes, without any model call ("re-scored, not a decision").

### Applied to `eval/questions.jsonl` (Oct 12, 2026, after the owner replied "continue" and accepted the proposals and the two pre-filled changes)

Reason for both: owner decision after the 4a run; the 4a result is not changed (it stands as REJECT, scored with the old gold); the re-run in step 4a-2 part 2 is a fresh experiment. The only "yes" proposal in `docs/calendar-same-date.md` was q63's `winter-2027-005`; every other collision is "no". `gold_answer` text and every other field are unchanged.

| question | before | after |
|---|---|---|
| q33 | `gold_sources`: `spring-2027-007` ("Classes begin") and `spring-2027-006` ("Start of Spring 2027 term."), both required; no extra | `gold_sources`: `spring-2027-007` only (required); `calendar_acceptable_extra`: `["spring-2027-006"]` |
| q63 | `gold_sources`: `winter-2027-004`; no extra | `gold_sources`: `winter-2027-004` (required); `calendar_acceptable_extra`: `["winter-2027-005"]` ("Classes begin") |

`docs/calendar-same-date.md` was generated before this change and is left as it was (its v1 column is the 4a scoring with the old gold).

## Router on, selector v2 (Oct 12, 2026; step 4a-2 result)

- Experiment 4a-2 (selector v2) passed its pre-registered rule, so `router.mode` is `"on"` and `router.selector` is `2` by default (`config/models.yaml`; `CTA_ROUTER_MODE=off` / `--router off` restores the old pipeline, `CTA_ROUTER_SELECTOR=1` / `--selector 1` the 4a selector). Tests pin the router off except in the router tests.
- The 4a result is unchanged (REJECT, v1 scoring, old gold). The 4a-2 pass is on a refined gold and a changed selector; most of the improvement from 10 to 12 of 13 comes from the gold change (q33, q63), and q37 is the selector's own gain. The graph is unchanged; selector v2 is a pool and prompt change.
- The unsupported-term path keeps the 4a selector; `calendar_scoring` 1 stays available and every calendar-only record stores both verdicts.
- Known remaining limitations: "next semester" resolves to the current term; q75 (several same-day-type rows) varies between runs; the classifier sends q09, q13 and q30 to the calendar node (q13 falls through to retrieve, the others are answered correctly there).

## Judge variants: v3 stays; faithfulness caveat (Oct 12, 2026; step 4-judge)

- Three judge variants were tested against 16 labeled and 10 planted answers (`docs/step4-judge-results.md`); none met the pre-registered rule, so the judge stays rubric v3 with the configured settings and `RUBRIC_VERSION` stays 3. No `judge.variant` switch was added (it was only to be added for a qualifying variant).
- **Faithfulness caveat:** v3's faithfulness verdicts disagree with the owner and the second reader on "the sources do not state X" answers (q22 and q52 on the stored baseline answers) and on q03. The faithfulness numbers of steps 3b, 4a and 4a-2 therefore carry a caveat line in `docs/experiments.md`; differences of one or two questions in faithfulness between arms are not to be read as effects. The planted-error check shows the judge does catch a changed number or a false "the sources do not state X" claim when the sources show it.
- **Labels:** `eval/judge_labels.json` holds the 16 labels (8 owner, 8 second reader accepted by the owner on 2026-10-12) as references to stored runs only.
- **API facts for this judge model** (probe calls): `reasoning_effort: "minimal"` is rejected (supported: none, low, medium, high, xhigh); with "low" or "medium" `temperature: 0` is rejected (default only), so a reasoning judge cannot be run deterministically.
- **Observation not acted on:** with low reasoning effort the judge matched the labels better on correctness (15 and 16 of 16 against 12). Acting on it would need its own pre-registered experiment; it would also make the judge stochastic.
- **Process error found and corrected:** the v3 row added to the `docs/judge-check.md` agreement table in the previous step compared verdicts on different answers for five items; a correction note was added there (the figures coincide with the corrected ones).
- **Phase 3 plan:** step 4c now says to attach the relevant office's contact to every abstention (CLAUDE.md requires it; the q52 and q15 abstentions name none).

## Chain questions q76 to q87 merged (Oct 12, 2026; Phase 3 step 4b-1)

- **Independent check first.** `scripts/verify_chain_candidates.py` (not built on the generator's expansion code) re-read the raw saved catalog JSON (`data/raw/app.coursedog.com`), the raw rule files, the rule cache and the contact chunks and checked all 12 candidates; all passed (`docs/chain-verification.md`). The owner delegated the review to the assistant's recommendations on 2026-10-12 and has not compared the golds with the live catalog site; the golds are built mechanically from the records, so the raw-JSON check is what supports them.
- **Four edits:** q82 is type `unanswerable` with an empty `gold_sources` (the convention of the existing unanswerable questions; `catalog:CST 3508` is named as the reference record in its note); q86's gold is the catalog text word for word plus one sentence naming DEN 1112 as a corequisite and the other conditions (CUNY proficiency, department approval), `gold_sources` stay DEN 1100 and DEN 1112; the q87 spacing is in the raw catalog text itself ("flow charting.SATISFIES FLEXIBLE CORE- SCIENTIFIC WORLD", checked in the raw JSON), not a join by the generator, so the gold keeps it verbatim; the checklist is filled.
- **Merged** (append-only, no existing line changed): dev q76 q77 q79 q81 q83 q85 q87, test q78 q80 q82 q84 q86; chain questions carry the tag `chain`, q87 (the non-chain control) does not. q83 (unknown code `CST 4999`) has department `CST-NYT` like q27; q84 (`ENG 1101`, outside the four departments) has department null like q29 and q46. The file now has 86 questions: **55 dev and 31 test**. The new test questions are run once at the Phase 3 milestone with the other test questions, never before.
- **Facts from the check:** the raw saved pages hold 1,445 distinct records (1,444 distinct codes: AFR 2000 has two records), all Active, no inactive or legacy forms; `CST 4999` appears nowhere in them; `ENG 1101` exists in the full list (English Composition I, department ENGL-NYT) so q84's ABSTAIN rests on scope, not on a missing record; "Database Design" is the exact title of one record (CST 3504) of the four departments' 197 records and no other title contains the phrase.

## Prerequisite-chain tool as a LangChain `@tool` (Oct 12, 2026; step 4b plan)

- The chain lookup is a `@tool` from `langchain_core.tools`. Reason: it replaces hand-written tool plumbing (a name, a description from the docstring, an argument schema and one `invoke` call that the graph node uses) and later tools (4c contact lookup) follow the same shape. No new dependency: `langchain-core` is already installed as part of `langgraph==1.2.14`. The walk itself stays plain, deterministic code; no model chooses which courses are in the chain. If a new package were needed, the step stops and asks.
- Prompts of the route (`src/cta/graph/prompts/classify_v2.txt`, `chain_answer.txt`) are committed with `docs/step4b-plan.md` before any paid call and are not edited after results.

## Prerequisite-chain tool on by default (Oct 12, 2026; step 4b-final)

- `router.chain` is `"on"` in `config/models.yaml`. Why: experiment 4b passed its pre-registered rules R1 to R6 on dev (`docs/experiments.md`): all 8 chain questions answered by the chain node in every run, the control q87 never, calendar questions unchanged (13 of 13, 0 wrong rows), judged correctness on the 48 shared dev ids 0.744 against 0.679, q83 abstains. `--chain off` and `CTA_ROUTER_CHAIN=off` still turn it off (tests pin it off where they need the old classifier).
- **Disclosed:** the first computation of the report counted q83's chain no-record abstain as a calendar misroute (a shared route name) and showed R4 as FAIL; the measurement helper was corrected to the classifier's intent after the first numbers were seen. The correction and the reason are in `docs/step4b-chain-results.md` ("Measurement note"); the owner decided to switch the default on knowing this.
- Known limits are listed in `docs/phase3-plan.md` (q39 beyond depth 4, q40 graded partial although every gold source was received).

## Contact line on every abstention (Oct 13, 2026; step 4c)

- Owner decisions: seats, instructors and meeting times of a named course go to the department of the course prefix (when it is one of the four); fallback office is the Registrar; Special Circumstances is printed by role only; only email and phone are printed (room and hours are stored in `config/contacts.yaml`); the Dropping-and-Withdrawing PDF maps to the Registrar; the account cues stay (written knowing q44, so dev cannot validate them, nor the office table, which was derived with the dev abstentions in view: the test split at the final milestone is the check); q47 and q49 only get the line.
- `contacts.yaml` takes phones from the `Phone:` or `Office Phone:` line only. The validator (`cta.validate`, area `contacts`) refuses a number printed only after `Fax:`, the 24/7 AI-agent line, an email missing from the record, and a source page or `fetched_at` that does not match.
- The calendar node still builds its own Registrar line (`render.abstain_text`); `add_contact` skips a line that is already in the text, so those answers are byte-identical and never get two. The graph is unchanged (the step runs after it, in `Router.answer`), so `docs/architecture.md` is unchanged except for one sentence. The router-off path (the frozen baseline) gets no contact.
- The prompt (rule 5: name an office only if a source does) is unchanged; replay rule D5 checks that no email or phone appears that is neither in the table nor in the original answer.
- Tests pin `CTA_ROUTER_CONTACTS=off` where they test the earlier router behaviour (like chain), and test contacts in `tests/test_contact.py`.
- `router.contacts` is `"on"` by default since the replay passed.

## Contact records: phones only from Phone lines (Oct 13, 2026; step 4c-data)

- `phones` of a contact record (and of the page records' `contact`) holds only numbers on `Phone:` or `Office Phone:` lines. Fax numbers are in `fax`, the Admissions 24/7 AI-agent number is in `ai_agent_line`; the panel text, and so the contact chunks, keep the printed labels. No chunk changed, so nothing was re-embedded. "Phone Number:" lines inside hours tables are not treated as phone lines (they repeat the `Phone:` number).
- Other readers of `phones` (`render.registrar_contact`, the candidate scripts) get the corrected list; for the Registrar the value is unchanged.

## Contact policy v2: a contact only when the office clearly applies (Oct 13, 2026)

- **Why.** Manual testing in the chat page showed that low-similarity abstentions got unrelated cards: "what questions can I ask you" the Mathematics card, "my mom died" the Financial Aid card, a question about logging in to CUNYfirst with an email address the Dental Hygiene card. A wrong card is worse than none. CLAUDE.md now says "Abstain, with the relevant office's contact when one clearly applies".
- **Confident rules (the only ones that add a contact):** (1) the question names one of the four departments, by name or by a course code with one of their prefixes: that department; (2) an account-word cue: the office the table maps it to; (3) a calendar abstention: the Registrar; (4) a chain no-record for a code with a prefix of the four departments: that department. The precedence stays as in policy v1 (calendar and chain abstentions first, then the named department, then the cue), because the rule tests are kept: a calendar abstention that names a course still goes to the Registrar.
- **Removed:** the chunk-source map (rule 5 of v1), the Registrar fallback, and the Advisement default for a chain no-record outside the four departments. With no match the abstention has no contact: `contact` is null in the API and the answer text has no contact line. `add_contact`, `router.contacts` and `--contacts` keep their structure; `config/contacts.yaml` keeps its entries (its `pdf_offices` and `fallback` keys are no longer read).
- Pre-registration and replay: `docs/step4c-plan.md`, section "v2". Milestone 1 was run with policy v1; the final milestone uses v2 (addendum in `docs/milestone1-results.md`).

## Chat polish after manual testing (Oct 13, 2026)

1. **Markdown subset.** The chat page renders paragraphs, "- " bullet lists, **bold** and the `[n]` citation links from answers. Hand-written pure function (`web/lib/markdown.ts`, node:test tests), no new dependency; text goes through React text nodes (never innerHTML), so HTML-looking text is shown as text; an unmatched `**` stays text.
2. **Abstain and "not announced yet" are plain assistant messages** (no amber or teal box, no state label). The contact card still follows the message when `contact` is present. `answer_type` and `abstain_reason` in the API are unchanged (they feed the logs).
3. **Topic-aware abstain wording (API layer only).** When the router result is abstained on the retrieval route with a generic text (threshold abstain `below_threshold` or a model-written ABSTAIN line, code `model`), one extra model call (same chat model, temperature 0, JSON; prompt `src/cta/api/prompts/topic.txt`, committed before any paid call) returns `{topic, in_scope}`. The code writes the sentence from two fixed templates; the model never writes it. The topic is sanitised (control characters, markdown, links, emails removed; at most 8 words and 60 characters; anything that redaction would change, or empty, falls back). If the call fails or the reply is unusable the generic sentence stays. Calendar abstains, chain no-record and personal-account messages are not changed. The call's tokens, cost and time are added to the request totals and to the trace (stage `topic`). Nothing in the pipeline, the router, the eval path, prompts of the pipeline or thresholds changes.
4. **Account cues.** More first-person and account words count as account questions, only when the system already abstains: "my aid" maps to Financial Aid; "emplid", "student id", "log in", "login", "password" map to no office (the data has none), so the answer is the personal-account message with no card. Replay on the stored dev answers: non-abstaining answers byte-identical; contact changes listed by id (`docs/step4c-replay-v2.md`).
5. **`cta.api.logs`** collapses whitespace and line breaks in the printed question to single spaces.

## Chat page, finishing round (Oct 13, 2026)

1. **Markdown headings.** The subset gains headings (`#`, `##`, `###` at the start of a line), shown as small heading elements (h3/h4 styling, not page-title sizes), with the same safety rules (React text nodes only; a `#` in the middle of a line stays text).
2. **"Hold" cues.** The processed data (chunks and contacts) is searched for which office, if any, it says handles account holds. If it names one office clearly, "my hold", "my holds", "a hold on my" and "my account" become account cues mapped to that office; if not, the same cues map to no office (personal-account message, no card). Cues apply only when the system already abstains. The evidence and the result are recorded below once the search is done.
3. **"How this was found" panel** on each assistant answer: a collapsed toggle built from the API's `how_found` data, in plain language (route in words, sources in the order shown to the model with the rerank order and a note on a weak best match, calendar term and row, chain courses and "no record" ones, time per step, tokens and cost in cents, and for abstentions why, with the top similarity and the cutoff). Nothing is shown that the API did not send. Pure helpers with node:test tests.
4. **Privacy notice** under the input: one short line and an expandable "What is saved?". The text is checked against migration 005 and the log writer; where it differs from the plan, the true statement is used.

### Hold cues: the evidence and the decision (Oct 13, 2026)

Search of `data/processed/chunks.jsonl` (every chunk, including the contact chunks) for "hold(s)": the data does **not** name one office that handles account holds.
- `page/bursar/payment-deadlines#1` (https://www.citytech.cuny.edu/bursar/payment-deadlines.aspx): "If your tuition remains unpaid after enrollment a hold will be placed on your account that will prevent you from adding or swapping courses." (names a cause, not an office that handles holds)
- `page/registrar/epermit#1`: "Must not have any holds on academic record." (a condition, no office)
- `pdf/cunyfirst-student-reference#2` (CUNY-wide guide, data/pdfs/cunyfirst_student_reference.pdf): "On the left sidebar the Holds option will show all holds. By clicking on each Hold, you can view the details, including the office contact information, and instructions on how to resolve it." (the hold itself names its office, in CUNYfirst, which is behind a login and out of scope)
- the contact chunks mention no holds; the other matches are the verb ("holds a master's degree", "hold an integral role").

**Decision:** not clear, so "my hold", "my holds", "a hold on my" and "my account" are added to `account_only` (account questions with no office): the page shows the personal-account message and no card. They count only when the system already abstains.

### Privacy notice: what was checked against the code (Oct 13, 2026)

`web/lib/notice.ts` holds the text; `tests/test_requestlog.py` checks it against the code. Verified true: only emails, phone numbers, SSN-like numbers and 8-digit IDs are removed (`cta.redact`); names are not (tested); `request_logs` has no column for an IP address, user agent, cookie or header (migration 005 and the writer's column list), and neither the API nor the page sets a cookie or uses browser storage; the stored trace holds ids, scores, times, tokens and cost, no chunk text. **Two statements in the plan were not exactly true, and the notice uses the true ones:** (1) rows are deleted after 30 days only when the purge command is run, which is by hand, so the notice says so; (2) uvicorn's access log would print each client address to the terminal (not to the database), so the launcher now starts the server with `access_log=False` and a test checks it.

## Feedback votes and inspecting one request (Oct 13, 2026)

Per-answer feedback: a vote is only "up" or "down", with **no free text**, saved against the request id so the owner can list mistakes and turn real ones into new dev questions later. Stored with a vote: the vote and the time of the vote, in two new columns of the request's own row (migration 006: `feedback`, `feedback_at`); no IP address, user agent, cookie or other identifier. Only API rows (`source = 'api'`) can be voted on; the latest vote wins; the vote changes nothing but those two columns; a vote goes with its row when the purge command deletes it after 30 days. The page offers the two buttons under every assistant answer (including abstentions and personal-account messages) and keeps the vote in the page state only (no cookies, no storage). `cta.api.logs` gets a feedback column and filter, vote counts in its footer, and `--id REQUEST_ID` to print one whole stored row (redacted again when printed).

## Politer abstain wording, natural topics, page padding (Oct 13, 2026)

1. **Templates** (the code writes them; the model still only supplies `topic` and `in_scope`): out of scope -> "I'm sorry, but I can only help with City Tech questions (registration, deadlines, advising, tuition and aid, and four departments), so a question about {topic} is outside what I can answer."; in scope but nothing found -> "I'm sorry, I couldn't find anything about {topic} in the City Tech pages and documents I use." The generic fallback sentence also gets a short apology prefix ("I'm sorry, ..."). Calendar, chain no-record and personal-account messages are unchanged.
2. **Topic prompt** (`src/cta/api/prompts/topic.txt`, new version committed before any paid call): the topic is written from the assistant's point of view ("my dad" -> "your dad", "my aid" -> "your financial aid"); course codes, department names and acronyms keep their capital letters exactly as in the question (EET, CST 3504, Dental Hygiene); never names, IDs or other numbers (the number inside a course code is the one exception); at most 8 words. The sanitising rules and fallbacks are unchanged.
3. **Page padding:** the conversation area gets bottom padding and the page a `scroll-padding-bottom`, so the last line of an opened "How this was found" panel or sources list is never left under the input bar.

## Owner decisions on the plan of 2026-10-13 (docs/chain-layout-plan.md)

1. `answer_type: "clarify"` (and a `clarify` route value if the logs need it) is added to the API contract and the page types later, in the CLARIFY step (step 4 of the build order), not before.
2. No suggestion buttons on the clarifying reply.
3. The deterministic CLARIFY rule is added to `run_answers` later, in the CLARIFY step, pre-registered then.
4. No Advisement contact for advice questions.
5. q42 moves to the chain node in the two-course step (step 2); the 4b definitions M2 and R1 are restated before that step's run.
6. NO ADVICE action nouns include "sign up" and "payment plan", with a control check that a question without an advice cue ("How do I sign up for a payment plan?") does not fire.

**Build order of the five steps:** chain layout, two-course questions, date lists, CLARIFY, NO ADVICE. Each step gets its own pre-registered rule, committed before its first paid call.

### Step 1 (chain layout): the keep rule, pre-registered before any paid run
Quoted exactly from `docs/chain-layout-plan.md`, "How I would introduce it": "One change behind a switch: `router.chain_render: "model" | "code"` (default `"model"`; `CTA_ROUTER_CHAIN_RENDER`, `--chain-render`). Keep rule, measured on **dev only** with the chain questions (CH set), judged under the current rubric, repeated judge twice because the answers themselves are deterministic: (K1) checks 1 to 9 pass; (K2) judged correctness on the CH set not lower than the 4b mean by more than one question, faithfulness not lower by more than one (with the usual caveat); (K3) M1 to M6 of the 4b report unchanged; (K4) cost per chain question lower. If kept, the default flips in its own commit."

How the rule will be read, fixed before the run: **K1 and K4 are deterministic** (the checks over all 197 chains, and token and cost numbers). **K2 is decided by the judge's verdicts**, the part that is known to be unreliable on "the sources do not state X" sentences ("No prerequisite listed in the catalog" is of that kind), while the answer text is verbatim by construction; K2 compares the mean of the two judge passes with the mean of the three 4b runs on the 8 CH questions (q22 q39 q40 q76 q77 q79 q81 q85). **K3**: the new run also contains q83 (no record) and q87 (the non-chain control); M1 (every CH question answered by the chain node), M3 (gold catalog sources among the sources received) and M6 (q83 abstains) are measured; M2, M4 and M5 involve questions this change cannot touch (only the chain node's answer step changes; the classifier and every other route are untouched) and are therefore stated as "unchanged by construction", not re-run. **Cost:** the plan's two figures disagree (the introduction paragraph said about $0.04, the step list $0.07); the honest estimate is 10 answers plus 2 judge passes of about $0.0043 each, **about $0.07**.

### Chain layout step 1: result (Oct 13, 2026)
The keep rule (K1 to K4) passed on dev (`docs/chain-layout-results.md`); `router.chain_render` is now `"code"` by default. K2 passed at the edge of what the rule allows (faithfulness 7.00 against 8.00 of 8; the one drop is q39, where the judge does not see the walk's depth-limit sentence); this is recorded so that nobody reads it as a clean improvement. `"model"` stays as the fallback until the final cleanup, as decided. The model-written chain answers of milestone 1 remain the record of the old route.

## q40 gold correction: source wins (Oct 13, 2026)
The gold check on q40 (dev) found that the last sentence of its gold_answer did not match the catalog record of CST 1204, whose prerequisite text is "PRE: CST 1100 & 1101".
- **Old sentence:** "CST 1204 (Database Systems Fundamentals) requires CST 1100 (Intro to Computer Systems)."
- **New sentence:** "CST 1204 (Database Systems Fundamentals) requires CST 1100 (Intro to Computer Systems) and CST 1101 (Problem Solving Comp. Program); catalog text: “PRE: CST 1100 & 1101”."
- **Reason:** source wins: the catalog record, found by the gold check. `gold_sources` is unchanged.
- **Made after reading the catalog record, not after reading any run's score.** It is not tuning: no retrieval, prompt or threshold changed and no run was repeated. Retrieval metrics cannot change. Only q40's answer-level verdicts (correctness, faithfulness) could change when a run is judged again. Old result files keep the verdicts they got under the old gold.

## Two-course questions (step 2): the 4b definitions M2 and R1 restated for q42's new route (Oct 13, 2026)
Written before any code of this step. The 4b definitions (`docs/step4b-plan.md`) read: **M2** = control (CTRL) questions answered by the chain node, each id listed; a control question the classifier calls `prerequisite` but whose extraction fails (two codes, no code) is not counted in M2. **R1** = q87 is not answered by the chain node in 3 of 3 runs, and M2 lists at most 1 other id (q21, a one-code prerequisite question without the `chain` tag).

Why they must change: with up to three codes accepted, q42 ("What are the prerequisites for MAT 1190CO, and how are they different from MAT 1190?", two codes, intent `prerequisite`, no `chain` tag) is no longer a failed extraction. It goes to the chain node on purpose, so under the old M2 it would count as a wrong catch.

Restated for the run of this step (the 4b results themselves stay as measured; they are the record of the old route):
- **M2** is unchanged in wording: CTRL questions answered by the chain node, each id listed. CTRL still means every dev question that is not in CH. **CH** is still "dev questions tagged `chain` whose type is not `unanswerable`"; with the eight questions of 2026-10-13 it is q22 q39 q40 q76 q77 q79 q81 q85 **q93 q94** (ten), so M1 expects 10 of 10 and M3 (two or more gold catalog sources) adds q93 and q94.
- **R1** becomes: q87 is not answered by the chain node in any run, and M2 lists **at most the two ids q21 and q42** and nothing else. q42 is expected (not merely allowed) to be answered by the chain node; if it falls through, that is reported as a miss, not as a pass.
- "Fall through" now means: no code, a code that is not a record and not an unambiguous title, or **more than three codes**. Two or three codes are not a fall-through any more.
- q42's judged result is compared before (4b runs: answered by retrieve and judged correct) and after (the chain node); the combined answer shows both catalog texts verbatim, which should satisfy its gold, but that is measured, not assumed.

### Step 2 (two-course questions): the keep rule, pre-registered before any code (Oct 13, 2026)
**What changes.** `extract_course` accepts 2 or 3 distinct course codes (order written, repeats removed). One code behaves exactly as today. More than 3 codes, a title together with codes, two titles, and no code still fall through to retrieval. One combined walk with one shared cap of 15 courses with records and the usual depth limit; the asked courses are reserved first, so a long first chain never pushes an asked course out. The code renderer writes one section per asked course, in the order asked: a heading "Prerequisites for CODE", then that course's blocks exactly as in step 1, numbered [1], [2] ... across the whole answer (the numbers match the sources). A course reached from two asked courses is shown once, in the first asked course's section; the later section says "CODE is already shown above." for each such course. An asked course already shown in an earlier section gets only that sentence. The lead line is "Here are the prerequisites for A and B, from the catalog:" (three: "A, B and C"). The question "how are they different?" is not answered by code; the quoted texts stand next to each other.

**An unknown code among several.** The asked code keeps its own section, which says "There is no catalog record for CODE in the four departments (CST, Math, EET, Dental Hygiene)." The other asked courses are still walked and shown. If every asked code is unknown, the answer is the existing abstention (`chain_no_record`, contact only for a named department), written for all codes.

**No new switch.** The change sits behind the two existing ones. `router.chain: off` sends everything to retrieval as before. With `router.chain_render: model` (the rollback to the model-written 4b answer), two- and three-code questions fall through to retrieval exactly as in 4b, because there is no model path for several courses. A catalog text that is unsafe as markdown (`ChainRenderError`) also falls through to retrieval for several courses. Single-course behaviour stays unchanged by construction (one code takes the old walk and the old renderer; K2 proves it).

**Keep rule.** All of K1 to K4 must hold (deterministic, no model call). J1 is for a later paid run and is stated now but not run.
- **K1** Unit tests over the walk and the renderer for a fixed set of two- and three-code combinations drawn from the 197 course chains, including a pair that shares a course (CST 1204 and CST 2403 share CST 1101) and a pair where one course names the other (CST 3504 names CST 1204; corrected in place on 2026-10-14: the first version said CST 3601 names CST 2301, which names CST 1204, but CST 3601's text names CST 3513, CST 2301 and CET 3640, and CST 2301's text is unparsed shorthand; see "three details settled" below): (1) every course of the union appears exactly once; (2) the asked courses appear in the order asked, each with its heading; (3) a shared course is in the first section only and the later section has the fixed sentence; (4) at most 15 courses with records in all, and anything cut is named exactly as the walk reports it; (5) every verbatim string unchanged, citation numbers match the sources, no word "chain", no "Level", output identical on a second call; (6) four codes fall through, titles alone never trigger the several-course path; (7) cross-listed codes (EET 3672 / CET 3672 / MECH 3672) stay separate; (8) an unknown code among several shows the sentence above and the others are still walked; all unknown abstains.
- **K2** For every one of the 197 courses, the answer to a one-code question is byte-identical to the renderer as it stood at the end of C1 and C2 (commit `f6cdbdc`): the SHA-256 of each text is stored in `tests/fixtures/chain_single_render_sha256.json`, generated from `f6cdbdc` before any code of this step. This includes every question that went to the chain node with one code in the stored dev runs (`4b-run1..3`, `chain-code-run1..2`; the test prints them). No model call.
- **K3** Routing, checked from the STORED classifier outputs (`router.intent`) of the past dev runs, with no new model call: a question with 2 or 3 codes goes to the chain node if and only if the stored intent is `prerequisite`; a question with more than 3 codes goes to retrieval; no stored question with 0 or 1 code changes route. (q42 is the one stored question whose route is expected to change.)
- **K4** q42, q93 and q94, given the intent `prerequisite`, go to the chain node (for q93 and q94 the classifier's own output is not known until the paid run, so this is a statement about the node), and the sources received contain every gold source: q42 `catalog:MAT 1190CO`, `catalog:MAT 1190`; q93 `catalog:CST 1204`, `catalog:CST 2403`; q94 `catalog:CST 3601`, `catalog:CST 1204`.
- **J1 (later paid run, dev only, not run now)** CH (q22 q39 q40 q76 q77 q79 q81 q85 q93 q94) plus q42, q21 and the controls q83 and q87, `--chain-render code`, two runs (the second is the second judge pass, as in step 1). Holds if: M1 10 of 10 in both runs; R1 as restated above (q87 never; M2 only q21 and q42); M3 at least 0.80 in both runs with q93 and q94 counted; the eight earlier CH answers byte-identical to the step 1 code runs (K2 says they must be); q93 and q94 judged faithful ("yes") in both runs and not "incorrect". If q42 is judged incorrect in either run, J1 fails; partial is reported only. After the run, the owner is shown q42's actual answer text before the keep decision. **Reported, not a rule (beyond the q42 sentence above):** q42 before (4b: retrieval, judged correct) and after; prediction written now: correctness may drop to "partial" because the code answer quotes both texts but does not write the difference sentence of its gold.

**Tests of the page.** The page tests get the new section heading and the "already shown above" and "no catalog record" sentences from a fixture written by the Python renderer, as for step 1.

### Step 2: three details settled while building (Oct 13, 2026; before any run, no rule weakened)
1. **The "one names the other" pair is CST 3504 and CST 1204 only.** The keep rule above also said CST 3601 names CST 2301, which names CST 1204. That was wrong: the catalog text of CST 2301 is the shorthand `PRE_CST1201_CST1204`, which the walk by rule does not read (UNPARSED, shown verbatim). The test uses CST 3504 / CST 1204 in both orders.
2. **A later section may go on from a course where an earlier section stopped at the depth limit.** Found by K1 (1) (the union of the single walks): a course that sits at level 4 in the first asked course's chain can be at level 2 in the second's. Without a rule, its prerequisites would be missing from the combined answer although a single question about the second course shows them. The course stays in the first section (shown once); its prerequisites are shown in the section that reached it nearer, and the "list stops" sentence for it is dropped.
3. **Cross-listed codes.** EET 3672 / CET 3672 / MECH 3672: only EET 3672 is in the four departments' records here, so the other two are "no catalog record" and are never mapped onto it (tested). The never-merged test also runs on CST 1204 and CST 2304, two records that share one description.

## Step 5b: formatting rule for multi-date retrieval answers, pre-registered (Oct 14, 2026; before any 5b paid run, nothing built)

Source: `docs/chain-layout-plan.md`, item 5, scope update of 2026-10-13. One change: a line in the answer prompt asking for a short bullet list, one per line, when the sources give several dates, tiers or amounts, with the sentence before the list kept to one line. It sits behind `answer.format_rule: off | on`, **default `off`** until the rule below passes. Retrieval-route answers only; the calendar and chain routes are written by code and untouched.

**Note on the evidence.** The judge scored the run-on q13 answer ("When is my tuition bill due this fall?") as **correct**. So the judge cannot show an improvement from the layout; the layout part of this change rests on the deterministic checks F1 to F3, which the owner can read, and F4 and F5 only guard against harm.

**Keep rule (all must hold; measured on dev only; test split untouched):**
- **F1** Over every dev retrieval answer whose cited chunk holds three or more dates in a table or list, the answer has at least three bullet lines that each contain a date, and no date of the source is missing.
- **F2** No retrieval answer of the other kind (one fact) becomes a list of more than one bullet.
- **F3** The condition that explains the tiers ("depends on when you first registered") is still in the text.
- **F4** Judged correctness and faithfulness on the retrieval-route dev questions, mean of three runs, not lower than the baseline arm minus 0.03 (the tolerance of rule R5 of 4b).
- **F5** Abstention accuracy and wrongly-abstained not worse.
- **F6** Retrieval metrics unchanged (holds by construction: the prompt acts after retrieval).

**Design of the measurement.** Two arms on the current code: the old prompt (`off`) as the baseline and the new prompt (`on`). The earlier 4b runs are **not** reused as the baseline. Three judged passes per arm, six in all.

**Cost (estimate, stated before any paid call).** About 42 retrieval-route questions at about $0.0046 each, about $0.19 per judged pass, **about $1.2 for the three before and three after passes**. The tool's dry-run figure (an upper bound) is printed before any paid call. The owner approves the spend.

## Step 2 (two- and three-course questions): KEEP (owner, Oct 14, 2026)

The owner read the J1 results (`docs/chain-layout-results.md`, commit `b6731f2`) and decided to **keep** step 2. There is no default to flip: `router.chain` and `router.chain_render` already carry it.

**Clarification of one J1 condition, decided after reading the results; no threshold or condition was changed.** J1 says the eight earlier CH answers must be "byte-identical to the step 1 code runs (K2 says they must be)". This is read as K2 defines it: identical, by SHA-256, to the renderer at `f6cdbdc` (`tests/fixtures/chain_single_render_sha256.json`). The step 1 runs (`chain-code-run1/2`) predate C1 and contain the word "chain", so a literal text comparison cannot hold. Result: 8 of 8 in both runs.

**Known limit: q42.** Judged "partial" in both runs: the answer quotes both courses' catalog texts but does not write the difference between them, as predicted before the run. Not "incorrect", so J1 held. Whether code should write a comparison sentence is not decided and not planned.

**Judge noise, not an answer fault.** In run 1 the judge gave q42 faithfulness "no" because it claimed the MAT 1275 no-credit note belongs only to MAT 1190; the answer quotes each course's own text unchanged. The same text got "yes" in run 2. Likewise q22 (identical text: correct/yes, then partial/no) and q21 (partial, then correct).

## Step 3a: calendar layout, keep rule pre-registered (Oct 14, 2026; before any code)

Source: `docs/chain-layout-plan.md`, item 5, option A (owner approved the build on 2026-10-14). Code only, **no prompt change, no model call in the rule, no new switch**: the calendar renderer (`src/cta/graph/render.py`) is the only code that writes a calendar answer, and its old layout (one run-on sentence per row, the long provenance clause repeated on every row) is the thing being replaced. The old layout stays in git history and in milestone 1; there is no fallback switch because the rows, their order and their citation numbers do not change (check 6), so a switch would guard nothing. Where the plan's six checks said "keep provenance inline or in the line below", the choice made here is the line below.

**New layout.**
- A **row** is one line: the date in bold, a colon, the event, `[n]`, and `(applies to: ...)` after `[n]` when the row has it: `**Thursday, September 3, 2026**: Last day to add a course. [1]`. With two or more rows each is a "- " bullet; a single row is a plain paragraph.
- A **TBA row**: `Event: not announced yet [n] Contact the Registrar: <contact>.` (no date, no bold).
- **One provenance line per calendar** (term, PDF file name, last-updated date), after that calendar's rows, in a paragraph of its own: `From the Fall 2026 calendar (fall_2026.pdf, last updated 2026-09-15). The calendar can change.` Rows are grouped by calendar (groups in order of the earliest date), sorted by date then id inside a group; `[n]` numbers follow the displayed order.
- The "Assuming the current term, X." line is its own paragraph above the rows.
- The **source chunk** each row sends to the judge and the "How this was found" panel keeps the full old sentence with its provenance (so the judge sees the provenance the answer states).
- The words "chain" and "Level" appear nowhere in these texts.

**Keep rule.** All must hold; tests are deterministic and free, no model call.
1. Every returned row's weekday-and-date text is exactly what `date_in_words` writes for it, and the rows are the same rows in the same order (by date, then id; groups by calendar).
2. Each row's `[n]` is unique and its source (by position) is that row.
3. The provenance line appears once per calendar, its term, file name and last-updated date equal the rows' fields, and the text "The calendar can change." is in every provenance line.
4. A TBA row says "not announced yet", has no date and keeps the Registrar contact line.
5. A one-row answer keeps its provenance (the line below); a two-term answer has two provenance lines, each after its own rows.
6. **Calendar-only scoring identical on all stored dev runs:** for every stored dev run with calendar-route answers (`4b-run1..3`, `router-run1..3`, `router2-run1..3`), rendering the stored selected row ids returns exactly those ids in the stored order, so the row-id scoring (v2) cannot change; the test also runs the v2 scorer on the re-rendered ids and expects the stored verdicts.
7. **No change to any non-calendar answer, checked by hash:** the 197 single-course chain hashes (K2, `tests/fixtures/chain_single_render_sha256.json`) still pass; the hash of `abstain_text` for fixed inputs and of the unsupported-term and selector-failed abstentions is unchanged; and the code commit touches `render.py` (and its tests, one web test and fixtures) and no other source file.
8. **Page:** the new text, written by the Python renderer into fixtures, parses on the page into bold date, `[n]` citation links, bullets and the provenance paragraph.
9. Ruff, pytest, `python -m cta.validate`, typecheck, `next build` and the node tests pass.

**Live check (dev, allowed cost up to $0.02):** the real page in headless Chrome, "When does Winter 2027 end?" and "When does the Winter 2027 session start and end?" (q95), at 390 px and 1280 px, light and dark. The judged effect on calendar answers that are scored by text (q09, q10, q30 ...) is not measured by this rule; the next judged dev run will include them.
