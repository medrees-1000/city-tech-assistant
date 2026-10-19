# Step 4b plan: prerequisite-chain tool in the router (written 2026-10-12, before any code or paid call of this step)

Dev split only. The test split is not run, read or opened. Nothing below is tuned after results: if a fix looks needed it is reported and the step stops. The classifier prompt v2 (`src/cta/graph/prompts/classify_v2.txt`) and the chain answer prompt (`src/cta/graph/prompts/chain_answer.txt`) are committed with this plan, before the first paid call, and are not edited after seeing results.

## The change

- **Classifier v2** (used only when `router.chain` is `on`; with `off` the 4a classifier text is unchanged): the output becomes `{"intent": "calendar" | "prerequisite" | "other", "term_mention": ...}`. `prerequisite` means the question asks which courses are required before a specific course, or for its prerequisite chain; it is not `prerequisite` for a description, credits, schedule, who teaches it, or general degree requirements. The text is `prompts/classify_v2.txt` (the 4a text plus the `prerequisite` paragraph).
- **A new graph node `chain`** after `classify` for `prerequisite`: it extracts one course code or one exact course title from the question, calls the chain lookup, and passes the result to a chain answer step. The calendar and retrieve routes are unchanged. Edges: `classify -> calendar | chain | retrieve`; `chain -> END | retrieve` (fall-through).
- **The chain lookup is a LangChain `@tool`** (`from langchain_core.tools import tool`), reason in `docs/decisions.md`: it replaces hand-written tool plumbing (name, description, argument schema, one `invoke`); no new dependency (`langchain-core` is installed with `langgraph`). If a new package were needed, the step would stop and ask.
- **Switch:** `router.chain: "off" | "on"` (default `"off"`, quoted), `CTA_ROUTER_CHAIN`, and `--chain on|off` on `run_answers`.

## The walk (plain code, deterministic, no model)

The expansion rules of `docs/chain-candidates.md`: course codes come from the record's resolved prerequisite text (an explicit code, or a bare number after a code taking its prefix, which is recorded); no expansion of a code after "MUST NOT", "NOT HAVE" or "NOT" in the same clause (an exclusion: listed, not followed); breadth-first with a visited set (cycles end); **depth at most 4** (level 0 is the asked course); **at most 15 courses with a catalog record**; non-course conditions (placement, proficiency, GPA, approval, eligibility, major, degree) kept as text; UNPARSED text (shorthand such as `PRE_CST1100_CST1101`, or truncated) shown verbatim and nothing expanded; a code with no record in the 197 records is shown as "no record" and not expanded (it does not count toward the 15). Prerequisite texts are verbatim; the tool never decides AND/OR or which alternative applies; corequisite wording is not separated (as in the candidates).
**Truncation:** if the depth limit or the 15-course cap cuts the chain, the result records exactly which courses were not expanded (a chain course at level 4 whose text names codes, with those codes) and which named codes were not added because of the cap. That note goes to the answerer inside the prompt, not as a numbered source.

## Extraction

Exactly one distinct course code in the question (case and spacing normalised: `cst2412`, `CST 2412`; a repeated mention counts once; words such as seasons are not prefixes) **or**, if there is no code, exactly one exact, case-insensitive, unique course title among the 197 records found as a whole phrase in the question. Two or more distinct codes, a title that belongs to more than one record, several titles, or neither: **fall through to the existing retrieve route** (route `chain_fallthrough`). A code with **no record** in the 197: **abstain directly** ("ABSTAIN: ...no record exists in the catalog data for the four departments (CST, Math, EET, Dental Hygiene)"), no contact yet (step 4c adds contacts).

## The chain answer step

Each chain course with a record is a numbered source (`id` = `catalog:<CODE>`, the form eval gold sources use) holding its record text as the existing course chunk shows it. The user message lists the chain order (level, code, source number), the no-record codes, the exclusions, the conditions and any truncation note. The system prompt is `prompts/chain_answer.txt`. Same model, temperature and top_p as the existing answer step (`answer` section of `config/models.yaml`). The abstain threshold does not apply to this route.

## Logging

No migration: the existing `request_logs.route` takes the values `chain`, `chain_fallthrough` and `abstain`, and the existing `router` JSON column holds `{"chain": {"code", "course_count", "truncated", "unexpanded", "fallthrough", ...}}`.

## Measures (dev only; the sets are computed from `eval/questions.jsonl` at run time and printed in the report)

- **CH** = dev questions tagged `chain` whose type is not `unanswerable`. Today: q22 q39 q40 q76 q77 q79 q81 q85. **AB** = q83. **CTRL** = every other dev question (q87 is in it).
- **M1** CH questions **answered by the chain node** (final route `chain`). Also reported: classifier intent `prerequisite`.
- **M2** CTRL questions answered by the chain node (final route `chain`, or the chain abstain), each id listed. Also reported: CTRL questions with classifier intent `prerequisite` that fell through (route `chain_fallthrough`), each id listed. *Interpretation fixed now:* a control question that the classifier calls `prerequisite` but whose extraction fails (two codes, no code) ends in the unchanged retrieve route and is not counted in M2. Its count is reported so the other reading can be seen.
- **M3** chain coverage: for CH questions with 2 or more gold catalog sources (today q39 q40 q76 q77 q85), the share where every gold source was among the sources the answerer received (`request_logs.retrieved`, which holds the ids of the numbered sources).
- **M4** the 13 calendar-only dev questions under calendar scoring v2 (`--calendar-scoring 2`) and wrong rows.
- **M5** judged correctness and faithfulness (judge v3, unchanged) on the 48 dev ids common to the router2 runs: correct share among the judged normal-gold questions.
- **M6** q83 abstained.
- **Extras (no rule):** p50 and p95 latency of the `chain` route, tokens and cost per route, the classifier's cost change against router2.

## Keep rule (all must hold)

- **R1** q87 is not answered by the chain node in 3 of 3 runs, and M2 lists at most 1 other id.
- **R2** M1 misses at most 1 CH question per run.
- **R3** (i) M3 is at least 0.80 in every run; (ii) the mean M3 over the 3 runs, on the CH questions with 2 or more gold sources that the router2 logs also contain, is higher than the router2 mean M3 on the same questions (computed from `router2-run1..3` request logs, which do hold the received-sources ids). The router2 runs ran before q76 to q87 existed, so that set is {q39, q40}; the router2 runs never ran q76 q77 q79 q81 q85, which is stated in the report.
- **R4** M4 is at least 12 of 13 in every run, 0 wrong rows, and no calendar misroute (an `other`-gold question sent to the calendar node) beyond q09, q13, q30.
- **R5** the mean M5 over 3 runs is not lower than the router2 mean minus 0.03.
- **R6** q83 abstains in 3 of 3 runs.

Otherwise **REJECT**: `router.chain` stays off and the result is written up.

## Predictions written before the run (not rules)

- **q39's gold cannot be reproduced by the walk.** Its gold has MAT 1275 and MAT 1275CO at level 5, beyond the depth limit of 4 (the same holds for q41 in the test split, which is not used here). The walk will truncate there and say so, so M3 for q39 is expected to be a miss; with 5 questions in M3, 0.80 then allows no other miss.
- **q21 and q42 are prerequisite questions that carry no `chain` tag** (they sit in CTRL). q21 (one code) is expected to be answered by the chain node and will be the one other id R1 allows; q42 has two codes and is expected to fall through.
- Course golds of q22 (root only) are shorter than the chain; q22 is not in M3.

## Run plan

3 runs over the dev split (55 questions), the same command and judge settings as the router2 runs, router selector 2, rerank pool_a, chain on, calendar scoring 2, labels `4b-run1`, `4b-run2`, `4b-run3`, `--budget 2.00` (the step's allowance, counting these three labels). Expected cost $1.00 to $1.50; if the estimate from `router2-run1`'s cost fields for 3 runs exceeds $1.50 the step stops before any run.
```
uv run python -m cta.eval.run_answers --split dev --label 4b-run1 --router on --selector 2 --chain on --calendar-scoring 2 --rerank pool_a --budget 2.0 --budget-labels 4b-run1,4b-run2,4b-run3 --yes
```

## Caveats written in advance

Dev questions only; 8 CH questions, one control that is a clear non-chain question, one abstain; the same model classifies and answers; three runs; the judge's faithfulness verdicts are unreliable on "the sources do not state X" answers (`docs/step4-judge-results.md`), so read faithfulness differences of one or two questions as noise; the golds were generated by the same rule as the walk and checked against the raw JSON, which makes the dry check circular for the code-set part (Part 3), though it is independent of the answerer.
