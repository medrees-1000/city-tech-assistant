# Cutoff sweep (read-only; nothing was changed)

Written 2026-10-15 for tester round 1b, item 1c. **Free: no model call, no re-run, no config change.** Dev split only. The current cutoff is 0.59 (`answer.abstain_threshold`); it is **not** changed by this document and no recommendation here is acted on in this round.

## Where the numbers come from
Only the stored `eval/results/tester1-dev.json` (63 dev questions, run on the settings of the accepted runs). A question's top similarity here is the largest `similarity` among its stored retrieved chunks (the reranked top ten). The cutoff is compared with the best *vector* similarity of the whole candidate pool, which can differ slightly from this stored number; for the four questions that abstain it is close (they all have ten stored chunks). **No dev question was missing a stored similarity.** The two tester cases (0.576 for "whats the tuition deadline", 0.559 for "whens finaid disbursement") are **not** dev questions; their numbers are the ones measured by embedding in tester round 1 (item B).

## What the run shows before any sweep
- Only **4 of 63** dev questions abstain below the cutoff, and all four are correct abstentions: q45 (0.5675, "What days and times does MAT 1475 meet this fall?", gold ABSTAIN), q27 (0.5403, open seats, gold ABSTAIN), q49 (0.4879, "Can I take a class at another college?", typed ambiguous) and q44 (0.4406, "What is my GPA this semester?", gold ABSTAIN).
- **No answerable dev question (lookup, multi_chunk, time_sensitive) abstains below the cutoff today**, so lowering the cutoff cannot win anything on the dev set.
- The lowest top similarities among dev questions answered through retrieval are q24 0.591 (typed ambiguous), q53 0.628, q52 0.632, q59 0.634, q18 0.635, q87 0.638 (all lookup or multi_chunk).

## The table (cutoffs 0.55 to 0.62)
| cutoff | answerable questions that abstain now and would start answering | unanswerable or ambiguous questions that abstain now and would start answering (wrongly) | answerable questions answered now that would start abstaining | tester: "whats the tuition deadline" (0.576) | tester: finaid disbursement (0.559) |
|---|---|---|---|---|---|
| 0.55 | 0 | 1 — q45 (0.568) | 0 | answers | answers |
| 0.56 | 0 | 1 — q45 (0.568) | 0 | answers | abstains |
| 0.57 | 0 | 0 | 0 | answers | abstains |
| 0.58 | 0 | 0 | 0 | abstains | abstains |
| 0.59 | 0 | 0 | 0 | abstains | abstains |
| 0.60 | 0 | 0 | 0 | abstains | abstains |
| 0.61 | 0 | 0 | 0 | abstains | abstains |
| 0.62 | 0 | 0 | 0 | abstains | abstains |

("would start answering" means the best similarity is at or above the cutoff; the fourth column is only filled for cutoffs above 0.59.)

## Plain-language conclusion
- **The dev set cannot show a benefit of a lower cutoff:** it has no answerable question between 0.55 and 0.59, so every column of "would start answering" is zero for answerable questions. The cost side is visible: at 0.55 and 0.56 q45 ("what days and times does MAT 1475 meet") would start to be answered, which is wrong (class meeting times are out of scope); from 0.57 up nothing wrong flips on dev.
- **The tester's cases sit in exactly the band the dev set does not cover.** "whats the tuition deadline" (0.576) would be answered at 0.57 and below; the finaid case (0.559) only at 0.55. A cutoff of 0.57 would fix the first and would not flip any dev question, but it rests on one tester question and an empty band of dev data, so it is a guess, not a measurement. Raising the cutoff to 0.62 would make no answerable dev question abstain either (the lowest answerable one is 0.628), so on dev there is no pressure in either direction.
- What this says about the choice: the cutoff of 0.59 was set from dev data when the dev set had no question in this band, and it still has none; deciding whether 0.57 is better needs reviewed questions that score between 0.55 and 0.59 (the tester's short questions are candidates, to be reviewed by the owner before they enter the dev set; see `docs/tester-round-1-new-questions.md`). **No change was made.**
