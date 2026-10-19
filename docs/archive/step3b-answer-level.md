# Answer-level comparison: reranker off against pool_a

## Metrics, mean (min to max) over the 3 runs of each arm

| metric | OFF | ON |
|---|---|---|
| correct share | 0.628 (0.577 to 0.654) | 0.692 (0.654 to 0.731) |
| partial share | 0.269 (0.231 to 0.308) | 0.269 (0.231 to 0.308) |
| incorrect share | 0.103 (0.077 to 0.115) | 0.038 (0.038 to 0.038) |
| faithfulness yes share | 0.910 (0.885 to 0.962) | 0.923 (0.885 to 0.962) |
| abstention accuracy | 1.000 (1.000 to 1.000) | 1.000 (1.000 to 1.000) |
| wrongly abstained (count per run) | 3.000 (3.000 to 3.000) | 3.000 (3.000 to 3.000) |
| citation rate | 1.000 (1.000 to 1.000) | 1.000 (1.000 to 1.000) |
| invalid citations (per run) | 0.000 (0.000 to 0.000) | 0.000 (0.000 to 0.000) |
| NO ADVICE correct share | 1.000 (1.000 to 1.000) | 1.000 (1.000 to 1.000) |

## Latency per request in ms: median / p95, mean over the runs

| part | OFF | ON |
|---|---|---|
| total | 1202 / 2363 | 3020 / 4783 |
| search | 13 / 15 | 14 / 16 |
| rerank | - | 1731 / 3276 |
| answer | 1325 / 2483 | 1341 / 2809 |

## Cost per request in USD (mean over the runs)

| part | OFF | ON |
|---|---|---|
| answers | 0.00017 | 0.00017 |
| rerank | 0.00000 | 0.00051 |
| judge | 0.00396 | 0.00406 |

## Failure labels per run (count)

- OFF run 1 (`baseline-dev-60-v3`): {'generation error': 3, 'not supported yet': 7, 'not supported yet (chained prerequisite)': 3, 'ranking miss': 1, 'retrieval miss': 2}
- OFF run 2 (`off-run2`): {'generation error': 3, 'not supported yet': 7, 'not supported yet (chained prerequisite)': 3, 'ranking miss': 1, 'retrieval miss': 4}
- OFF run 3 (`off-run3`): {'generation error': 2, 'not supported yet': 7, 'not supported yet (chained prerequisite)': 3, 'ranking miss': 1, 'retrieval miss': 3}
- ON run 1 (`on-run1`): {'generation error': 2, 'not supported yet': 7, 'not supported yet (chained prerequisite)': 3, 'retrieval miss': 2}
- ON run 2 (`on-run2`): {'generation error': 4, 'not supported yet': 7, 'not supported yet (chained prerequisite)': 3, 'retrieval miss': 2}
- ON run 3 (`on-run3`): {'generation error': 2, 'not supported yet': 7, 'not supported yet (chained prerequisite)': 3, 'retrieval miss': 3}

## The rule (docs/experiments.md, step 3b), on the arm means

- PASS  a: correct share: +0.064 (limit -0.038)
- PASS  b: faithfulness yes share: +0.013 (must not fall)
- PASS  c: abstention: accuracy +0.000, wrongly abstained +0.00 per run
- PASS  d: citation validity: citation rate +0.000, invalid citations +0.00 per run

**Verdict by the rule: KEEP pool_a.**

## Per question: verdict in each run (c = correct, p = partial, i = incorrect; y = faithful yes, ~ = partly, n = no; - = not judged)

| id | type | OFF corr | ON corr | OFF faith | ON faith | change |
|---|---|---|---|---|---|---|
| q01 | lookup | c p p | c p p | y y y | y y ~ | correctness: unstable; faithfulness: unstable |
| q03 | lookup | c c c | c c c | y y y | y y y |  |
| q04 | lookup | c c c | c c c | y y y | y y y |  |
| q05 | lookup | c c c | c c c | y y y | y y y |  |
| q06 | lookup | c c c | p c p | y y y | y y y | correctness: unstable (leaning worse) |
| q08 | lookup | c c c | c c c | y y y | y y y |  |
| q09 | time_sensitive | c c c | c c c | y y y | y y y |  |
| q12 | time_sensitive | i i i | i i i | y y y | y y y |  |
| q13 | time_sensitive | c c c | c c c | y y y | y y y |  |
| q14 | time_sensitive | c c c | c c c | y y y | y y y |  |
| q15 | time_sensitive | i i i | i i i | y y y | n n n | faithfulness: real worse |
| q16 | multi_chunk | c p c | c c c | y y y | y y y | correctness: unstable |
| q18 | multi_chunk | c c c | c p c | y y y | y y y | correctness: unstable |
| q19 | multi_chunk | c c c | c c c | y y y | y y y |  |
| q21 | lookup | c c c | c c c | y y y | y y y |  |
| q22 | multi_chunk | p p p | p p p | n y n | y n n | faithfulness: unstable |
| q24 | ambiguous | - - - | - - - | - - - | - - - |  |
| q27 | unanswerable | c c c | c c c | - - - | - - - |  |
| q28 | unanswerable | c c c | c c c | - - - | - - - |  |
| q30 | unanswerable | c c c | c c c | - - - | - - - |  |
| q31 | time_sensitive | i i i | i i i | y y y | y y y |  |
| q33 | time_sensitive | i i i | i i i | y y n | n n n | faithfulness: unstable (leaning worse) |
| q34 | unanswerable | c c c | c c c | - - - | - - - |  |
| q36 | time_sensitive | i i i | i i i | y y y | y n y | faithfulness: unstable |
| q37 | time_sensitive | i i i | i i i | y y y | y y y |  |
| q39 | multi_chunk | p p p | p p p | y y y | y y y |  |
| q40 | multi_chunk | p p p | p p p | n n n | y y y | faithfulness: real better |
| q42 | lookup | p p p | p p p | y y y | y y y |  |
| q44 | unanswerable | c c c | c c c | - - - | - - - |  |
| q45 | unanswerable | c c c | c c c | - - - | - - - |  |
| q47 | unanswerable | c c c | c c c | - - - | - - - |  |
| q49 | ambiguous | - - - | - - - | - - - | - - - |  |
| q51 | multi_chunk | c c c | c c c | y y y | y y y |  |
| q52 | lookup | i i i | c c c | n y n | y y y | correctness: real better; faithfulness: unstable (leaning better) |
| q53 | lookup | c c c | c c c | y y y | y y y |  |
| q54 | lookup | p p p | c p c | y y y | y y y | correctness: unstable (leaning better) |
| q56 | lookup | p i i | c c c | y y y | y y y | correctness: unstable (leaning better) |
| q57 | lookup | c c c | c c c | y y y | y y y |  |
| q58 | lookup | c c c | c c c | y y y | y y y |  |
| q59 | multi_chunk | p p c | p p p | y y y | y y y | correctness: unstable |

Real changes: ['q15', 'q40', 'q52']
Unstable (not counted): ['q01', 'q06', 'q16', 'q18', 'q22', 'q33', 'q36', 'q52', 'q54', 'q56', 'q59']

## Judge noise: `on-run1` judged twice, 1 of 80 correctness and faithfulness verdicts differ

- q15 faithfulness: no -> partly


## Counts per run (26 judged normal-gold questions)

| run | correct / partial / incorrect | faithful yes / partly / no | median total latency (ms) |
|---|---|---|---|
| off-run1 = `baseline-dev-60-v3` (stored answers, v3) | 17 / 7 / 2 | 23 / 0 / 3 | 1164 |
| off-run2 | 15 / 8 / 3 | 25 / 0 / 1 | 1261 |
| off-run3 | 17 / 6 / 3 | 23 / 0 / 3 | 1151 |
| on-run1 | 19 / 6 / 1 | 25 / 0 / 1 | 3019 |
| on-run2 | 17 / 8 / 1 | 24 / 0 / 2 | 3103 |
| on-run3 | 18 / 7 / 1 | 23 / 1 / 2 | 2885 |

## Sources the answerer received (first 5 chunks, from the stored run `on-run1`, against `off-run2`)

- **q06** (worsened for retrieval). OFF: CST overview #4, **CST degrees #2**, CST home #1, CST overview #2, CST BTECH program #2. ON: CST overview #4, CST home #1, CST student-resources #9 (Student FAQs), **CST degrees #2**, CST BTECH program #2.
  The degrees page moved from 2nd to 4th; it is still in the five, but the answer was graded partial in 2 of 3 ON runs against correct in 3 of 3 OFF runs.
- **q56** (7 to 1 in retrieval). OFF: EET overview #2, EET 2000 course, EET overview #3, EET chair page, EET BTECH program. ON: **EET student-resources #14 (Internship/Scholarship)**, EET 2000 course, EET overview #2, overview #3, chair page.
  The gold page entered the five; correctness went from partial/incorrect/incorrect to correct in all 3 ON runs.
- **q52** (miss to 1). OFF: Dental FAQ #8, apply #1, advisement #1, AAS program #10, FAQ #16. ON: **Dental FAQ #12 ("Is there a five...")**, FAQ #16, FAQ #8, apply #1, advisement #1. Correctness incorrect in 3 of 3 OFF runs, correct in 3 of 3 ON runs.

## The questions asked about

- **q15**: retrieval miss in all six runs (the gold `student-hours` page is in no pool). Correctness incorrect in all six. **Faithfulness fell from "yes" in all OFF runs to "no" in all ON runs** (real change, worse). The reranker put the
  virtual-advisors #15 chunk (a Summer 2026 advisement schedule) first; the answer says no student hours are listed; the judge says source 1 contradicts that. In `judge-repeat` this one verdict moved from "no" to "partly".
- **q06**: leaning worse (OFF correct x3; ON partial, correct, partial); the retrieval rank drop (2 to 4) shows up in the answers.
- **q22**: partial in all six; faithfulness unstable inside both arms (OFF no, yes, no; ON yes, no, no): judge and answer noise on a chained-prerequisite question, no change attributable to the reranker.
- **q40**: partial in all six; faithfulness **"no" in 3 of 3 OFF runs and "yes" in 3 of 3 ON runs** (real change, better). Under rubric v3 the stored OFF answer is still "no" (see `docs/judge-check-v3.md`); with the reranker the sources shown
  to the answerer differ and the judge accepts the answer. I did not check the sources by hand.
- **q42**: partial in all six, no change.
- **q54**: OFF partial x3; ON correct, partial, correct: unstable, leaning better.
- **q59**: OFF partial, partial, correct; ON partial x3: unstable.
