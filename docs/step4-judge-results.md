# Judge variants against labeled and planted answers (step 4-judge, 2026-10-12)

Pre-registered in `docs/experiments.md` and committed with the prompts, labels and plant code in `3161c8e`, before the paid run. Judge model unchanged (`gpt-5.6-terra`). Nothing stored was re-judged. Test split not touched. Cost **$0.7447** of the $1.00 budget (the run finished; the upper-bound estimate had been $1.71, real cost was lower because repeated prompts are billed at the cached price).
Cells show correctness / faithfulness. Planted items are generated at run time from the labeled items (8 number plants: `66 -> 68` on q04, `3 -> 6` on q05, `1098 -> 1099` on q08, `MAT 2675 -> MAT 2676` on q22 twice, `CST 3613 -> CST 3614` on q40 twice, `BIO 2311 -> BIO 2313` on q52 on-run1; 2 cross-pairs, q22 and q52).

| item | kind | label (corr / faith) | v3 run1 | v3 run2 | v4-reason run1 | v4-reason run2 | v4-claims run1 | v4-claims run2 |
|---|---|---|---|---|---|---|---|---|
| q01 @ baseline-dev | real | partial / yes | correct / yes | correct / yes | partial / yes | partial / yes | correct / partly | correct / partly |
| q03 @ baseline-dev | real | correct / partly | correct / yes | correct / yes | correct / yes | correct / yes | correct / yes | correct / yes |
| q04 @ baseline-dev | real | correct / yes | correct / yes | correct / yes | correct / yes | correct / yes | correct / yes | correct / yes |
| q05 @ baseline-dev | real | correct / yes | correct / yes | correct / yes | correct / yes | correct / yes | correct / yes | correct / yes |
| q06 @ baseline-dev | real | correct / yes | correct / yes | correct / yes | correct / yes | correct / yes | correct / yes | correct / yes |
| q08 @ baseline-dev | real | correct / yes | correct / yes | correct / yes | correct / yes | correct / yes | correct / yes | correct / yes |
| q12 @ baseline-dev | real | incorrect / yes | incorrect / yes | incorrect / yes | incorrect / yes | incorrect / yes | incorrect / partly | incorrect / partly |
| q15 @ baseline-dev | real | partial / yes | incorrect / yes | incorrect / yes | partial / yes | partial / yes | incorrect / yes | incorrect / yes |
| q22 @ baseline-dev-60-v3 | real | partial / yes | partial / no | partial / no | partial / no | partial / no | partial / yes | partial / yes |
| q22 @ on-run1 | real | partial / yes | partial / yes | partial / yes | partial / yes | partial / yes | partial / yes | partial / yes |
| q40 @ baseline-dev-60-v3 | real | partial / yes | partial / yes | partial / yes | partial / yes | partial / yes | partial / yes | partial / yes |
| q40 @ on-run1 | real | partial / yes | partial / yes | partial / yes | partial / yes | partial / yes | partial / yes | partial / yes |
| q52 @ baseline-dev-60-v3 | real | incorrect / yes | incorrect / no | incorrect / no | incorrect / no | incorrect / no | incorrect / no | incorrect / no |
| q52 @ on-run1 | real | correct / yes | correct / yes | correct / yes | correct / yes | correct / yes | correct / yes | correct / yes |
| q15 @ on-run1 | real | partial / yes | incorrect / yes | incorrect / yes | incorrect / yes | partial / yes | incorrect / no | incorrect / no |
| q15 @ baseline-dev-60-v3 | real | partial / yes | incorrect / yes | incorrect / yes | partial / yes | partial / yes | incorrect / yes | incorrect / yes |
| plant:q04 @ baseline-dev | plant_number | planted: not yes | partial / no | partial / no | partial / no | partial / no | partial / no | partial / no |
| plant:q05 @ baseline-dev | plant_number | planted: not yes | partial / no | partial / no | partial / no | partial / no | partial / no | partial / no |
| plant:q08 @ baseline-dev | plant_number | planted: not yes | partial / no | partial / no | partial / no | partial / no | partial / no | partial / no |
| plant:q22 @ baseline-dev-60-v3 | plant_number | planted: not yes | incorrect / no | incorrect / no | partial / no | partial / no | incorrect / no | incorrect / no |
| plant:q22 @ on-run1 | plant_number | planted: not yes | partial / no | partial / no | partial / no | partial / no | partial / no | partial / no |
| plant:q40 @ baseline-dev-60-v3 | plant_number | planted: not yes | partial / no | partial / no | partial / no | partial / no | partial / partly | partial / partly |
| plant:q40 @ on-run1 | plant_number | planted: not yes | partial / no | partial / no | partial / no | partial / no | partial / partly | partial / partly |
| plant:q52 @ on-run1 | plant_number | planted: not yes | partial / no | partial / no | partial / no | partial / no | partial / partly | partial / partly |
| cross:q22 | plant_cross | planted: not yes | partial / no | partial / no | partial / no | partial / no | partial / no | partial / no |
| cross:q52 | plant_cross | planted: not yes | incorrect / no | incorrect / no | incorrect / no | incorrect / no | incorrect / no | incorrect / no |

| | v3 (control) | v4-reason | v4-claims |
|---|---|---|---|
| (1) real items with a faithfulness verdict that differs from the label, run 1 / run 2 | 3 / 3 | 3 / 3 | 5 / 5 |
|     which items (run 1) | q03 @ baseline-dev, q22 @ baseline-dev-60-v3, q52 @ baseline-dev-60-v3 | q03 @ baseline-dev, q22 @ baseline-dev-60-v3, q52 @ baseline-dev-60-v3 | q01 @ baseline-dev, q03 @ baseline-dev, q12 @ baseline-dev, q52 @ baseline-dev-60-v3, q15 @ on-run1 |
|     count excluding q15 on-run1 | 3 / 3 | 3 / 3 | 4 / 4 |
| (2) planted items marked not yes (of 10), run 1 / run 2 | 10 / 10 | 10 / 10 | 10 / 10 |
| (3) correctness matches with the 16 labels, run 1 / run 2 | 12 / 12 | 15 / 16 | 12 / 12 |
| (4) verdicts that flip between the two runs | 0 | 1 | 0 |
| qualifies | control | no (criteria 1 failed) | no (criteria 1 failed) |

Cost $0.7447. Decision by the pre-registered rule: **v3**.

## What the table shows

- **No variant qualifies; v3 stays.** Criterion (1) fails for both: v4-reason has the same 3 faithfulness mismatches as v3 (q03, q22 and q52 on the stored baseline answers), v4-claims has 5.
- **The three v3 faithfulness mismatches are the known ones:** q03 (the judge says yes, the owner partly), and q22 and q52 on the stored baseline answers (the judge says no; the second reader says yes). The two "the sources do not state X" answers are the baseline answers q22 and q52; on the `on-run1` answers v3 agrees with the labels.
- **v4-claims fixes q22 (baseline) but breaks others:** it says "partly" on q01 and q12 and "no" on q15 on-run1 where the labels say yes, and it still says "no" on q52 (baseline). Its two-step check is stricter on exactly the abstentions and short answers that carry few claims. It is deterministic here (0 flips), v4-reason had 1 flip.
- **v4-reason changes only correctness, in the direction of the labels:** correctness matches 15 and 16 of 16 labels (v3: 12 of 16, both runs), because it grades q01 and q15 (baseline-dev) as partial like the owner and q15 baseline-dev-60 as partial like the second reader. Its faithfulness verdicts equal v3's on every real item except q15 on-run1 in none of the two runs. This was not a pre-registered goal; criterion (3) only asks for "at least v3's".
- **Planted errors:** all three variants mark all 10 planted items as not yes in both runs (v4-claims uses "partly" on three of them). The planted errors are crude, so this says the judges see a changed number or a false "sources do not state X" claim against the sources, not that they catch subtle unsupported claims.
- **q15 on-run1 (the borderline item):** v3 says yes, v4-reason yes, v4-claims no. Excluding it the counts do not change for v3 and v4-reason (3 / 3) and drop by one for v4-claims (4 / 4).
- **Corrected v3 agreement with the owner's 8 original items** (the `baseline-dev` answers the owner labeled, judged now by v3): correctness 6 / 8 (q01 correct vs partial, q15 incorrect vs partial), faithfulness 7 / 8 (q03 yes vs partly). v4-reason: correctness 8 / 8, faithfulness 7 / 8 (q03).

## Caveats

16 labeled items is small; 8 labels come from a second reader accepted by the owner; nearly all real labels are yes, so the planted items carry the detection test; the planted errors are crude; the judge sees only the answer and the sources; v4-reason runs at the default temperature (the API rejects temperature 0 with reasoning on), so it is stochastic by design (1 flip in 64 verdicts here).
