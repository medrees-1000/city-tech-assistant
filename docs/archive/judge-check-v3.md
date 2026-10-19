# Judge check: rubric v2 against v3 on the stored `baseline-dev-60` answers

The answers are the same in both columns (nothing was regenerated); only the rubric differs. Each question below is one where the correctness or faithfulness verdict changed. The judge's one-line reasons are copied unedited. This file does not say which version is right: check them by hand against the gold answer and the sources.
Questions with a changed verdict: **3** of 40.


## q01 (lookup)

**Question:** How do I apply for graduation at City Tech?

**Gold answer:** Check your Degree Audit with an advisor first: you are ready to graduate once you have 60+ credits for an associate degree or 120+ for a bachelor's, a GPA of 2.0 or better, and have completed credits in residency, the Writing Intensive requirement, overall liberal arts and science credits, General Education (Pathways) and major requirements. The page links a PDF, 'Steps to apply for Graduation in CUNYfirst', for how to apply. Apply by the graduation filing date in the Academic Calendar: students who apply late may not have their names in the commencement program and may have their degree awarded at the next conferral date.

| | v2 | v3 |
|---|---|---|
| correctness | partial | correct |
| correctness reason | It correctly explains applying through CUNYfirst, the alternate portal process, and deadline consequences, but omits the requested/important step of checking the Degree Audit with an advisor and the eligibility requirements. | It accurately explains the CUNYfirst application route, the alternate Registrar Portal process, and the filing-deadline consequences asked about. |
| faithfulness | yes | yes |
| faithfulness reason | All claims in the answer are supported by sources [1] and [4]. | All claims are supported by sources [1] and [4]. |

## q52 (lookup)

**Question:** Do the science prerequisites for the Dental Hygiene program expire?

**Gold answer:** Yes. All science courses, including BIO2311, BIO2312, and CHEM, must have been completed within five years of acceptance into the program.

| | v2 | v3 |
|---|---|---|
| correctness | incorrect | incorrect |
| correctness reason | The answer abstains even though the requested policy is that all science prerequisites must be completed within five years of acceptance. | The answer abstains despite the requested conclusion being that all science prerequisites, including BIO2311, BIO2312, and CHEM, expire after five years. |
| faithfulness | yes | no |
| faithfulness reason | Its limited statement accurately reflects source [5], which explicitly gives a five-year age limit for chemistry courses, and it makes no unsupported factual assertion. | It falsely claims the sources only provide a five-year limit for chemistry, whereas source [5] does state that chemistry expires but the broader assertion about what the sources state is unsupported by the provided excerpts. |

## q56 (lookup)

**Question:** What internship and research opportunities does the Electrical and Telecommunications Engineering Technology department list for students?

**Gold answer:** Names at least 3 opportunities from this list and invents none: Reaching a New Energy Sciences Workforce (RENEW); Brookhaven National Laboratory: A Research Opportunity; NASA Pathways Programs and OSSI SOLAR Internships; PVEDI Engineering, Architecture & Geology, DPC.; Making a Successful Transition from College to Career; National Oceanic and Atmospheric Administration (NOAA); NASA Applied Sciences Develop National Program; Dr. Baruh's Presentation; EPA - Fellowship Programs; Internship and Fellowship Opportunities; EPA P3 Competition; Internship and Fellowship Seminar; NASA Student Opportunities; CIPAIR Presentation; Internship-Research Opportunities.

| | v2 | v3 |
|---|---|---|
| correctness | incorrect | partial |
| correctness reason | The answer does not name at least three of the department's listed internship and research opportunities from the required list. | It identifies an internship course and faculty research areas, but it does not name at least three of the listed internship and research opportunities required by the reference answer. |
| faithfulness | yes | yes |
| faithfulness reason | Its claims about EET 2000 and faculty research areas are supported by sources [2] and [4]. | All details about EET 2000 and the faculty research areas are supported by sources [2] and [4]. |

## Not changed (stated because the v3 rubric was written for them)

q22 and q40 were expected to change from faithfulness "no" to "yes" and **did not**: both stay "no" under v3. The v3 judge's reason for q22 is the same sentence as under v2 (the claim that the sources do not specify the
prerequisites is called unsupported/contradicted), and for q40 it now says the answer "contradicts source [5]" and that its claim about CST 1201 is unsupported. Whether that is right is for the owner to check against the five sources shown;
this file does not decide it. The three verdicts that did change (q01, q52, q56) are in questions the v3 wording was not written for, so they are likely judge noise; the judge-repeat run in `docs/experiments.md` (step 3b) measures how
much the judge moves on identical answers.
