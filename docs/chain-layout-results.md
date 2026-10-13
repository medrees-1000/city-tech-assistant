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
