# Plan: a stronger answer model for the retrieval route (docs only, 2026-10-14)

Written for the project owner. Nothing in this file has been run. The only call made to write it was the free models-list call. Prices come from the OpenAI pricing page read today (standard tier, text, per 1M tokens) and from `config/models.yaml`.

## 1. What the account can use

The models endpoint returned 133 ids. The chat models that matter here:

| Model | Input | Cached input | Output | Note |
|---|---|---|---|---|
| gpt-6-luna (now: every chat step) | $0.10 | $0.01 | $0.50 | baseline |
| gpt-6.1-sol | $2.00 | $0.10 | $10.00 | listed in `models.yaml` already |
| gpt-6-sol | $2.00 | $0.20 | $10.00 | same price as 6.1-sol; the older version, not proposed |
| gpt-6-astra | $10.00 | $1.00 | $50.00 | the largest gpt-6 model; not in `models.yaml` yet |
| gpt-5.6-luna / sol / terra | $0.20 / $4.00 / $2.00 | | $1.20 / $20.00 / $12.00 | the judge is gpt-5.6-terra; see section 3 |
| gpt-5.5 | $5.00 | $0.50 | $30.00 | older generation, dearer than 6.1-sol |
| gpt-5.4, gpt-5.4-mini, gpt-4.1 | $2.50, $0.75, $2.00 | | $15.00, $4.50, $8.00 | older, not proposed |

(`o1`, `o3`, `gpt-5-pro` and the other reasoning or pro models are also on the account; they are slow and dear and the answer step needs no long reasoning, so they are not candidates.)

**Candidates (two):**
1. **gpt-6.1-sol**: same family and generation as the baseline, 20 times the input price. The natural "one step up".
2. **gpt-6-astra**: the top of the same family, 5 times dearer again. It tells us whether more capability helps at all; it is optional (section 5, decision 1).

## 2. The one change

Only the model that writes **retrieval-route answers** changes. Today every chat step shares `chat_model` (`src/cta/answer.py`, `src/cta/graph/llm.py` for the classifier, selector and topic call, and `src/cta/index/rerank.py`), so the change needs a new key:

- `answer.model` in `config/models.yaml` (default `null` = use `chat_model`, so nothing changes by default), overridden by `CTA_ANSWER_MODEL` and a runner flag `--answer-model`.
- It is read only where the retrieval answer is written and priced (`answer.py`, and the cost line in `src/cta/graph/build.py`). The classifier, the calendar selector, the topic call and the reranker stay on gpt-6-luna; the judge stays on gpt-5.6-terra; retrieval, k, the abstain threshold and the prompt are untouched.
- A new model must be in `models.yaml` (a model that is not listed is refused, so cost is never silently zero); gpt-6-astra gets added with the price above.
- **Step 0 (free tests, then one probe):** tests that the default (`null`) gives the same model, the same request body and the same prompt as today, and that only the answer call changes with the key set. Then one tiny call per candidate (under $0.001 in all) to check that `temperature` 0.1, `top_p` 0.3, `reasoning_effort: none` and `max_completion_tokens` are accepted, as was done for luna on 2026-10-12. If a model refuses a setting, I report it and ask before changing anything; a different setting between arms would be a second change.

## 3. The judge is a different generation, with two safeguards

The judge is gpt-5.6-terra. The baseline and both candidates are gpt-6 models, so no arm is the judge's own family, which is why gpt-5.6-terra, -sol and -luna are not candidates (a judge may favour text written by its own family). The remaining bias is general: a judge may prefer longer, more polished text. Safeguards, fixed now:
- Report the mean answer length (words) per arm next to the verdicts. If an arm is "better" but more than 30 percent longer, the result is flagged and the owner decides.
- The owner reads every question whose verdict differs between the baseline and the winning arm in the majority of passes (expected under ten questions), before anything is switched.
- Optional (decision 3): one cross-check pass per arm by `--rejudge` (no answer calls) with a second judge, gpt-5.5, about $0.5 per arm. It is not part of the rule; it is evidence if the main result is close.

## 4. Pre-registered rule (written before any run)

**Questions:** the 42 dev questions that are tagged neither `calendar` nor `chain` (lookup 16, time_sensitive 9, unanswerable 8, multi_chunk 5, ambiguous 4), run through the whole pipeline (`--router on --selector 2 --chain on --chain-render code --calendar-scoring 2 --rerank pool_a`). A few go to the calendar or chain route because of the classifier; their answers are written by code and identical in every arm, so all metrics are also reported on the questions that took the retrieval route in all runs. One question is 0.024 of 42.

**Arms:** A0 = gpt-6-luna (baseline). A1 = gpt-6.1-sol. A2 = gpt-6-astra (only if decision 1 says so). **Three judged passes per arm** = three full runs of the 42 questions (answers rewritten each time, judged each time), same ids, same code, same settings.

**Metrics** (mean of the three passes, shares of the 42): judged correctness ("correct" share and the partial share), judged faithfulness ("yes" share), wrongly-abstained, abstention accuracy, citation rate, cost per request, latency (median and p95), mean answer length. Retrieval metrics are not part of the rule (they cannot change: retrieval is untouched).

**Noise.** The judge alone moves 0.03 to 0.05 between passes, and one question is 0.024. So "better" must clear the noise, and "not worse" must allow it:

An arm is **better** (a candidate to be switched on) only if **all** hold:
- B1: mean "correct" share at least **0.05 above** A0 (about two questions), **and** higher than A0 in at least 2 of the 3 paired passes;
- B2: faithfulness "yes" share not lower than A0 minus 0.03;
- B3: wrongly-abstained not higher than A0 plus 0.024 (one question), and abstention accuracy not lower than A0 minus 0.03;
- B4: citation rate not lower than A0 minus 0.03, and invalid citations not above A0's;
- B5: cost per request on the retrieval route at most $0.01 for A1 (about 13 times today's), and at most $0.03 for A2 (see section 6); the owner may waive this, in writing, before the run;
- B6: the length flag of section 3 is not raised, or the owner accepts it after reading the changed questions.

**Not worse** (the rule for an arm that is not better) means a difference of **less than 0.03** in correct share and in faithfulness share against A0, inside what the judge does alone. An arm that is not better stays off, whatever its cost; "not worse and dearer" is a rejection.

Between two arms that are both better, the cheaper wins unless the dearer is above the cheaper by at least 0.05 more on B1. If no arm is better, `answer.model` stays `null` (luna) and that result is recorded as "no gain from a stronger model on dev".

**Test split:** untouched. A switch of the default is its own commit after the owner's decision; the next test run (the `--final` run) uses whatever default stands then.

## 5. Cost of the experiment

Measured on the stored run `router2-run1`: the retrieval answer call averages about 1,950 prompt tokens and 110 completion tokens; the rest of a retrieval request (classifier, reranker, topic call) costs about $0.0005 and stays on luna; the judge costs about $0.0046 per question.

| Per pass of 42 questions | judge | answers | other steps | pass total |
|---|---|---|---|---|
| A0 gpt-6-luna | $0.19 | $0.01 | $0.02 | about **$0.22** |
| A1 gpt-6.1-sol | $0.19 | $0.21 | $0.02 | about **$0.42** |
| A2 gpt-6-astra | $0.19 | $1.05 | $0.02 | about **$1.26** |

- **Recommended (A0 and A1, three passes each): about $1.9** (3 x 0.22 + 3 x 0.42). Well inside the $3 budget; I would set the runner's `--budget` to $2.50, and the tool prints a dry-run estimate before any paid call.
- A2 with three passes would be about $3.8 more, which breaks the $3 budget. A2 with one screening pass is about $1.3 (total about **$3.2**); with two passes about $2.5 (total about $4.4). A one-pass arm cannot satisfy B1's "2 of 3 passes" or the noise margin, so a screening pass could only say "worth a full test or not", not "better".
- Optional cross-judge (decision 3): about $0.5 per arm.

**Decisions for the owner:**
1. **Include gpt-6-astra?** My recommendation: no for now. Run A0 and A1 (about $1.9). Add astra later, with its own three passes, only if A1 shows a clear gain and you want to know whether more helps (it costs about $3.8 and would need your approval of a bigger budget). If you want it now: one screening pass, about $1.3, total about $3.2 (slightly over the stated $3).
2. **Margin and cost ceiling** (B1 0.05, B5 $0.01 per request for A1): accept or change before the run.
3. **Cross-judge** (gpt-5.5, about $0.5 per arm): yes or no.
4. **Daily cap consequence** (next section): accept that a better, dearer model may mean a higher cap or the model used only on the retrieval route (which is what this plan does).

## 6. What it does to the cost per request and per day

Per retrieval-route request (answer step switched, other steps unchanged): today about $0.00075 (answer $0.00025, rest $0.0005). With gpt-6.1-sol about **$0.0055** (answer about $0.005): 7 times higher. With gpt-6-astra about **$0.026**: 35 times higher. Calendar and chain requests do not call the answer model (calendar: classifier and selector only, about $0.0005; chain: classifier only, about $0.00004), so they cost the same as today.

Against the planned **$1.00 daily cap** (retrieval requests only, all other costs ignored): luna about 1,300 per day; sol about 180 per day; astra about 38 per day. A real mix (calendar and chain questions are about a third of dev questions) lifts these numbers a little. For a student portfolio demo 180 questions a day is plenty, 38 is tight; that is why astra gets a lower bar to clear (B5) only if the owner waives it.

## 7. How the winning arm doubles as the "before" arm of step 3b

Step 3b (answer-prompt formatting rule, `answer.format_rule: off | on`, F1 to F6 in `docs/decisions.md`) needs a "before" arm: three judged passes with the old prompt, on the current code, on the 42 retrieval-route dev questions, **on the model that will be in use**. Its F4 compares judged scores of the same model with and without the rule, so a 3b baseline measured on luna would be the wrong baseline if sol wins.

So: the winning arm's three runs here (old prompt, current code, same ids, `format_rule` not yet existing = off) are used as 3b's "before" arm, provided (a) the 3b ids are the same 42, (b) the 3b code step proves by hash that the answer prompt with `format_rule: off` is byte-identical to today's, (c) nothing else in the pipeline changed in between. This saves 3 judged passes: about **$0.66 if luna stays** (3 x $0.22) or about **$1.3 if sol wins** (3 x $0.42), and it removes the risk of a second baseline drifting from the first. 3b then needs only its "after" arm (three passes with the rule on, the same model): about $0.66 or $1.3 instead of $1.3 or $2.5. If the winner changes the default model in between, the "before" arm is exactly the winner's arm, so no run is repeated.

## 8. Order

1. **3a** calendar layout: done (`1ca08af`, results in `docs/chain-layout-results.md`).
2. **This experiment:** step 0 (key, flag, tests, probe; free) with your go; then the paid arms (about $1.9) with your go; then I show you the results, the changed questions and the cost, and you decide.
3. **3b** formatting rule, reusing the winner's runs as its "before" arm; the 3b code and its pre-registration are committed first.

Nothing in this plan changes a default until you say so.
