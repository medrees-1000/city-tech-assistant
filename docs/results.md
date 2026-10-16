# Results (all numbers)

Every table below is printed by `python3 scripts/readme_numbers.py` from the committed files in `eval/results/` (`final-run.json`, `final-run-pass2.json`, `final-run-owner-grades.json`, `final-config-dev.json`, `baseline-dev-60-v3.json`, `casual-b0.json`). The script does not read any question file. The final test run (`final-run`) was done once with the code frozen at `final-run-frozen`; the test split had also been run three times in milestone 1 and before, so it is not untouched (see `docs/decisions.md`, "Corrections after review"); `docs/decisions.md` ("Final run" and "Final run, addendum") has the rules written before the run. The two owner grades (q50 correct, q74 partial) were given after seeing the results and are labelled that way everywhere.

Reading notes:
- "Normal-gold questions" are the questions whose gold answer is a fact from the sources. Abstention, clarify, NO ADVICE and calendar-only questions are scored by rules and listed separately.
- The dev set is the set I tuned on. It holds 91 questions, 20 of them casual-wording questions (q104 to q123) that I added late, after seeing that casual wording failed.
- The Phase 2 baseline was run on the 40 dev questions that existed then (vector search only, no router, no reranker, judge rubric v3). The second row of table (b) is the final configuration on the same 40 questions.
- Questions answered by the router's code paths (calendar table, prerequisite chain) are included in the dev and test numbers. Retrieval metrics (recall, precision, hit rate, MRR) only cover the questions that have a section-level gold source.
- One test question moves a rate by about 8 points (13 normal-gold questions) or 3 points (31 questions).
- Dev run `final-config-dev` was made at commit `802f1d3` with the same config as the test run (the "dirty" flag in its file is only because this README's numbers script was being written at the time).

### (a) Final test run, 31 questions, code frozen at the tag final-run-frozen (final-run)

| Answer correctness (normal-gold questions) | n | correct | partial | incorrect |
|---|---|---|---|---|
| harness-only | 13 | 10 | 3 | 0 |
| with owner grades for q50, q74 (owner-graded after seeing results) | 15 | 11 | 4 | 0 |

- Faithfulness (judge says the answer is supported by its sources): 13 of 13
- Abstention on questions that must abstain: 7 of 7; wrongly abstained: 0 of 14
- Citation rate: 1.00 (n=23), invalid citations 0
- Retrieval on the 14 retrieval-scored questions: recall@5 0.738, precision@5 0.314, hit@5 0.857, MRR 0.811
- Cost of one request to the assistant (classifier, selector, reranker, answer call and query embedding; no judge): $0.00040
- Cost of the whole eval run including the judge: $0.081 ($0.0026 per request; answers $0.0123, judge $0.0684)
- Latency: median 2.3 s, p95 7.9 s
- Judge pass 2 (same judge, same rubric, answers re-judged): 13 of 14 questions agree on both verdicts; differs: q02 (the log stores the answer with public contact details redacted, so pass 2 saw redacted text)
- Judge cost pass 2: $0.0692

### (b) Development set (the set I tuned on)

| Run | n normal | correct | partial | incorrect | faithful | abstained when it must | wrongly abstained | hit@5 | MRR |
|---|---|---|---|---|---|---|---|---|---|
| Phase 2 baseline (40 dev questions, vector search only, rubric v3) | 26 | 17 (65%) | 7 | 2 | 23 of 26 | 5 of 5 | 3 of 28 | 77% | 0.68 |
| Final configuration, the same questions | 26 | 20 (77%) | 6 | 0 | 24 of 26 | 5 of 5 | 1 of 28 | 97% | 0.93 |
| Final configuration, all 91 dev questions | 52 | 34 (65%) | 7 | 11 | 48 of 52 | 12 of 12 | 12 of 57 | 95% | 0.87 |
| Final configuration, dev questions without the casual-wording group | 37 | 30 (81%) | 6 | 1 | 35 of 37 | 10 of 10 | 2 of 41 | 93% | 0.89 |

- Final dev run `final-config-dev`: cost of one request to the assistant $0.00053, median latency 2.9 s, p95 5.5 s
- Retrieval on its 59 scored questions: recall@5 0.854, precision@5 0.251, hit@5 0.949, MRR 0.873

### (c) Test against dev (final configuration)

| Set | n normal | correct | faithful | recall@5 | hit@5 | MRR | wrongly abstained |
|---|---|---|---|---|---|---|---|
| dev (the set I tuned on) | 52 | 34 (65%) | 48 of 52 | 0.85 | 0.95 | 0.87 | 12 of 57 |
| test (final run, code frozen) | 13 | 10 (77%) | 13 of 13 | 0.74 | 0.86 | 0.81 | 0 of 14 |
| dev without the casual-wording group | 37 | 30 (81%) | 35 of 37 | n/a | 0.93 | 0.89 | 2 of 41 |

### (d) Casual wording

- The casual group is the 20 dev questions tagged `casual` (q104 to q123), in `final-config-dev`.
- Fact questions (normal gold, n=15): correct 4, partial 1, incorrect 10; refused 10 of 15
- The other 5 casual questions are scored by rule (clarify, no advice, calendar-only, must-abstain): 5 of 5 correct
- All 20 together: 9 of 20 pass
- Baseline of the casual round (`casual-b0`, run before q123 was added, 19 questions): 4 of 14 fact questions correct (29%)
- "Wrongly abstained" in the dev tables is the runner's term: abstained questions among the answerable set (fact questions plus the no-advice question), so its denominator is one larger than the fact-question count.

### (f) Cost and latency by route (whole request to the assistant, no judge)

| Route | requests (dev + test) | median cost | median latency (ms) |
|---|---|---|---|
| abstain | 10 | $0.00008 | 1950 |
| advice | 6 | $0.00092 | 6039 |
| calendar | 28 | $0.00049 | 2224 |
| calendar_fallthrough | 5 | $0.00097 | 3714 |
| chain | 19 | $0.00004 | 940 |
| clarify | 4 | $0.00004 | 904 |
| other | 50 | $0.00070 | 3874 |

## (e) What I tried that did not work

Each experiment had its keep rule written in `docs/decisions.md` or `docs/experiments.md` before the run. A rejected experiment stayed in the code only behind a switch that is off.

| Experiment | Rule (written first) | Result | Where |
|---|---|---|---|
| Stronger answer model (gpt-6-sol instead of gpt-6-luna) | B1: correct share must rise by at least 0.05 | 0.859 against 0.923, so the change was -0.064; about 5.5 times the cost per retrieval request ($0.0045 against $0.0008). Rejected. | `docs/model-experiment-results.md` |
| Formatting rule for multi-date answers, round 1 | F2 (no answer may change into a bullet list) | Six questions became bullet lists in every pass. Failed. | `docs/decisions.md`, "Step 5b closed" |
| Formatting rule, round 2 (narrower) | F2' (at most 3 answer-passes changed) and F4 (correct share at least 0.893) | 4 of 81 passes changed, correct share 0.859. Failed on both. | `docs/decisions.md`, "Step 5b closed" |
| Answering non-English questions in English from a translation (option 1) | R4: at least 4 of 5 languages pass 8 of 10 probes, no hard failure, at least 5 of 6 safety probes caught | Spanish 9, Arabic 8, Haitian Creole 7, Russian 8, Chinese 8 of 10; hard failures in Spanish, Haitian Creole and Chinese. Failed. The assistant now replies in English that it answers in English only (option 3). | `docs/decisions.md`, "Tester round 1b, Part 2" |
| Fallback query rewrite (E1) for casual questions that score under the cutoff | K1 to K6, with K2: every must-abstain question must still abstain | Failed twice. The first attempt could not reach the required share. After amendment A1 (also after a calendar fall-through), "Can I take a class at another college?" was answered in 3 of 3 K2-repeat runs, where it should not be. The switch stays off. | `docs/decisions.md`, "Casual round" and "AMENDMENT A1" |
| Lowering the 0.59 abstain cutoff | A sweep over 0.55 to 0.62 on stored dev results | No cutoff separates the out-of-scope question q45 (0.568) from a valid short tester question (0.576), so the cutoff stays and a near-miss reply was added instead. | `docs/cutoff-sweep.md` |
| Hybrid search (keyword plus vector, two versions) and a department filter on retrieval | pre-registered rules in `docs/experiments.md` | Hybrid search was rejected (the BM25 version narrowly, by the rule as written); the department filter was rejected (no effect). The code stays, switched off. | `docs/experiments.md`, experiments 1, 1b and 2a |

## Test failures in detail

| id | question (short) | what happened | category | already in known limits? |
|---|---|---|---|---|
| q07 | degrees of the EET department | AAS and BTech named, the Accelerator Science and Technology minor missing; two of the three gold chunks were not in the top 5 | retrieval miss | new in this form |
| q41 | steps before EET 4202 | the chain stopped at depth 4 (MAT 1475 to MAT 1375 not followed) | chain depth limit | yes (milestone 1) |
| q60 | what is the TAP waiver | right sources at ranks 1 and 2; the answer left out how to request it | partial answer | judged correct in the earlier milestone-1 run, so judge or generation variance is possible |
| q50 | how much tuition do I get back if I drop (owner-graded after seeing results: correct) | gave the Fall 2026 refund schedule with the term named; did not say other terms differ | harness could not grade it | harness limit |
| q74 | last day to drop in Fall 2026 (owner-graded after seeing results: partial) | gave the three grade-related rows; the four refund rows were left out by design (refund rows only when the question mentions a refund) | trade-off of the drop-family rule | yes, known limit 26 |

No test answer was unfaithful, no answerable question was refused, and no must-abstain question was answered.
