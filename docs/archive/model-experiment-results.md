# Model experiment: gpt-6-luna against gpt-6-sol on the retrieval answer (2026-10-14)

Rule: `docs/decisions.md`, "Model experiment: gpt-6-luna against gpt-6-sol ..." (commit `b4685fe`, before any paid run). Plan: `docs/model-experiment-plan.md`. Dev only. Runs `modelexp-luna-run1..3` and `modelexp-sol-run1..3` (38 questions each, same flags, only `--answer-model` differs; this is a **clean single-variable comparison**, because gpt-6-sol accepts luna's settings: reasoning none, temperature 0.1, top_p 0.3), plus `cal3a-check`. Report: `uv run python scripts/model_exp_report.py`. Default unchanged: `answer.model` stays null (luna).

## Result: the rule fails. gpt-6-sol is not better than luna; it is a little worse and about 5.5 times dearer. Recorded as "not worth the cost".

Primary set: 28 questions took the retrieval route in all six runs (q01 q03 q04 q05 q06 q08 q13 q14 q15 q16 q18 q19 q24 q27 q28 q44 q45 q47 q49 q51 q52 q53 q54 q56 q57 q58 q59 q87). The other ten of the 38 were answered by code in at least one run (q09 q12 q21 q30 q31 q33 q34 q36 q37 q42). One question is 0.036 of 28.

| Primary set, per pass (1, 2, 3) and mean | gpt-6-luna | gpt-6-sol |
|---|---|---|
| judged "correct" share | 0.923, 0.923, 0.923; **mean 0.923** | 0.808, 0.846, 0.923; **mean 0.859** |
| judged "partial" share | 0.077 each; 0.077 | 0.192, 0.154, 0.077; 0.141 |
| faithfulness "yes" share | 0.952, 0.952, 0.905; 0.937 | 0.905, 1.000, 0.952; 0.952 |
| wrongly abstained | 0.091 each | 0.091 each |
| abstention accuracy | 1.00 each | 1.00 each |
| citation rate / invalid citations | 1.00 / 0 | 1.00 / 0 |
| cost per retrieval-route request (whole request) | $0.0008 | $0.0045 |
| median latency | 6.2 s | 6.2 s |
| mean answer length | 59.2 words | 57.0 words (ratio 0.96) |

The same numbers on all 38 questions (reported, not used for the decision): correct 0.889 for luna against 0.852 for sol; cost $0.0007 against $0.0034 per request.

**The rule.**
- B1 FAIL: gain **-0.064** (needed +0.05); sol was higher in **0 of 3** paired passes.
- B2 pass (+0.016), B3 pass (no change), B4 pass (no change), B5 pass ($0.0045 is under $0.01), B6 pass (length ratio 0.96).
- Borderline: no (the gain is negative). No cross-judge is proposed.

**Reading.** Luna's three passes gave the same verdict on every one of the 28 questions (0.923 each time), so its answers and the judge are steady at these settings. Sol varied (0.808, 0.846, 0.923) although temperature is 0.1: a stronger model at the same settings is not as steady, and its third pass equals luna. The mean gap is about 1.8 questions on 28 and is mostly in two questions (q54, q57, both "partial" for omitting listed steps such as tutoring, advisor and the application procedure); sol was better on q59 (all three passes) and wrote a shorter answer on q14, which the judge once marked faithfulness "no" for a sentence the sources contradict ("the calendar does not give an individual refund date"). With only 28 questions and a judge that moves 0.03 to 0.05 alone, the honest statement is: **no sign that sol answers better, some sign that it is slightly worse**; not tested further, since the rule needs a gain.

## The answers where the arms differ in a majority of passes (4 questions; full text and judge reasons printed by the script)
- **q14** (refund date): luna correct/yes in all passes; sol partial/no, partial/yes, correct/yes. Sol's run 1 says "the calendar does not give an individual refund date" and omits the later weekly dates; the judge calls that unfaithful.
- **q54** (fail a math course): luna correct in all passes; sol partial in all three (omits tutoring, office hours, advisor and the financial-aid check; the gold lists them).
- **q57** (Fresh Start): luna correct in all passes and includes how to apply (NG-15, the form, the fee, the SAP effect); sol partial, partial, correct (84 words, omits the application procedure).
- **q59** (not paying tuition): **sol better**: correct in all three; luna partial in all three (omits that non-payment is not an official drop).

## Cost and daily figures
- Per run (answer pipeline plus judge): luna $0.154, $0.152, $0.155; sol $0.261, $0.251, $0.264. Calendar check $0.0077. **Round total $1.24** (cap $2.50; the probes cost under $0.0001).
- Per request by route (from run 1 of each arm): retrieval route luna **$0.0008**, sol **$0.0045**; calendar route $0.0005 (classifier and selector); prerequisite (chain) $0.00004; code abstention $0.00008. The average over the 38-question mix: luna **$0.0007**, sol **$0.0034**.
- Under the $1.00 daily cap: about 1,230 retrieval requests a day with luna, **about 220 with sol**; across the mix, about 1,400 with luna and 290 with sol. Not adopted, so these are only the answer to "what would it have cost".

## The calendar check of step 3a (`cal3a-check`, one judged pass, $0.0077)
The 11 questions q09 q61 q63 q64 q65 q67 q68 q71 q75 q90 q95: all 11 answered by the calendar route and all 11 correct. Only q09 is judged by text: **correct and faithful "yes"**, as in its three earlier runs (`router2-run1..3`). The ten others are scored by row id (identical to the stored rows, as check 6 predicted), including the two new ones q90 and q95. The new layout did not hurt.
