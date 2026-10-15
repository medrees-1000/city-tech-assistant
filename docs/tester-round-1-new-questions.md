# Tester round 1: drafted new dev questions (for the owner to review)

**Nothing here is in `eval/questions.jsonl`.** These are drafts for the owner to accept, change or drop; every question needs the owner's review before it enters the file. All rows are `split: "dev"`. The ids are placeholders (`NEW-...`); the owner assigns the real ids. Gold answers use only facts from sources we already hold (the gold of the existing dev question each variant is built from, or the data's own statement that no calendar or record exists); nothing is invented, and unknowns are marked TODO. Question texts come from the tester's rows (the stored text) or are minimal variants of existing dev questions.

## B. Noisy-question variants (markup, emoji, a redaction placeholder)

The plain question and its gold are an existing dev question (q13 and q61). **Expected behaviour is not promised:** in the tester round the cleaned search text moved the similarity toward the plain wording but the four tester questions stayed under the 0.59 cutoff (docs/decisions.md, "Tester round 1, item B"), so some of these may fail until retrieval changes; they are meant to measure that.

```json
{"id":"NEW-B1","question":"<script>alert(1)</script> When is my tuition bill due this fall?","gold_answer":"(the gold of q13)","gold_sources":[{"id":"page/bursar/payment-deadlines#4","source":"https://www.citytech.cuny.edu/bursar/payment-deadlines.aspx","heading":"Bill Payment Deadlines > Fall 2026 Payment Due Dates"},{"id":"page/bursar/payment-deadlines#1","source":"https://www.citytech.cuny.edu/bursar/payment-deadlines.aspx","heading":"Bill Payment Deadlines"}],"type":"time_sensitive","department":null,"split":"dev","note":"Noisy variant of q13 (script tag). Copy q13's gold_answer text when accepted."}
{"id":"NEW-B2","question":"🔥🎓 when is my tuition bill due this fall?? ⁉️⁉️","gold_answer":"(the gold of q13)","gold_sources":[{"id":"page/bursar/payment-deadlines#4","source":"https://www.citytech.cuny.edu/bursar/payment-deadlines.aspx","heading":"Bill Payment Deadlines > Fall 2026 Payment Due Dates"},{"id":"page/bursar/payment-deadlines#1","source":"https://www.citytech.cuny.edu/bursar/payment-deadlines.aspx","heading":"Bill Payment Deadlines"}],"type":"time_sensitive","department":null,"split":"dev","note":"Noisy variant of q13 (emoji). Copy q13's gold_answer text when accepted."}
{"id":"NEW-B3","question":"my phone is [PHONE], when is my tuition bill due this fall?","gold_answer":"(the gold of q13)","gold_sources":[{"id":"page/bursar/payment-deadlines#4","source":"https://www.citytech.cuny.edu/bursar/payment-deadlines.aspx","heading":"Bill Payment Deadlines > Fall 2026 Payment Due Dates"},{"id":"page/bursar/payment-deadlines#1","source":"https://www.citytech.cuny.edu/bursar/payment-deadlines.aspx","heading":"Bill Payment Deadlines"}],"type":"time_sensitive","department":null,"split":"dev","note":"Noisy variant of q13 (a redaction placeholder, as the API passes it on). Copy q13's gold_answer text when accepted."}
{"id":"NEW-B4","question":"<img src=x onerror=alert(1)> What is the last day to add a course in Fall 2026?","gold_answer":"Thursday, September 3, 2026: Last day to add a course. [fall-2026-007] (Fall 2026 calendar, fall_2026.pdf, last updated 2026-09-15; the calendar can change)","gold_sources":[{"id":"fall-2026-007","source":"data/calendar/calendar_events.json","heading":"Fall 2026: Last day to add a course."}],"type":"time_sensitive","department":null,"split":"dev","note":"Noisy variant of q61 (an img tag); a calendar-only gold, scored by row id.","tags":["calendar"]}
```

## C. Terms with no calendar

The data states that only Fall 2026, Winter 2027 and Spring 2027 calendars exist (`config/calendar_terms.yaml`; q34 is the existing example). Gold `ABSTAIN`, as q34 (the runner checks only that the answer starts with `ABSTAIN:`; the new wording is "No calendar has been published for ... yet").

```json
{"id":"NEW-C1","question":"when does summer 2027 semester start","gold_answer":"ABSTAIN","gold_sources":[],"type":"unanswerable","department":null,"split":"dev","note":"The tester's F07 question (5aa6e0dd). No Summer 2027 calendar is published; the assistant must say so and give the Registrar contact, not borrow another term's dates."}
{"id":"NEW-C2","question":"fall 2027 add/drop deadline?","gold_answer":"ABSTAIN","gold_sources":[],"type":"unanswerable","department":null,"split":"dev","note":"The tester's F07 question (4a7e826e). No Fall 2027 calendar is published. TODO (owner): the Spring 2027 calendar has rows that mention Fall 2027 registration, but none for add/drop; confirm ABSTAIN is the wanted gold."}
```

## D. A course outside the four departments

The subject prefix appears in no catalog record we hold. Gold `ABSTAIN` (the runner checks the prefix); the new text names the four departments and the catalog address.

```json
{"id":"NEW-D1","question":"prereq for ENG 1101","gold_answer":"ABSTAIN","gold_sources":[],"type":"unanswerable","department":null,"split":"dev","note":"The tester's F08 question (cb7a1b29). ENG is not a subject of the four departments' catalog records; the answer says so and points to the City Tech catalog. TODO (owner): confirm in the live catalog that ENG 1101 exists (the assistant does not claim it does)."}
{"id":"NEW-D2","question":"What are the prerequisites for BIO 1101?","gold_answer":"ABSTAIN","gold_sources":[],"type":"unanswerable","department":null,"split":"dev","note":"Same pattern with another subject that is not in the data. TODO (owner): confirm the course exists in the live catalog before accepting."}
```

## A. Distress tiers (not drafted)

Skipped: the eval runner scores the pipeline's answers, and the distress, stress and other guardrail replies are written by the API layer before the pipeline runs, so the runner has no way to score them. They are covered by the unit tests (`tests/test_screen.py`: 12 + 10 positives and 22 near-misses) and by the live page checks.

## E. Personal-data note (not drafted)

Also an API-layer behaviour (the note is added after the pipeline answers), so the eval runner would never see it; covered by `tests/test_screen.py`.
