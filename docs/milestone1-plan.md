# Milestone 1: the first test-split run (`--final`), pre-registration

Written 2026-10-13 and committed before any test run. Owner decision (`docs/phase3-plan.md`): the first milestone runs right after step 4c-data, before steps 5 and 6. **There is no keep or reject rule and nothing to tune.** Results are reported and are never used to choose or change retrieval settings, prompts, thresholds, router rules, the contact table or the cues. A final milestone follows step 6. The test split is run once per configuration; the runner refuses a label that already exists, and if it refuses a second test run for any other reason I stop and report (no bypass).

## What is run (31 test questions, both configurations, same day)

Test split: 31 questions (lookup 4, time_sensitive 8, multi_chunk 7, ambiguous 3, unanswerable 9). The 10 original test questions (q02 q07 q10 q11 q17 q20 q23 q25 q26 q29) are in the stored `eval/results/baseline-final.json`; the other 21 were added later and have never been run.

| | OLD | NEW |
|---|---|---|
| code | HEAD (`a69d5cd` plus this plan) | the same commit |
| retrieval | vector, `retrieval.mode vector` | vector (default) |
| rerank | off | `pool_a` (default) |
| router | off | on, selector 2, chain on, contacts on (all defaults) |
| dept filter | off | off (default) |
| answer prompt, model, sampling, k, threshold | `gpt-6-luna`, temperature 0.1, top_p 0.3, k 5, threshold 0.59 | identical |
| judge | `gpt-5.6-terra`, rubric v3, temperature 0, reasoning none | identical |
| `eval.today` | 2026-10-11 | 2026-10-11 |
| calendar scoring | v2 (so both are scored by the same rule; OLD returns no calendar rows) | v2 |

Commands (output goes to log files; I do not open or print per-question test results until both runs have finished):

```
OLD: uv run python -m cta.eval.run_answers --split test --final --label ms1-old --router off --rerank off --chain off --contacts off --dept-filter off --mode vector --calendar-scoring 2 --budget 0.80 --budget-labels none --yes
NEW: uv run python -m cta.eval.run_answers --split test --final --label ms1-new --calendar-scoring 2 --budget 0.80 --budget-labels ms1-old --yes
```

NEW takes no override flag: it is every current default. The resolved NEW configuration and `git rev-parse HEAD` are printed in the report. The `answer.py` code differs from the frozen baseline (`08cc8df`) in 6 lines that do not change behaviour (cost property; the threshold reads `top_vector_similarity`, which equals the top-1 cosine in vector mode), so OLD is the baseline path. OLD differs from the stored `baseline-final` in the judge rubric (v3 now, v2 then) and in the 21 added questions.

**Judge passes: one.** The runner has no repeated or majority-vote judge pass on a fresh run (`judge-repeat` was a separate re-judge of stored answers). I build no new judge code, so each answer is judged once. Judge noise is therefore unmeasured here.

## Estimate (free) and cap

From the dev runs: NEW costs $0.0040 per question (4b-run1..3, answer + rerank + judge, all routes, one judge pass), OLD $0.0041 per question (`baseline-dev-60-v3`). For 31 questions: NEW about $0.12, OLD about $0.13, **total about $0.25** (a longer test answer or an abstain-heavy set moves it by tens of percent). Expected $0.25 to $0.60, hard cap **$0.80 for both runs together** (`--budget 0.80` with OLD's cost subtracted for NEW; a run refuses to start if its own estimate does not fit and stops by itself before the next question if the running cost would pass it). If the runner's estimate for either run is above the cap I stop and report.

## What is reported (counts, not only percentages)

With 31 questions one question moves a rate by about 3 points, and a single answer run is noisy (the dev runs of one arm differed by up to 2 questions). Nothing below is a significance test.

1. Retrieval on the retrieval-scored questions: recall@5, precision@5, hit rate, MRR (n stated).
2. Answer correctness and faithfulness on normal-gold questions, with the usual caveat that faithfulness is unreliable on "the sources do not state X" answers (`docs/step4-judge-results.md`).
3. Abstention accuracy, wrongly abstained.
4. Calendar-only questions under scoring v2, with every wrong row stated.
5. Chain questions q78 q80 q82 q84 q86: result and whether every gold source was among the sources the answerer received.
6. Cost and latency per route; breakdown by type (lookup, multi_chunk, time_sensitive, ambiguous, unanswerable).
7. OLD against NEW on the 31 common ids; OLD against the stored `baseline-final` on its 10 ids (q02 q07 q10 q11 q17 q20 q23 q25 q26 q29), for consistency only (rubric v2 against v3 noted).
8. **Contact check:** a table of every NEW test question that abstained: id, path, office added, line added. The owner judges whether the office is right; I give no pass or fail on it.
9. Every OLD and NEW failure with its failure label and the first line of the answer, grouped by type; each marked as a known limit already logged (q39 depth, q47/q49 style, judge false "no" on "sources do not state X") or as a new finding. No fixes are proposed or made.
