# Eval data

Nothing here is edited by hand after a run. The numbers in the main README come from these files.

## Question files
- `questions.jsonl`: the labelled questions (id, question, gold answer, gold sources, type, department,
  split dev or test, optional tags). The owner wrote or reviewed every one. The test split was run once
  with the code frozen (git tag `final-run-frozen`).
- `questions_casual_v2.jsonl`: a second, held-out set of casual-wording questions (split `heldout`).
- `judge_labels.json`: owner verdicts on stored answers, used to check the judge model.

## results/
One JSON file per run (config, git commit, and one record per question: retrieval, route, answer
checks, cost, latency). They are frozen: change a number and the README no longer reproduces.
- Final run: `final-run.json` (test split), `final-run-pass2.json` (second judge pass),
  `final-run-owner-grades.json` (owner grades for answers the judge left ungraded),
  `final-run-answers.jsonl` (the answer texts; the database log is purged after 30 days).
- `final-config-dev.json`: the dev split with the final configuration. `casual-b0.json`: casual-round baseline.
- Earlier baselines the README mentions: `baseline.json`, `baseline-dev.json`, `baseline-dev-60.json`,
  `baseline-dev-60-v3.json`, `baseline-final.json`, `ms1-old.json`, `ms1-new.json`, `cv2-dev-fix.json`.
- Dev runs that tests read as stored data: `tester1-*`, `4b-run1..3`, `chain-code-run1,2`,
  `router-run1..3`, `router2-run1..3`.
- `blind/`: the blind grading sheet, key and owner grades of the version 2 casual held-out set (cv2).

Older run files were deleted in the cleanup; they are in git at tag `pre-cleanup`.

## How to read them
- `python3 scripts/readme_numbers.py` and `python3 scripts/recompute_final.py final-run` print the
  README numbers from these files.
- `uv run python -m cta.eval.compare OLD.json NEW.json` compares two retrieval runs.
