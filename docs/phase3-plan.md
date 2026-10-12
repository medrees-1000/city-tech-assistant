# Phase 3 plan: improve the baseline, one measured change at a time

**Where we are (2026-10-12):** step 0 is done (60 questions, comparison file `eval/results/baseline-dev-60.json`). Steps 1 (hybrid, ts_rank), 1b (hybrid, BM25) and 2a (department filter) were
all run and REJECTED by their pre-registered rules. **Step 3 (LLM reranker) was run retrieval-only on dev: both pools met the rule and Pool A (vector top 20 reranked, MRR 0.789 to 0.925, recall@5 0.775 to 0.897,
7 questions better, q06 worse) was kept; the default is now `retrieval.rerank: pool_a`** (`CTA_RERANK=off` gives the old behaviour). Step 2b (term filter) was not built: on dev, 13 of 40 questions name a term but only 3 are
retrieval-scored and all 3 already rank 1 (`docs/experiments.md`, step 3 pre-registration). The hybrid modes, BM25, the department filter and `config/departments.yaml` remain in the code, off. Judge rubric is v3 (first used when the
stored `baseline-dev-60` answers are re-judged with the next answer-level run). **Step 3b (answer-level check, 3 runs per arm, rubric v3) passed the pre-registered rule: pool_a stays the default** (correct share 0.628 to 0.692, nothing worse on faithfulness, abstention, citations; cost +$0.0005 and +1.7 s median per request; `docs/experiments.md`, `docs/step3b-answer-level.md`). **Step 4a-0 and 4a-1 done:** 14 owner-approved calendar questions merged (dev 48, test 26; the 30 retrieval-scored dev questions are unchanged; `docs/decisions.md`). **Next:** 4a, then 4b, 4c, and the first test-split milestone run with `--final` (after step 3, per the protocol).

**Step 3 and 3b results (kept):** the reranker (`retrieval.rerank: pool_a`, vector top 20 reranked by `gpt-6-luna`, top 5 to the answerer) improved retrieval on dev (MRR 0.789 to 0.925, recall@5 0.775 to 0.897; q06 got worse) and passed the answer-level rule. Means of 3 runs per arm under rubric v3: correct share 0.628 to 0.692, incorrect 0.103 to 0.038, faithfulness yes 0.910 to 0.923; abstention, citations and advice unchanged. Cost +$0.0005 per request. **Latency, a follow-up for step 6 (guardrails and caching):** total latency per request, median 1.2 s to 3.0 s and p95 2.4 s to 4.8 s (the reranker call is about 1.7 s median); a response cache (question, date, data version) and reranker score caching are the first things to evaluate there. **Open question:** under rubric v3 the q22 and q40 faithfulness verdicts did not change (both still "no") although v3 was written for them; this stands until the owner has hand-checked `docs/judge-check-v3.md`. Details: `docs/experiments.md` (experiments 3 and 3b), `docs/step3b-answer-level.md`. No test split has been run on the new questions.

Starting point: `docs/baseline-findings.md` (Phase 2: dev `eval/results/baseline.json`, test `eval/results/baseline-final.json`; Phase 3 comparison: `eval/results/baseline-dev-60.json`).
The baseline is vector-only search, k = 5, `gpt-6-luna`, judge `gpt-5.6-terra` with rubric v2, abstain threshold 0.59.

## Framework policy

- Retrieval, evaluation and the data pipeline stay hand-built. The owner must be able to explain every line.
- The router in step 4 is built with LangGraph. LangChain components (`ChatOpenAI`, tool calling) are allowed where they replace
  boilerplate. Each one gets a one-line reason in `docs/decisions.md` and its version is pinned in `pyproject.toml`.
- LangSmith tracing arrives in step 6, runs alongside `request_logs` (not instead of it), and sends only redacted text.

## Protocol (every experiment)

1. One change at a time, behind a config switch (default off = baseline behaviour). The baseline path must stay reproducible.
2. Measure on **dev** against the frozen baseline (`eval/results/baseline-dev-60.json`, the frozen system run on the grown dev set in step 0). Same
   judge, same rubric (v2), same `eval.today`. Retrieval-only changes are first measured with `run_retrieval` (no LLM cost).
3. Log the result in `docs/experiments.md`: what changed, the metric deltas (retrieval at k = 1, 3, 5, 10; correctness;
   faithfulness; abstention; citations), the cost and latency deltas, the questions that got better and the ones that got worse
   (the sets are small, so name them), and a **keep or reject** decision with the reason. A rejected experiment is still logged.
4. A change is kept only if it improves what it was meant to fix and does not make another metric worse by more than one question.
5. The test split is run once per milestone (after steps 3, 4 and 6) with `--final`, and never used to choose anything. A question
   that a decision was based on is not test.
6. Pin versions of new dependencies and say why each is needed.

## Experiments, in order, and the failures each should fix

Failures are those in `docs/baseline-findings.md`. "Should fix" is a hypothesis to test, not a result.

| Step | Change | Should fix |
|---|---|---|
| 0 (done) | Grow the eval set (about 30 owner-reviewed questions: calendar, chained prerequisites, cross-listed courses, abstain and advice cases, ambiguous, more department lookups), then re-run the frozen baseline on the new set. | Nothing: it makes the measurements meaningful. Dev has 20 questions and test 10, and only 17 and 5 of them are retrieval-scored. |
| 1, 1b (done: both rejected) | Hybrid search (1: Postgres ts_rank; 1b: BM25): fill `chunks.tsv`, full-text search, reciprocal rank fusion with the vector ranking. | q15 (the page says "ETET", the question says "Electrical Engineering Technology"), q07 (department-name words); course-code questions that rank 2 (q21, q22). |
| 2 (2a done: rejected; 2b not worth building on dev: no term-naming scored question ranks below 1) | Department and term filters (soft term rule from `docs/decisions.md`; a department filter only when the question names one). | q15 (department and the "Fall 2024" label that must be stated), q07 (overview chunks outrank the degrees page). |
| 3 (done: Pool A kept) | Reranker over the top 20 to 30. | q07 (gold at ranks 4 and 8) and the rank-2 and rank-3 cases (q05, q06, q21, q22). It cannot help q01 or q15, whose gold chunk is not retrieved. |
| 4a-0 (this step) | Calendar question candidates for owner review: about 14 new calendar questions (`docs/calendar-candidates.md`, written by `scripts/make_calendar_candidates.py` from `calendar_events.json`). Nothing is added to `eval/questions.jsonl` until the owner approves. | Nothing: it makes step 4a measurable (the 10 existing calendar-gold questions are mostly "not supported yet"). |
| 4a | Calendar tool inside a minimal LangGraph router (calendar lookup, else retrieve and answer, else abstain). Adds `langgraph` (reason in `docs/decisions.md`). Resolves the term from the question or from `eval.today`; answers from the calendar table, not vector search. | Calendar: q11, q12 and the calendar questions (q31, q33, q36, q37 and the 4a-0 additions). |
| 4b | Prerequisite chain tool (follows the rule IDs through the course records). | Chain: q22, q39, q40 and the chain questions. |
| 4c | Contact lookup tool (office and department contacts from the contact records). | q15 (abstain with the department contact) and the abstain-with-contact cases. |
| 5 | Answer style: completeness (answer all parts the question asks) and clarifying questions. | q23, q24 (CLARIFY), partial answers such as q01 and q07 once the evidence is retrieved. Needs the sources in front of the model first, so after step 3 or 4. |
| 6 | Guardrails (input scope, personal data, indirect injection, output citation check), LangSmith tracing alongside `request_logs`, caching (embedding cache exists; exact response cache keyed by question + date + data version; no semantic cache), and the HNSW index decision. | No failure in the baseline: 0 invalid citations so far. These protect the product, and the HNSW decision depends on row count and latency (619 rows now, exact scan is fast). |

Not on the roadmap yet but worth a decision after step 3: retrieving the neighbouring sections of a top page (q01: one section of
an otherwise retrieved page was missed).

## Deliberately not changed

- The embedding model, chunking and chunk text, the data pipeline, and the 619 chunks (a retrieval experiment may add a column such
  as `tsv`, never edit the text without its own experiment and re-embed).
- The judge model, rubric v2 and the failure-label rules, so results stay comparable. The judge's faithfulness grade is known to be
  lenient; that is stated in every results table, not tuned away.
- The existing 30 questions, their splits and gold answers. New questions are added after the owner's review and get ids from
  q31 on. The old test split was run once and its questions have been seen, so it is a record, not a fresh test; the new test
  questions are held out until the first milestone.
- Sources and scope (the four departments, the central offices, Fall 2026 / Winter 2027 / Spring 2027). No login pages, no student data.
- Models and prices in `config/models.yaml`, except as an experiment says.

## Step 0, in detail

1. This plan. 2. `scripts/make_eval_candidates.py` writes `docs/eval-candidates.md`: about 30 candidate questions chosen from the data
and a fixed list of categories, never from baseline results, each with a **draft** gold answer built from the source text, or `TODO`.
3. The owner reviews, edits and approves; only then are questions added to `eval/questions.jsonl` (a separate step). 4. Re-run the
frozen baseline on the grown dev set (`baseline-dev-2`) and record it in `docs/experiments.md`. The baseline is run on the grown
test set only at the first milestone, together with the changed system, so the new test questions stay unseen until then.
