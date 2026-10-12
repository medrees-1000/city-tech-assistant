# Baseline findings (Phase 2)

Vector-only retrieval (exact cosine, k = 5 shown to the model), `gpt-6-luna` answers, `gpt-5.6-terra` judge with
rubric v2, abstain threshold 0.59. Prompt, threshold, k, models and rubric were frozen at commit `08cc8df` before the
test run (`docs/decisions.md`). Every number below is copied from `eval/results/baseline-dev-judge-v2.json` (dev) and
`eval/results/baseline-final.json` (test). Dev has 20 questions and test has 10, so **every group is tiny: read n,
not the decimals.** A difference between dev and test is not evidence of anything.

## Metrics

| Metric | Dev (20 questions) | Test (10 questions) |
|---|---|---|
| Questions scored for retrieval | n=17 | n=5 |
| Recall@1 / hit rate@1 | 0.549 / 0.706 (n=17) | 0.507 / 0.800 (n=5) |
| Recall@3 / hit rate@3 | 0.838 / 0.941 (n=17) | 0.613 / 0.800 (n=5) |
| Recall@5 / hit rate@5 | 0.838 / 0.941 (n=17) | 0.747 / 1.000 (n=5) |
| Recall@10 / hit rate@10 | 0.838 / 0.941 (n=17) | 0.933 / 1.000 (n=5) |
| Precision@5 | 0.235 (n=17) | 0.320 (n=5) |
| MRR | 0.814 (n=17) | 0.850 (n=5) |
| Correctness, normal gold | n=15: correct 0.80, partial 0.13, incorrect 0.07 | n=5: correct 0.60, partial 0.40, incorrect 0.00 |
| Faithfulness, normal gold | n=15: yes 1.00, partly 0.00, no 0.00 | n=5: yes 1.00, partly 0.00, no 0.00 |
| NO ADVICE gold, judged correct | n=1: correct 1.00 | n=0 |
| Abstention accuracy (ABSTAIN gold) | 1.0 (n=2) | 1.0 (n=3) |
| Wrongly abstained (answerable) | 0.062 (n=16) | 0.000 (n=5) |
| Citation rate / invalid citations | 1.0 (n=16) / 0 | 1.0 (n=5) / 0 |
| Judge failures | 0 | 0 |
| Cost per request (answer + judge) | $0.00436 (n=20) | $0.00279 (n=10) |
| Total cost of the run | $0.0871 | $0.0279 |
| Latency, total, median / p95 ms | 1179 / 2351 (n=20) | 1193 / 2277 (n=10) |
| Latency, chat call alone, median / p95 ms | 1201 / 2447 (n=18) | 1199 / 2266 (n=7) |
| Query-embedding cache hits | 20/20 | 10/10 |

Notes on the table:
- Retrieval is scored only on questions with a section or course gold source. Excluded on dev: q12 (calendar-only), q27, q28
  (unanswerable). Excluded on test: q11 (calendar-only), q23 (CLARIFY, no source), q25, q26, q29 (unanswerable).
- "Normal gold" means a question judged against a written gold answer. ABSTAIN, CLARIFY and NO ADVICE questions and the
  calendar-only question are reported on their own lines or in the failure table, not inside the correctness share.
- Cache hits: on test, the dry run had already embedded the questions, so the real run found them all in the cache. On dev
  they were cached by earlier steps. **No embedding time is in any latency number.** Judge time is not in the latency.
- Cost per request counts the answer and the judge. The answer cost is an upper bound (no cached-input discount).
- Dev was used to choose the abstain threshold and, after the owner's check, the rubric (v1 to v2). Dev numbers are therefore a little
  optimistic. Test was run once, after the freeze.

## How far to trust the judge

The owner checked 8 dev verdicts by hand (`docs/judge-check.md`). Rubric v2 agrees with the owner on correctness 7 of 8 and on
faithfulness 7 of 8 (v1: 6 of 8 and 7 of 8). The two disagreements left: q15 (judge incorrect, owner partial) and q03 faithfulness
(judge yes, owner partly: the answer's "No." goes beyond the source). The judge is probably **too lenient on faithfulness**
(faithfulness is 1.00 on both splits), so the faithfulness number is an upper bound. The test verdicts were not checked by hand.

## Failure labels

Rule (frozen): not supported yet; abstention error for an ABSTAIN-gold question that was answered; retrieval miss if any scorable gold
source is missing from the top 10; ranking miss if any is missing from the top 5; abstention error if it abstained; else generation error.
q20 and q22 (the two chained-prerequisite questions Phase 1 built) are labelled "not supported yet (chained prerequisite)".

| Label | Dev | Test |
|---|---|---|
| retrieval miss | 2 | 1 |
| ranking miss | 0 | 0 |
| generation error | 0 | 0 |
| abstention error | 0 | 0 |
| not supported yet | 2 | 2 |
| not supported yet (chained prerequisite) | 1 | 1 |

| Split | Question | Type | Label | Reason |
|---|---|---|---|---|
| dev | q01 | lookup | retrieval miss | not in the top 10: page/registrar/applying-graduation#1 |
| dev | q12 | time_sensitive | not supported yet | calendar-only gold |
| dev | q15 | time_sensitive | retrieval miss | not in the top 10: page/EET-NYT/student-hours#1 |
| dev | q22 | multi_chunk | not supported yet (chained prerequisite) | needs the prerequisites of the prerequisites (chained prerequisite) |
| dev | q24 | ambiguous | not supported yet | CLARIFY question |
| test | q07 | lookup | retrieval miss | not in the top 10: page/EET-NYT/degrees#3 |
| test | q11 | time_sensitive | not supported yet | calendar-only gold |
| test | q20 | multi_chunk | not supported yet (chained prerequisite) | needs the prerequisites of the prerequisites (chained prerequisite) |
| test | q23 | ambiguous | not supported yet | CLARIFY question |

Because the rule is retrieval-first and "any gold source missing" counts, **there are no generation errors at all**: every answer that
was not correct either missed a gold source in the top 10, or belongs to a part of the system that does not exist yet.

## The five most instructive failures

1. **q15, dev: "What are the student hours for the Electrical Engineering Technology department?"** The model said "ABSTAIN: The
   sources do not list the Electrical Engineering Technology department's student hours." The only gold page
   (`page/EET-NYT/student-hours#1`, a table titled "ETET Office Hours (Student Hours) Fall 2024") was not in the top 10 (the top 5 were
   EET program chunks and a course). The department contact chunk `contact:EET-NYT` was at rank 7, outside the 5 shown, so the abstention
   could not name the office. The gold answer accepts an abstention only with the department contact, and the judge graded it incorrect for
   that reason. Two causes: the page says "ETET" in a table-heavy chunk, and the abstain path has no contact lookup.
2. **q01, dev: "How do I apply for graduation at City Tech?"** The answer explains applying in CUNYfirst, the alternate portal and the
   late-filing consequence, all cited, but leaves out the Degree Audit check with an advisor and the eligibility list. That section
   (`applying-graduation#1`, "Check Your Degree Audit") was not retrieved while four other sections of the same page were (ranks 1 to 4 of the
   shown five). The judge graded it partial. Related sections of one page are retrieved, but not all of them.
3. **q07, test: "What degrees does the Electrical and Telecommunications Engineering Technology department offer?"** The model answered
   "an associate in applied science in Electrical Engineering Technology (ET-AAS) and a bachelor of technology (ETB-BTECH) [3]". The gold also lists
   the Accelerator Science and Technology Minor. Gold chunks: `degrees#1` at rank 4, `degrees#2` at rank 8, `degrees#3` (the minor) not in the top 10. The top 3 were
   department-overview chunks. The answer is accurate and incomplete (partial).
4. **q20 (test) and q22 (dev), chained prerequisites.** q20: "What do I need to complete before DEN 2400, including the prerequisites of
   those courses?" The model gave DEN 2400's direct prerequisites, then followed only some links (DEN 2300, DEN 1200, DEN 1100) and added a
   claim that DEN 2413 requires four courses plus BIO 3524. The judge: omitted the requirements of DEN 2311, DEN 2315, DEN 2318, DEN 1217, DEN 1218
   and DEN 1114. q22 (MAT 2675): the model repeated the catalog's own wording, "requires the prerequisites of both MAT 1575 and MAT 2580", and stopped; MAT 1575 was at rank 6 and
   MAT 2580 was not in the top 10. Following a chain needs a loop or a tool, and top-5 retrieval does not fetch the next level.
5. **q11 (test) and q12 (dev), dates that live in the calendar table.** "When is the 87th Commencement Ceremony?" (gold: not announced, TBA) and "When does
   the Winter 2027 session end?" (gold: Monday, January 25, 2027) were both stopped by the threshold (top-1 0.463 and 0.542) and answered with the fixed
   "ABSTAIN: I could not find this in the City Tech sources I have." The data is in the verified `calendar_events` table, which the baseline never queries. Not a
   retrieval failure: nothing in vector search can fix it. Related: q23 ("When is the deadline?", gold CLARIFY) was also abstained instead of asking which deadline,
   and q24 ("How many credits do I need to graduate?", gold CLARIFY) answered with 60 and 120 credits plus an example program, without asking which program.

## What each planned Phase 3 change should address

This maps the failures above to the roadmap in `docs/phase2-plan.md`. It is a plan, not a result: none of these changes has been tried.

| Phase 3 change | Failures it should address | Note |
|---|---|---|
| Hybrid search (tsvector + reciprocal rank fusion) | q15 (the page says "ETET"; keyword and acronym match), q07 (department-name words) | Course codes also ranked low in step 6/7 (q21 rank 2, q22 rank 2); not failures here |
| Term and department filters | q15 (department EET and a "Fall 2024" label that must be stated), q07 (overview chunks outranking the degrees page) | The soft term rule in `docs/decisions.md` also covers q15's answer wording |
| Reranker | q07 (gold at ranks 4 and 8), the rank-2 and rank-3 cases (q05, q06, q21, q22) | Will not help q01 or q15, whose gold chunk is not retrieved at all |
| Router with tools: calendar lookup | q11, q12 (and the calendar source of q09) | Largest clean win: both are "not supported yet" today |
| Router with tools: prerequisite chain | q20, q22 | Needs the rule IDs and course records already in `data/processed/courses` |
| Router with tools: contacts | q15 (abstain with the department contact) | The contact chunk exists; the abstain path does not use it |
| A clarify behavior in the router | q23, q24 | The baseline cannot ask a question |
| Retrieving neighbouring sections of a top page | q01 (one section of an otherwise retrieved page was missed) | Not on the roadmap list yet; worth a decision |
| Guardrails, tracing, caching, HNSW | none of the failures here | 0 invalid citations; retrieval is already exact and fast |

## Not measured

- Test correctness has not been verified by hand.
- Multi-turn behavior, long-term drift, and any question outside the 30 are untested.
- The calendar was never exercised: q11 and q12 are the only calendar-only questions.

## 40-question dev baseline (Phase 3 step 0c, 2026-10-12)

The same frozen system (search, prompt, threshold, models, rubric v2; commit `08cc8df` for the system code, `37f472f` for the
runner) run on the grown dev split: the original 20 dev questions plus 20 reviewed new ones. Run `baseline-dev-60`,
`eval/results/baseline-dev-60.json` (also in `eval_runs`). **This is the comparison file for the Phase 3 experiments.** The test split
(20 questions now) was not run. n is next to every number; the groups are small, and the 20 new questions were written and reviewed
by the owner before this run (they were not chosen from any baseline result).

| Metric | 20-question dev (`baseline.json`, rubric v2) | 40-question dev (`baseline-dev-60.json`) |
|---|---|---|
| Questions in the split | 20 | 40 |
| Retrieval-scored questions | n=17 | n=30 |
| Recall@1 / hit@1 | 0.549 / 0.706 | 0.488 / 0.700 |
| Recall@3 / hit@3 | 0.838 / 0.941 | 0.735 / 0.867 |
| Recall@5 / hit@5 | 0.838 / 0.941 | 0.775 / 0.900 |
| Recall@10 / hit@10 | 0.838 / 0.941 | 0.828 / 0.933 |
| MRR | 0.814 | 0.789 |
| Chain row (tagged), recall@5 / hit@5 / MRR | not reported (q22 only) | n=3: 0.500 / 1.000 / 0.833 |
| Correctness, normal gold | n=15: correct 0.80, partial 0.13, incorrect 0.07 | n=26: correct 0.62, partial 0.27, incorrect 0.12 |
| Faithfulness, normal gold | n=15: yes 1.00, partly 0.00, no 0.00 | n=26: yes 0.92, partly 0.00, no 0.08 |
| Chain row: correctness / faithfulness | - | n=3: correct 0.00, partial 1.00, incorrect 0.00 / n=3: yes 0.33, partly 0.00, no 0.67 |
| NO ADVICE gold judged correct | n=1: correct 1.00 | n=2: correct 1.00 |
| Abstention accuracy (ABSTAIN gold) | 1.0 (n=2) | 1.0 (n=5) |
| Wrongly abstained (answerable) | 0.062 (n=16) | 0.107 (n=28) |
| Citation rate / invalid | 1.0 (n=16) / 0 | 1.0 (n=26) / 0 |
| Judge failures | 0 | 0 |
| Cost per request (answer + judge) | $0.00436 (n=20) | $0.00399 (n=40) |
| Total cost of the run | $0.0871 | $0.1597 |
| Latency total, median / p95 ms | 1179 / 2351 (n=20) | 1164 / 2193 (n=40) |
| Latency chat call alone, median / p95 ms | 1201 / 2447 (n=18) | 1219 / 2231 (n=32) |
| Query-embedding cache hits | 20/20 | 40/40 |

The chain row is also counted inside the "all" numbers. Retrieval is scored on 30 of the 40 questions (the calendar-only and
ABSTAIN questions have no section or course gold source). Latency has no embedding time (all 40 query vectors were cached; the dry run
embedded the 20 new ones).

### Failure labels

| Label | 20-question dev | 40-question dev |
|---|---|---|
| retrieval miss | 2 | 3 |
| ranking miss | 0 | 1 |
| generation error | 0 | 3 |
| abstention error | 0 | 0 |
| not supported yet | 2 | 7 |
| not supported yet (chained prerequisite) | 1 | 3 |

| Question | Type | Label | Reason |
|---|---|---|---|
| q01 | lookup | retrieval miss | not in the top 10: page/registrar/applying-graduation#1 |
| q12 | time_sensitive | not supported yet | calendar-only gold |
| q15 | time_sensitive | retrieval miss | not in the top 10: page/EET-NYT/student-hours#1 |
| q22 | multi_chunk | not supported yet (chained prerequisite) | needs the prerequisites of the prerequisites (chained prerequisite) |
| q24 | ambiguous | not supported yet | CLARIFY question |
| q31 | time_sensitive | not supported yet | calendar-only gold |
| q33 | time_sensitive | not supported yet | calendar-only gold |
| q36 | time_sensitive | not supported yet | calendar-only gold |
| q37 | time_sensitive | not supported yet | calendar-only gold |
| q39 | multi_chunk | not supported yet (chained prerequisite) | needs the prerequisites of the prerequisites (chained prerequisite) |
| q40 | multi_chunk | not supported yet (chained prerequisite) | needs the prerequisites of the prerequisites (chained prerequisite) |
| q42 | lookup | generation error | It correctly states the English and math-proficiency prerequisites, but omits the stated no-credit r |
| q49 | ambiguous | not supported yet | CLARIFY question |
| q52 | lookup | retrieval miss | not in the top 10: page/DENT-NYT/faq#12 |
| q54 | lookup | generation error | The answer correctly explains retaking, GPA replacement, transcript retention, prerequisites, and ad |
| q56 | lookup | ranking miss | in the top 10 but not the top 5: page/EET-NYT/student-resources#14 |
| q59 | multi_chunk | generation error | It accurately describes most consequences and the $15 fee, but omits that nonpayment and not attendi |

The three chain questions (q22, q39, q40) are labelled "not supported yet (chained prerequisite)" because they carry the `chain` tag. The
label rule first named only q20 and q22 in code, so the first print of this run showed q39 and q40 as "retrieval miss". After the
rule was changed to follow the tag, the labels were recomputed with `--relabel` (no API call; metrics are unaffected).

### What is different from the 20-question dev

- **Retrieval is lower, mostly because the new questions are harder, not because the system changed.** Hit rate @3 0.941 to 0.867, recall
  @5 0.838 to 0.775, MRR 0.814 to 0.789 (n = 17 to 30). The added misses: q52 (`DENT-NYT/faq#12` never retrieved, the five-year rule for
  science prerequisites), q56 (the EET internship list at rank 7, so a ranking miss), and the chain questions q39 and q40 (the chain courses
  beyond the first level are not in the top 10; chain row n = 3, recall @5 0.500, hit @5 1.000).
- **Correctness 0.80 to 0.62** (n = 15 to 26). New partial answers: q39, q40 (chains), q42 (left out the no-credit rule for MAT 1190),
  q54 (left out tutoring and the financial aid check), q59 (left out that non-payment is not an official drop). New incorrect: q52
  (the model abstained although the policy exists, `answer: the sources do not state whether ... expire`) and q56 (named fewer than 3
  opportunities). Every chain answer is partial (n = 3).
- **Faithfulness is no longer 1.00:** 2 of 26 answers are "no", both chain answers (q22, q40) where the model says the sources do not give
  prerequisites that are in the catalog text it was shown. The judge is still probably lenient (see the trust section above).
- **Calendar questions: none supported.** All five calendar-only dev questions (q12, q31, q33, q36, q37) were answered with an abstention
  (q12, q36 and q37 stopped by the threshold, q31 and q33 by the model); none gave a wrong date. The Summer 2027 question (q34) abstained correctly.
- **Abstention accuracy 5 of 5** (q27, q28, q34, q44, q45). **Wrongly abstained 3 of 28** answerable questions: q15, q47 (threshold) and q52
  (model).
- **NO ADVICE 2 of 2 "correct" is partly vacuous:** q47 ("Should I take an Incomplete or withdraw?") was stopped by the threshold, and an
  abstention gives no advice, so the rule passes it although the gold wants the rules stated. Not changed; recorded in `docs/decisions.md`.
- **CLARIFY** (q24, q49) is still "not supported yet" until step 5; q49 was stopped by the threshold; q24 answered with 60 and 120 credits plus an example program, without asking which degree.
- Cost per request $0.0040 (was $0.0044), run total $0.160 (answers $0.0067 + judge $0.153); latency is the same (median 1,164 ms).
