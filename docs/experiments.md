# Experiments (Phase 3)

One entry per experiment, newest last. Protocol: `docs/phase3-plan.md`. Comparison file for dev:
`eval/results/baseline-dev-60.json` (the frozen system on the 40 dev questions; 30 of them are retrieval-scored). Each entry has
the change, the config switch, the metric deltas, cost and latency deltas, the questions that got better or worse, the decision, and
the caveats. A rejected experiment is still logged. The test split is never used to decide.

## Decision rules (written before the run they apply to)

### Step 1, hybrid search (written 2026-10-12, before any hybrid result was computed)

**Retrieval stage** (`run_retrieval --split dev`, 30 retrieval-scored dev questions, vector-only is `baseline-dev-60`):
- **Keep hybrid** if MRR **or** recall@5 improves by at least 0.01 **and** neither of the two drops by more than 0.02.
- Every question whose first relevant rank got better or worse is named (rank before to rank after; "miss" means not in the top 10).
- The chain-tagged row (n = 3) is reported separately and is not part of the rule: it is too small to decide anything.
- Other metrics (recall and hit rate at 1, 3, 10; by type) are reported, not part of the rule.

**Answer stage** (only if retrieval is kept; full answer and judge run on dev, label `hybrid-v1-dev-answers`):
- The change is kept for answers if correctness (normal gold) does not drop by more than one question, faithfulness does not drop by
  more than one question, wrongly abstained does not rise by more than one question, and abstention accuracy does not fall.
- Latency is reported (chat call and retrieval time separately); it is not a keep or reject criterion unless retrieval time grows
  by more than 100 ms at the median.

**Default switch:** `retrieval.mode` becomes `hybrid` by default only if both stages are kept, in a separate commit.

Caveat written in advance: with 30 scored questions one question moves a mean by about 0.03, so a change of 0.01 to 0.02 is below
what the set can resolve. The rule is a guard against obvious regressions, not a significance test.
