# Milestone 1 results (test split, `--final`, 2026-10-13)

Pre-registration: `docs/milestone1-plan.md` (`74fb1de`). Both configurations were run once on all 31 test questions with `--final`, one judge pass (rubric v3, `gpt-5.6-terra`), `eval.today` 2026-10-11, calendar scoring v2 on both. Result files: `eval/results/ms1-old.json`, `eval/results/ms1-new.json`; tables from `scripts/milestone1_report.py`. **Nothing here was used to change anything.** No fixes are proposed.

Run code: commit `74fb1de` (the plan commit; the report script was added afterwards). Costs: OLD **$0.0614**, NEW **$0.0770**, total **$0.1384** of the $0.80 cap (the plan estimated about $0.25). No judge failures, no reranker failures, no budget stop.

**Reading rules.** n is 31 (13 normal-gold judged questions, 7 calendar-only, 7 ABSTAIN-gold, 1 NO ADVICE, the rest CLARIFY or similar "not supported yet"). One question moves a rate by about 3 points (about 8 points on the 13 judged ones). A single answer run is noisy: on dev, runs of one arm differed by up to 2 questions. Faithfulness carries the usual caveat (unreliable on answers that say "the sources do not state X", `docs/step4-judge-results.md`). The old 20 test questions are compared with the stored `baseline-final`, which holds only the original 10 (q02 q07 q10 q11 q17 q20 q23 q25 q26 q29); that comparison is rubric v2 against v3.

## Headline

| metric | OLD | NEW |
|---|---|---|
| retrieval recall@5 (n=14 scored) | 0.636 | 0.724 |
| retrieval precision@5 (n=14 scored) | 0.243 | 0.300 |
| retrieval hit@5 (n=14 scored) | 0.857 | 0.857 |
| retrieval mrr (n=14 scored) | 0.692 | 0.811 |
| correctness, normal gold (n: counts) | 13: 4 correct / 3 partial / 6 incorrect | 13: 9 correct / 3 partial / 1 incorrect |
| faithfulness, normal gold (n: counts) | 13: 13 yes / 0 partly / 0 no | 13: 12 yes / 1 partly / 0 no |
| abstention | 7 of 7 ABSTAIN-gold abstained; wrongly abstained 7 of 14 answerable | 7 of 7 ABSTAIN-gold abstained; wrongly abstained 2 of 14 answerable |
| NO ADVICE gold | q48 correct | q48 incorrect |
| calendar-only, scoring v2 (n: counts) | 7: 0 correct / 0 partial / 7 incorrect | 7: 7 correct / 0 partial / 0 incorrect |
| failure labels | {'abstention error': 1, 'calendar missed': 7, 'generation error': 1, 'not supported yet': 3, 'not supported yet (chained prerequisite)': 1, 'ranking miss': 1, 'retrieval miss': 5} | {'abstention error': 1, 'generation error': 1, 'not supported yet': 3, 'not supported yet (chained prerequisite)': 1, 'retrieval miss': 2} |
| cost per request | 0.00198; run total $0.0614 (judge 0.0587; answer incl. router calls and rerank 0.0027) | 0.00248; run total $0.0770 (judge 0.0615; answer incl. router calls and rerank 0.0155) |
| latency total median / p95 ms | 21 / 2414 | 2670 / 8605 |

## By type

| type | n | OLD correct / partial / incorrect (normal gold) | NEW | OLD abstained / NEW abstained |
|---|---|---|---|---|
| lookup | 4 | 4: 2 correct / 1 partial / 1 incorrect | 4: 2 correct / 1 partial / 1 incorrect | 1 / 1 |
| multi_chunk | 7 | 7: 1 correct / 2 partial / 4 incorrect | 7: 5 correct / 2 partial / 0 incorrect | 4 / 0 |
| time_sensitive | 8 | 1: 1 correct / 0 partial / 0 incorrect | 1: 1 correct / 0 partial / 0 incorrect | 7 / 0 |
| ambiguous | 3 | 0: 0 correct / 0 partial / 0 incorrect | 0: 0 correct / 0 partial / 0 incorrect | 2 / 1 |
| unanswerable | 9 | 1: 0 correct / 0 partial / 1 incorrect | 1: 1 correct / 0 partial / 0 incorrect | 9 / 8 |

## NEW by route

| route (NEW) | n | latency median / p95 ms | answer + router + rerank cost per request | judge cost per request |
|---|---|---|---|---|
| abstain | 4 | 2168 / 2670 | 0.00008 | 0.00000 |
| calendar | 9 | 2087 / 4235 | 0.00045 | 0.00025 |
| calendar_fallthrough | 1 | 5661 / 5661 | 0.00145 | 0.00000 |
| chain | 6 | 3182 / 8605 | 0.00029 | 0.00434 |
| chain_fallthrough | 1 | 3146 / 3146 | 0.00097 | 0.00379 |
| other | 10 | 3865 / 10584 | 0.00134 | 0.00295 |

## Chain questions

| id | OLD correctness / faithfulness | NEW route, correctness / faithfulness | gold catalog sources in what the answerer received (OLD, NEW) |
|---|---|---|---|
| q78 (multi_chunk) | incorrect / yes | chain, correct / yes | 1/3, 3/3 |
| q80 (multi_chunk) | incorrect / yes | chain, correct / yes | 1/3, 3/3 |
| q82 (unanswerable) | incorrect / yes | chain, correct / partly | no gold, no gold |
| q84 (unanswerable) | correct / None | abstain, correct / None | no gold, no gold |
| q86 (multi_chunk) | incorrect / yes | chain, correct / yes | 1/2, 2/2 |

## Contact check (NEW abstentions)

| id | question | path | office added | line added |
|---|---|---|---|---|
| q23 | When is the deadline? | calendar_fallthrough / below_threshold | financial-aid | Contact the Financial Aid office: financialaid@citytech.cuny.edu, 718-260-5700. |
| q25 | When does the Summer 2027 semester start? | abstain / calendar_no_row | registrar | Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q26 | Do I have a hold on my account? | other / below_threshold | financial-aid | Contact the Financial Aid office: financialaid@citytech.cuny.edu, 718-260-5700. |
| q29 | What courses are required for the Architectural Technology degree? | other / model-written | advisement | Contact Advisement: Advisement4u@citytech.cuny.edu (prospective and new students), transferadvisement@citytech.cuny.edu (transfer students). Continuing students can find their department's advisor at https://www.citytech.cuny.edu/advisement/virtual-advisors.aspx |
| q35 | When do final exams start in Fall 2027? | abstain / calendar_no_row | registrar | Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q43 | What are the prerequisites for EET 2171, and are they the same as for EET 2162? | chain_fallthrough / model-written | EET-NYT | Contact the Electrical and Telecommunications Engineering Technology department: electricaltelecomm@citytech.cuny.edu, 718-260-5300. |
| q46 | Who is the chair of the Biological Sciences department? | other / below_threshold | CST-NYT | Contact the Computer Systems Technology department: compsystech@citytech.cuny.edu, 718-260-5170. |
| q48 | Should I sign up for the Nelnet payment plan? | other / below_threshold | bursar | Contact the Bursar: bursar@citytech.cuny.edu. |
| q72 | When do classes begin in Fall 2027? | abstain / calendar_no_row | registrar | Contact the Registrar: registrar@citytech.cuny.edu, 718-260-5800. |
| q84 | What do I need to take before ENG 1101? | abstain / chain_no_record | advisement | Contact Advisement: Advisement4u@citytech.cuny.edu (prospective and new students), transferadvisement@citytech.cuny.edu (transfer students). Continuing students can find their department's advisor at https://www.citytech.cuny.edu/advisement/virtual-advisors.aspx |

## OLD against the stored baseline-final

| id | baseline-final (rubric v2) correctness / faithfulness / abstained | ms1-old (rubric v3) | same? |
|---|---|---|---|
| q02 | correct / yes / False | correct / yes / False | yes |
| q07 | partial / yes / False | partial / yes / False | yes |
| q10 | correct / yes / False | correct / yes / False | yes |
| q11 | incorrect / yes / True | incorrect / None / True | NO |
| q17 | correct / yes / False | partial / yes / False | NO |
| q20 | partial / yes / False | partial / yes / False | yes |
| q23 | None / None / True | None / None / True | yes |
| q25 | correct / None / True | correct / None / True | yes |
| q26 | correct / None / True | correct / None / True | yes |
| q29 | correct / None / True | correct / None / True | yes |

Same verdicts and abstention on 8 of 10.

## NEW failures

**ambiguous**

- q23 [NEW] label: not supported yet; correctness None; faithfulness None; route calendar_fallthrough; abstained True. Q: When is the deadline? A: ABSTAIN: I could not find this in the City Tech sources I have. Contact the Financial Aid office: [EMAIL], [PHONE].
- q50 [NEW] label: not supported yet; correctness None; faithfulness None; route other; abstained False. Q: How much of my tuition do I get back if I drop a class? A: For Fall 2026, the tuition refund depends on the date your withdrawal is officially filed: by August 27, 100%; by September 3, 75%; by September 10, 50%; by September 17, 25%; and from September 18 onward, no tuition ref
- q74 [NEW] label: not supported yet; correctness None; faithfulness None; route calendar; abstained False. Q: What is the last day to drop a class in Fall 2026? A: Thursday, September 17, 2026: Last day to drop a course with a grade of WD. [1] (Fall 2026 calendar, fall_2026.pdf, last updated 2026-09-15; the calendar can change)

**lookup**

- q07 [NEW] label: retrieval miss; correctness partial; faithfulness yes; route other; abstained False. Q: What degrees does the Electrical and Telecommunications Engineering Technology department offer? A: The Electrical and Telecommunications Engineering Technology Department offers an associate in applied science in Electrical Engineering Technology (EET-AAS) and a Bachelor of Technology in Electrical Engineering Technol
- q43 [NEW] label: retrieval miss; correctness incorrect; faithfulness yes; route chain_fallthrough; abstained True. Q: What are the prerequisites for EET 2171, and are they the same as for EET 2162? A: ABSTAIN: The sources do not list the prerequisites for EET 2171 or EET 2162. Contact the Electrical and Telecommunications Engineering Technology department: [EMAIL], [PHONE].

**multi_chunk**

- q17 [NEW] label: generation error; correctness partial; faithfulness yes; route other; abstained False. Q: What do I need to be considered for the clinical Dental Hygiene program? A: To be considered for the clinical Dental Hygiene program, you must complete the six prerequisite courses: ENG 1101 (or an approved corequisite version), MQR, SOC 1101, BIO 2311, BIO 2312, and CHEM 1000 or higher. [2] The
- q41 [NEW] label: not supported yet (chained prerequisite); correctness partial; faithfulness yes; route chain; abstained False. Q: What do I need to take, step by step, before EET 4202? A: **Level 0**

**unanswerable**

- q48 [NEW] label: abstention error; correctness incorrect; faithfulness None; route other; abstained True. Q: Should I sign up for the Nelnet payment plan? A: ABSTAIN: I could not find this in the City Tech sources I have. Contact the Bursar: [EMAIL].
- q82 [NEW] label: -; correctness correct; faithfulness partly; route chain; abstained False. Q: What do I need to take before CST 3508? A: CST 3508’s prerequisite text is `PRE_CST1101_1204_MST2304_MAT13` [1]. It is marked UNPARSED, so its prerequisites cannot be determined from the catalog text [1].


## OLD failures

**ambiguous**

- q23 [OLD] label: not supported yet; correctness None; faithfulness None; route None; abstained True. Q: When is the deadline? A: ABSTAIN: I could not find this in the City Tech sources I have.
- q50 [OLD] label: not supported yet; correctness None; faithfulness None; route None; abstained False. Q: How much of my tuition do I get back if I drop a class? A: For **Fall 2026**, the tuition refund depends on the date your official drop is filed: 100% by August 27; 75% by September 3; 50% by September 10; or 25% by September 17. A withdrawal on September 18 or later has 100% tu
- q74 [OLD] label: not supported yet; correctness None; faithfulness None; route None; abstained True. Q: What is the last day to drop a class in Fall 2026? A: ABSTAIN: The sources say a drop occurs through the 21st day of the semester, but do not give the date of that day.

**lookup**

- q07 [OLD] label: retrieval miss; correctness partial; faithfulness yes; route None; abstained False. Q: What degrees does the Electrical and Telecommunications Engineering Technology department offer? A: The department offers an associate in applied science in Electrical Engineering Technology (ET-AAS) and a bachelor of technology in Electrical Engineering Technology (ETB-BTECH). [3]
- q43 [OLD] label: retrieval miss; correctness incorrect; faithfulness yes; route None; abstained True. Q: What are the prerequisites for EET 2171, and are they the same as for EET 2162? A: ABSTAIN: The sources do not list the prerequisites for EET 2171 or EET 2162.

**multi_chunk**

- q17 [OLD] label: generation error; correctness partial; faithfulness yes; route None; abstained False. Q: What do I need to be considered for the clinical Dental Hygiene program? A: To be considered for the clinical Dental Hygiene program, you must first complete the six prerequisite courses: ENG 1101 (or an approved corequisite version), MQR, SOC 1101, BIO 2311, BIO 2312, and CHEM 1000 or higher. [
- q20 [OLD] label: not supported yet (chained prerequisite); correctness partial; faithfulness yes; route None; abstained False. Q: What do I need to complete before DEN 2400, including the prerequisites of those courses? A: Before DEN 2400, you need to complete DEN 2300, DEN 2311, DEN 2315, and DEN 2318; DEN 2400 also has DEN 2413 as a corequisite. [1]
- q41 [OLD] label: retrieval miss; correctness incorrect; faithfulness yes; route None; abstained True. Q: What do I need to take, step by step, before EET 4202? A: ABSTAIN: I could not find this in the City Tech sources I have.
- q78 [OLD] label: retrieval miss; correctness incorrect; faithfulness yes; route None; abstained True. Q: What do I need to take before MAT 1375? A: ABSTAIN: I could not find this in the City Tech sources I have.
- q80 [OLD] label: retrieval miss; correctness incorrect; faithfulness yes; route None; abstained True. Q: What do I need before MAT 1372, and is there anything I must not have taken? A: ABSTAIN: I could not find this in the City Tech sources I have.
- q86 [OLD] label: ranking miss; correctness incorrect; faithfulness yes; route None; abstained True. Q: What do I need before DEN 1100? A: ABSTAIN: I could not find this in the City Tech sources I have.

**time_sensitive**

- q11 [OLD] label: calendar missed; correctness incorrect; faithfulness None; route None; abstained True. Q: When is the 87th Commencement Ceremony? A: ABSTAIN: I could not find this in the City Tech sources I have.
- q32 [OLD] label: calendar missed; correctness incorrect; faithfulness None; route None; abstained True. Q: What is the last day to drop a class for a 100% tuition refund in Winter 2027? A: ABSTAIN: The sources do not include Winter 2027 refund deadlines.
- q38 [OLD] label: calendar missed; correctness incorrect; faithfulness None; route None; abstained True. Q: What is the deadline to apply for graduation to take part in all commencement activities in Spring 2027? A: ABSTAIN: I could not find this in the City Tech sources I have.
- q62 [OLD] label: calendar missed; correctness incorrect; faithfulness None; route None; abstained True. Q: When does the filing period for Fall 2026 graduation begin? A: ABSTAIN: I could not find this in the City Tech sources I have.
- q66 [OLD] label: calendar missed; correctness incorrect; faithfulness None; route None; abstained True. Q: When does the filing period for Spring 2027 graduation end? A: ABSTAIN: I could not find this in the City Tech sources I have.
- q69 [OLD] label: calendar missed; correctness incorrect; faithfulness None; route None; abstained True. Q: When is spring break this spring? A: ABSTAIN: I could not find this in the City Tech sources I have.
- q73 [OLD] label: calendar missed; correctness incorrect; faithfulness None; route None; abstained True. Q: When does online registration for Fall 2027 begin for all students? A: ABSTAIN: I could not find this in the City Tech sources I have.

**unanswerable**

- q82 [OLD] label: abstention error; correctness incorrect; faithfulness yes; route None; abstained True. Q: What do I need to take before CST 3508? A: ABSTAIN: I could not find this in the City Tech sources I have.


## Resolved NEW config (git rev-parse HEAD at the run: 74fb1def748fcec027428f0226681595227f8d19)

```
{
 "chat_model": "gpt-6-luna",
 "judge_model": "gpt-5.6-terra",
 "answer": {
  "temperature": 0.1,
  "top_p": 0.3,
  "reasoning_effort": "none",
  "k": 5,
  "max_output_tokens": 600,
  "abstain_threshold": 0.59
 },
 "retrieval": {
  "mode": "vector",
  "candidates": 20,
  "rrf_k": 60,
  "dept_filter": "off",
  "rerank": "pool_a"
 },
 "rerank": {
  "temperature": 0,
  "reasoning_effort": "none",
  "max_output_tokens": 600
 },
 "router": {
  "mode": "on",
  "selector": 2,
  "chain": "on",
  "contacts": "on",
  "temperature": 0,
  "reasoning_effort": "none",
  "max_output_tokens": 300
 },
 "eval": {
  "today": "2026-10-11",
  "k_values": [
   1,
   3,
   5,
   10
  ],
  "max_cost_usd": 1.0
 }
}
```


## Reading the tables (counts, no verdicts)

- **OLD against NEW.** On the 13 normal-gold questions: 4 correct / 3 partial / 6 incorrect (OLD) against 9 / 3 / 1 (NEW). OLD abstained on 23 of 31 questions (wrongly on 7 of 14 answerable ones); NEW abstained on 10 (7 ABSTAIN-gold and 2 wrongly, q43 and q48, plus q23). Calendar-only questions: 0 of 7 (OLD: no calendar tool, so no rows) against 7 of 7 with no wrong row (NEW). Chain questions q78 q80 q86 went from incorrect to correct, q82 (UNPARSED rule text) from an abstention error to correct.
- **Retrieval** (14 scored questions; hit@5 is 12 of 14 in both): MRR 0.692 to 0.811, recall@5 0.636 to 0.724. q43 has no gold section in the top 10 in either.
- **Cost and latency.** NEW costs $0.0770 against $0.0614 for the 31 questions (the judge is $0.059 of OLD and $0.062 of NEW). NEW total latency median 2.7 s, p95 8.6 s; OLD median 21 ms (most of its answers are threshold abstentions without a model call) and p95 2.4 s. The NEW p95 comes from the chain and "other" routes.

## Failures: known limits against new findings

Known limits already logged:
- **q41 (NEW partial)**: the walk stopped at depth 4 (`truncated`, MAT 1475 -> MAT 1375 not expanded). Same limit as dev q39.
- **q23, q50, q74 (ambiguous, "not supported yet")**: CLARIFY scoring is step 5; not scored in either configuration.
- **q07 (partial in both)**: omits the Accelerator Science minor; retrieval miss of one gold section. It is on the logged baseline-final list.
- **q17 (partial in both)**: omits the four-semester deadline and the 3.4 GPA; the stored baseline-final graded it correct (rubric v2), OLD now partial (rubric v3 or answer noise; the answer text is similar).
- **OLD failures** (calendar missed 7, retrieval or ranking miss q41 q78 q80 q86, q82 abstention error, q43 miss): the gaps steps 4a and 4b were built for.

New findings (first seen on test):
1. **q48 (NO ADVICE gold, "Should I sign up for the Nelnet payment plan?")**: OLD correct, NEW incorrect. Both abstained at the threshold. The only difference is the contact line; the judge's reason in NEW is "It advises the student to contact the Bursar." So with `router.contacts` on, the NO ADVICE check can read the appended contact sentence as advice. This changes the q47/q49-style behaviour logged for dev: on dev, q47 was never judged this way. Not fixed.
2. **q43 (lookup, two course codes)**: the chain node extracts exactly one course; "EET 2171 and EET 2162" gives `extraction: many`, the question falls through to retrieve, which has neither course in its sources, and the model abstains (with the EET contact line added). OLD abstained too. The "exactly one course per question" rule is by design in step 4b but was not in the known-limits list.
3. **q82 (chain, UNPARSED text)**: judged correctness correct, faithfulness "partly", because the word UNPARSED comes from the chain description, which the judge does not see (it sees only the numbered sources). A judge-visibility artefact, in the family of the known faithfulness caveat but on a different mechanism.
4. **q46 ("Who is the chair of the Biological Sciences department?")** abstained correctly; the contact added is the **Computer Systems Technology department**, chosen by the best-ranked chunk (a CST chair page). **q26 ("Do I have a hold on my account?")** got the Financial Aid office, **q23 ("When is the deadline?")** Financial Aid. See the contact check; the owner judges the offices.

## What surprised me

- The contact line changed a verdict (q48), through the judge, not through the answer.
- The size of OLD's abstention rate (23 of 31) next to its cost advantage: OLD is 20% cheaper per question and wrong far more often on this set.
- NEW answered all 7 calendar-only questions with the right rows, including the Fall 2027 and Summer 2027 abstains (q25 q35 q72 -> Registrar line), on questions it had never seen.
- The best-chunk office map (rule 5) picks CST for a Biological Sciences question, as the dev notes warned for low-similarity chunks.

## Addendum (2026-10-13): contact policy

The contact check above (and every "line added" in it) was made with **contact policy v1**, which also used the best-ranked chunk's owner and a Registrar fallback to choose an office. After manual testing in the chat page showed unrelated cards on low-similarity abstentions, the project moved to **contact policy v2**: a contact only when the office clearly applies (named department or course prefix, account-word cue, calendar abstention, chain no-record for a prefix of the four departments); otherwise no contact. The results, the table and the failure analysis above are not edited. The final milestone will use v2. See `docs/decisions.md` ("Contact policy v2") and `docs/step4c-plan.md` ("v2").
