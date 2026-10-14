# Chain layout, step 1: dev comparison (2026-10-13)

Pre-registered rule and how it is read: `docs/decisions.md` ("Step 1 (chain layout): the keep rule", commit `62ca63a`, before any paid run). Runs: `chain-code-run1` and `chain-code-run2` (`--chain-render code`, dev, ids q22 q39 q40 q76 q77 q79 q81 q85 and the controls q83 and q87; two runs because the answers are deterministic and the second run is the second judge pass: the existing re-judge cannot replay a chain-route run, its sources are not retrieval sources) against `4b-run1..3` (model-written chain answers). Cost of the two runs: $0.0469 and $0.0469 (answers $0.0011 each, judge $0.0458 each), $0.094 in total; the tool's estimate was $0.07 per pass, an upper bound. Output of `scripts/chain_render_report.py`:

```
CH questions: ['q22', 'q39', 'q40', 'q76', 'q77', 'q79', 'q81', 'q85']

=== DETERMINISTIC RESULTS (no judge) ===
M1 4b-run1: 8 of 8 CH questions answered by the chain node
M1 4b-run2: 8 of 8 CH questions answered by the chain node
M1 4b-run3: 8 of 8 CH questions answered by the chain node
M1 chain-code-run1: 8 of 8 CH questions answered by the chain node
M1 chain-code-run2: 8 of 8 CH questions answered by the chain node
M3 4b-run1: gold catalog sources received on 4 of 5 questions with 2+ gold sources
M3 4b-run2: gold catalog sources received on 4 of 5 questions with 2+ gold sources
M3 4b-run3: gold catalog sources received on 4 of 5 questions with 2+ gold sources
M3 chain-code-run1: gold catalog sources received on 4 of 5 questions with 2+ gold sources
M3 chain-code-run2: gold catalog sources received on 4 of 5 questions with 2+ gold sources
M6 4b-run1: q83 abstained=True route=abstain
M6 4b-run2: q83 abstained=True route=abstain
M6 4b-run3: q83 abstained=True route=abstain
M6 chain-code-run1: q83 abstained=True route=abstain
M6 chain-code-run2: q83 abstained=True route=abstain
determinism: the two code runs wrote identical text for 8 of 8 CH questions
no 'Level' wording in any code answer: True
sources identical to the 4b runs' sources (ids and order): True
K4 cost per chain question (route cost, judge excluded): 4b $0.000323, code $0.000042 (lower: True)
latency per chain question, mean: 4b 2874 ms, code 1001 ms

=== THE JUDGE'S VERDICTS (rubric v3; known to be unreliable on 'the sources do not state X' sentences) ===
correctness 'correct' on the 8 CH questions: 4b runs [6, 6, 6] (mean 6.00); code runs [6, 6] (mean 6.00); difference +0.00 questions
faithfulness 'yes' on the 8 CH questions: 4b runs [8, 8, 8] (mean 8.00); code runs [7, 7] (mean 7.00); difference -1.00 questions
per question (4b run1, run2, run3 | code run1, run2) correctness / faithfulness:
  q22: corr/yes corr/yes corr/yes | corr/yes corr/yes
  q39: part/yes part/yes part/yes | part/partly part/partly
  q40: part/yes part/yes part/yes | part/yes part/yes
  q76: corr/yes corr/yes corr/yes | corr/yes corr/yes
  q77: corr/yes corr/yes corr/yes | corr/yes corr/yes
  q79: corr/yes corr/yes corr/yes | corr/yes corr/yes
  q81: corr/yes corr/yes corr/yes | corr/yes corr/yes
  q85: corr/yes corr/yes corr/yes | corr/yes corr/yes
controls: q87 (not a chain question) route: {'chain-code-run1': 'other', 'chain-code-run2': 'other'} correctness: {'chain-code-run1': 'correct', 'chain-code-run2': 'correct'}
  chain-code-run1 q39: correctness=partial (It correctly traces the listed course prerequisites through MAT 1375, but omits the MAT 1275 and MAT 1275CO endpoint requirements that are part of the) faithfulness=partly (The catalog-supported prerequisite statements are accurate, but the claim that the chain stops because of a "depth limit" is unsupported by the provid)
  chain-code-run1 q40: correctness=partial (It correctly gives CST 3613's prerequisites and the CST 1201 chain, but incorrectly states that CST 1204 requires both CST 1100 and CST 1101 rather th) faithfulness=yes (Every stated prerequisite and catalog quotation, including CST 1204's requirement of CST 1100 and CST 1101, is supported by the provided numbered sour)
  chain-code-run2 q39: correctness=partial (It accurately traces the listed course prerequisites through MAT 1375 but omits the final MAT 1275 and MAT 1275CO prerequisite details and incorrectly) faithfulness=partly (The catalog quotations and course relationships are supported, but the claim that the chain stops because of a "depth limit" is unsupported by the pro)
  chain-code-run2 q40: correctness=partial (It correctly gives CST 3613's prerequisites and CST 1201's requirements, but incorrectly states that CST 1204 requires both CST 1100 and CST 1101 rath) faithfulness=yes (Every claim in the answer, including CST 1204's stated prerequisite of CST 1100 and CST 1101, is supported by the provided numbered sources.)
```

## Reading it against the rule
- **K1 (deterministic checks 1 to 9): pass.** `tests/test_chain_render.py` (all 197 chains) and `web/lib/chainrender.test.ts`.
- **K2 (the judge's verdicts): pass, narrowly.** Correctness on the 8 CH questions: 4b mean 6.00, code mean 6.00 (not lower). Faithfulness: 4b 8.00, code 7.00, a drop of exactly one question, which the rule allows ("not lower by more than one"). The one drop is q39, in both code runs: the judge saw the closing sentence "The chain stops here: ... (depth limit)" as unsupported, because it judges against the numbered sources only and that sentence comes from the walk, not from a source (the same judge-visibility artefact as q82 in milestone 1). The answer text is verbatim by construction; the verdict on this item is the judge's limit, not a wrong statement. q39 and q40 are partial in all five runs for the reasons they were partial before: q39 stops at the depth limit; for q40 the judge says CST 1204 needs "only CST 1100" per its gold, while the catalog text is "PRE: CST 1100 & 1101" and the walk names both (a gold-versus-walk difference that is the same in the 4b runs; it is not caused by the layout).
- **K3 (M1 to M6): pass.** M1 8 of 8, M3 4 of 5, M6 q83 abstains: all identical to the 4b runs. M2, M4 and M5 involve questions this change cannot touch (only the chain node's answer step changed): unchanged by construction, not re-run. The sources and their order are identical to the 4b runs' sources.
- **K4 (cost lower): pass.** Route cost per chain question $0.000042 against $0.000323 (the classifier only), mean latency about 1.0 s against 2.9 s.
- **Determinism:** the two code runs wrote identical text for 8 of 8 CH questions.
- **Result: the rule passes; the default of `router.chain_render` flips to `"code"` in its own commit.**

# Step 2 (two- and three-course questions): J1 on dev (2026-10-14)

Rule: J1 in `docs/decisions.md` (step 2 keep rule, with the q42 sentence added in `1fa2930` before the run). Runs `chain2-run1` and `chain2-run2` (14 dev questions: CH q22 q39 q40 q76 q77 q79 q81 q85 q93 q94, plus q42, q21, q83, q87; `--router on --selector 2 --chain on --chain-render code --calendar-scoring 2 --rerank pool_a`). Real cost: **$0.0678 + $0.0681 = $0.136** (estimate $0.14, tool upper bound $0.10 per pass shown in the dry run; cap $0.30 not approached). Report: `uv run python scripts/chain2_report.py` (the full answers of q42, q93, q94 and the judge reasons print there; the answers are in `request_logs` under the two labels).

## Deterministic conditions (no judge)
| Condition | Result |
|---|---|
| M1: 10 of 10 CH answered by the chain node, both runs | **pass** (10/10, 10/10) |
| R1: q87 never by the chain node; non-CH ids by the chain node only q21, q42 | **pass** (q87 route `other` in both; ids `[q21, q42]` in both) |
| M3 at least 0.80 with q93, q94 counted, both runs | **pass** (6 of 7 = 0.86 in both; q39 is the miss, as in step 1 and 4b) |
| M6: q83 abstains | pass (both) |
| Earlier eight CH answers byte-identical to the step 1 code runs | **pass, read through the K2 hashes**: 8 of 8 equal the SHA-256 of the renderer at `f6cdbdc` in both runs. A literal text comparison with `chain-code-run1/2` fails 8 of 8 because those runs predate C1 and still contain the word "chain"; K2 was defined against `f6cdbdc` for that reason. |
| Two runs write identical text | yes, 11 of 11 chain-node questions |

## The judge's verdicts (rubric v3)
- **q93: correct / yes in both runs. q94: correct / yes in both runs.** Condition **pass**.
- **q42: partial in both runs** (run 1 faithfulness no, run 2 yes). The q42 sentence: J1 fails only on "incorrect"; **not incorrect, so it does not fail**. The judge's reasons: the answer states both listings but does not explain the difference, and (a judge misreading) says the MAT 1275 credit note belongs only to MAT 1190 although MAT 1190CO's text is quoted as it is; run 1's "no" faithfulness rests on that misreading. The prediction written before the run (partial, no difference sentence) held.
- Other verdicts on the same text vary between runs: q22 correct/yes then partial/no (identical text; the run 2 reason says the answer wrongly claims MAT 1275CO names MAT 1275, which the printed block shows it does), q21 partial then correct. This is the judge's known noise, not a change of the answers.

## J1: all stated conditions hold. The q42 answer text was to be shown to the owner before the keep decision (done in the report of this step). No default or setting was changed.

# Step 3a (calendar layout): results (2026-10-14)

Rule: `docs/decisions.md`, "Step 3a: calendar layout, keep rule" (commit `b6101b5`, before any code). Code commit `1ca08af`: only `src/cta/graph/render.py` changed in `src/` (check 7); tests in `tests/test_calendar_layout.py` (13 tests, checks 1 to 8), `web/lib/calendarrender.test.ts` (3 tests) and three fixtures written by the Python renderer; `tests/test_router.py` was updated to the new text (8 assertions of the old layout). Full run: ruff, pytest (1162 passed), `python -m cta.validate`, typecheck, `next build`, node tests (95 passed) all clean.

**Deterministic results.** Checks 1 to 5: pass (all 136 calendar rows render their old date text; numbers unique and mapped to their source; one provenance line per calendar with the rows' own term, file and date; TBA rows say "not announced yet" and keep the Registrar line; one-row answers keep their provenance below; two terms give two groups). Check 6: pass: for the 9 stored dev runs (`4b-run1..3`, `router-run1..3`, `router2-run1..3`), 133 calendar-route answers (the test requires at least 100), the stored returned row ids render back to exactly those ids in the same order, and the calendar scorer (versions 1 and 2) returns identical results. Check 7: pass: the 197 chain hashes, the abstention hash, and the diff is limited to `render.py`. Check 8: pass. The judged effect on text-scored calendar answers (q09, q10, q30 ...) is **not measured yet**; the next judged dev run will include them.

**Live check (real API and page, headless Chrome, dev, real requests).** "When does Winter 2027 end?" and "When does the Winter 2027 session start and end?" (q95), each at 390 px and 1280 px, light and dark: eight real requests, **$0.0040 in total** (about $0.0005 each; allowed $0.02). Servers stopped afterwards (ports 8000 and 3000 free).
- *End* (one row): a plain paragraph with the date in bold, "**Monday, January 25, 2027**: End of Winter 2027 Session [1]" (the [1] is a small blue link), then a separate paragraph "From the Winter 2027 calendar (winter_2027.pdf, last updated 2026-07-27). The calendar can change.", then the thumbs, "Sources (1)" and "How this was found".
- *Start and end* (two rows): two bullets, "**Monday, January 4, 2027**: Start of Winter 2027 session. [1]" and "**Monday, January 25, 2027**: End of Winter 2027 Session [2]", then the one provenance paragraph, then thumbs, "Sources (2)", "How this was found". The old answer repeated the long provenance clause on every row.
- At 390 px the bold date and event wrap to a second line inside the bullet and the provenance paragraph wraps over three lines; there is no horizontal scroll at either width (page width equals window width). At 1280 px each bullet fits on one line. Dark mode: white bold dates and light blue [n] links on the dark background, readable. In the full-page screenshot at 390 px the fixed input bar overlaps the "How this was found" link; that is how a full-page capture draws a fixed bar (the bar sits at the window bottom), not a layout fault.
- The Chrome libraries were missing on this machine; I downloaded three packages (libnspr4, libnss3, libasound2t64) into the scratch folder, outside the repo, and ran the existing headless shell with them. No repo file or dependency changed.

# Step 5b (answer-prompt formatting rule): results (2026-10-14)

Rule: `docs/decisions.md`, "Step 5b" (F1 to F6) and its addendum (commit `c6563dd`, before any paid run). Code `9b4eec3` (`answer.format_rule: off | on`, default off). Before arm: `modelexp-luna-run1..3` (reused, not re-run). On arm: `fmt-on-run1..3` (only `--format-rule on` differs; 38 ids; primary set of 28). Report: `PYTHONPATH=scripts uv run python scripts/format_rule_report.py`. **`answer.format_rule` stays off; nothing was switched on.**

## Result: F1, F3, F4, F5 and F6 pass; **F2 fails**, so the rule as pre-registered does not pass. The tuition question is fixed; the instruction also turns other answers into lists.

**Deterministic (no judge).**
- **F1 pass** (q13, all three on passes): four bullet lines, each with a date, every date the before answers stated is still there.
- **F3 pass** (q13): "depends on when you first registered" is in all three on answers.
- **F2 FAIL** (27 other questions x 3 passes): 21 answer-pass cases have more than one bullet. Six questions became lists in all three passes: q05 (3 to 4 bullets: CST internships), q06 (4: the four degrees), q16 (2: two drop periods), q18 (5 to 8: transfer credit rules), q24 (3: credit minimums), q56 (10 to 11: the EET internship resources). Two more did in some passes: q14 (10 bullets of refund dates in pass 1, none in the others) and q59 (a four-line tier list in passes 2 and 3, copied from the tuition table, although the question is about consequences). Several of these are sensible lists (degrees, resources, tiers); q16 and q59 are not what the rule was for. Under the rule as written they are failures.
- **F6 pass**: code-route answers (calendar, prerequisite, code abstention) are byte-identical in all six runs for all 10 questions that took a code route; no question changed route.

**The judge (primary set, 28 questions; passes 1, 2, 3 and mean).**

| | before (luna) | rule on |
|---|---|---|
| correct share | 0.923, 0.923, 0.923; **0.923** | 0.923, 0.923, 0.885; **0.910** |
| faithfulness "yes" | 0.952, 0.952, 0.905; **0.937** | 0.952, 0.952, 0.952; **0.952** |
| wrongly abstained | 0.091 | 0.091 |
| abstention accuracy | 1.00 | 1.00 |
| mean answer length | 59.2 words | 63.3 words |
| cost per request | $0.00081 | $0.00082 |

- **F4 pass** (correct 0.910 against the 0.893 floor; faithfulness 0.952 against 0.907). **F5 pass.**
- Two questions differ in the judged verdict in most paired passes: **q01** (partial before, one correct and two partial after: noise-sized) and **q54** (correct in all three before; correct, partial, partial after: the answer lost a sentence about delay and STEM progression, which the gold does not need but the judge liked).

**q13 before and after** (luna, run 1 of each):
- Before: "For Fall 2026, your tuition due date depends on when you first registered: March 19–July 19: August 3; July 20–August 7: August 14; August 8–27: August 27; August 28 or later: immediately upon registration. [1]"
- After (pass 1): "For Fall 2026, your tuition payment due date depends on when you first registered [1]:" then four bullets, "First registered March 19–July 19: August 3, 2026 [1]", "First registered July 20–August 7: August 14, 2026 [1]", "First registered August 8–27: August 27, 2026 [1]", "First registered August 28 or later: immediately upon registration [1]". Passes 2 and 3 are the same four tiers (one writes "August 8–August 27"; pass 3 puts the `[1]` before the colon and a full stop after each date). The judge scored the run-on version correct as well, so the gain is layout only, which is what the rule claimed.

**Cost.** On passes $0.1570, $0.1536, $0.1552 (**$0.466**); live check on the page about $0.003; the before arm was reused (no cost). Round total about **$0.47** (cap $1.00).

## Live check (real API with `CTA_ANSWER_FORMAT_RULE=on`, real page, headless Chrome; four real requests, $0.0029; servers stopped, ports free)
"When is my tuition bill due this fall?" at 390 px and 1280 px, light and dark: a one-line lead ("For Fall 2026, your tuition due date depends on when you first registered:" with a small blue [1]), then four real bullets, each "First registered ...: <date>, 2026." with its [1] link, then the thumbs, "Sources (5)" and "How this was found". No horizontal scroll at either width; at 390 px each bullet wraps to two lines and is easy to read; dark mode is readable. In one request the model put the [1] before the colon, which renders as "registered [1] :" with the colon on its own after the link, a small blemish.
