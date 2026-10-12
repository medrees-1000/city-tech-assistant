# Gold-answer evidence check (for the owner)

For each candidate whose gold states facts, the draft gold answer is split into sentences and each is compared with the sentences of its gold source text (standard-library `difflib` plus the share of the draft sentence's words found in one source sentence). A sentence is **found** if at least 75% of its words appear in one source sentence or the similarity ratio is at least 0.60; otherwise it says **NOT FOUND: check**. Rule sentences (the CLARIFY / NO ADVICE scoring rule and the 'names at least 3' rule) are listed but not checked. This is an aid to your review, not a replacement: a sentence can score well and still be wrong in a detail (a number, a negation), and a combined sentence can score low and be right.

## q40 — Starting from CST 3613 (Application Development with Database), which courses do I have to take first, and what do those courses require?

| # | Draft sentence | Closest source sentence | ratio | words found | result |
|---|---|---|---|---|---|
| 1 | CST 3613 (App. Development with Database) requires CST 1201 (Programming Fundamentals) and CST 1204 (Database Systems Fundamentals) | `catalog:CST 1204`: CST 1204 - Database Systems Fundamentals. | 0.47 | 53% | **NOT FOUND: check** |
| 2 | catalog text: “PREREQUISITE OF CST 1201, CST 1204 WITH A GRADE OF C OR HIGHER”. | `catalog:CST 3613`: Prerequisites: PREREQUISITE OF CST 1201, CST 1204 WITH A GRADE OF C OR HIGHER | 0.86 | 87% | found |
| 3 | CST 1201 (Programming Fundamentals) requires CST 1100 (Intro to Computer Systems) and CST 1101 (Problem Solving Comp. Program) | `catalog:CST 1100`: CST 1100 - Intro to Computer Systems. | 0.44 | 44% | **NOT FOUND: check** |
| 4 | catalog text: “PRE: FOR CST MAJORS: CST 1100 & 1101, C GRADE / PRE: FOR NON-CST MAJORS: CST 1101”. | `catalog:CST 1201`: Prerequisites: PRE: FOR CST MAJORS: CST 1100 & 1101, C GRADE | 0.62 | 83% | found |
| 5 | CST 1100 (Intro to Computer Systems) has no prerequisite course. | `catalog:CST 1100`: CST 1100 - Intro to Computer Systems. | 0.72 | 60% | found |
| 6 | CST 1101 (Problem Solving Comp. Program) has no prerequisite course. | `catalog:CST 1101`: CST 1101 - Problem Solving Comp. | 0.62 | 50% | found |
| 7 | CST 1204 (Database Systems Fundamentals) requires CST 1100 (Intro to Computer Systems). | `catalog:CST 1100`: CST 1100 - Intro to Computer Systems. | 0.59 | 67% | **NOT FOUND: check** |

## q42 — What are the prerequisites for MAT 1190CO, and how are they different from MAT 1190?

| # | Draft sentence | Closest source sentence | ratio | words found | result |
|---|---|---|---|---|---|
| 1 | MAT 1190CO: Pre- or corequisite of ENG 1101 OR ENG 1101ML OR ENG 1101CO. | `catalog:MAT 1190CO`: Prerequisites: Pre- or corequisite of ENG 1101 OR ENG 1101ML OR ENG 1101CO. | 0.85 | 86% | found |
| 2 | MAT 1190: CUNY proficiency in mathematics. | `catalog:MAT 1190`: The course incorporates opportunities within the classroom to develop students' reading, writing, oral, and listening skills in a mathematical context.SATISFIES REQUIRED CORE- MATH & QUANTITATIVE REASONING Prerequisites: CUNY pro… | 0.23 | 67% | **NOT FOUND: check** |
| 3 | Pre/corequisite: ENG 1101 or prerequisite: ENG 1101CO or ENG 1101ML.* Students who already have credit for MAT 1275CO or MAT 1275 or higher will not receive credit for this course | `catalog:MAT 1190`: Pre/corequisite: ENG 1101 or prerequisite: ENG 1101CO or ENG 1101ML.* Students who already have credit for MAT 1275CO or MAT 1275 or higher will not receive credit for this course | 1.00 | 100% | found |
| 4 | Difference: MAT 1190 requires CUNY proficiency in mathematics and adds a note that students with credit for MAT 1275CO, MAT 1275 or higher will not receive credit for it | `catalog:MAT 1190CO`: Students who already have credit for MAT 1275CO or MAT 1275 or higher will not receive credit for this course. | 0.59 | 52% | **NOT FOUND: check** |
| 5 | MAT 1190CO lists only the pre- or corequisite of ENG 1101, ENG 1101ML or ENG 1101CO. | `catalog:MAT 1190CO`: Prerequisites: Pre- or corequisite of ENG 1101 OR ENG 1101ML OR ENG 1101CO. | 0.78 | 69% | found |

## q43 — What are the prerequisites for EET 2171, and are they the same as for EET 2162?

| # | Draft sentence | Closest source sentence | ratio | words found | result |
|---|---|---|---|---|---|
| 1 | The prerequisites differ. | `catalog:EET 2171`: Prerequisites: PRE: EET 1202, EET 1241 | 0.51 | 33% | **NOT FOUND: check** |
| 2 | The two courses have identical descriptions, but titles, credits and rules differ. | `catalog:EET 2171`: Fundamentals of digital electronics using Boolean algebra, truth tables, Karnaugh maps and waveforms to analyze and understand digital logic circuit design. | 0.34 | 8% | **NOT FOUND: check** |
| 3 | EET 2171 (Projects Laboratory, 1 credit): PRE: EET 1202, EET 1241 | `catalog:EET 2171`: EET 2171 - Projects Laboratory. | 0.64 | 55% | found |
| 4 | EET 2162 (Digital Electronics I, 3 credits): PRE: EET 1240, EET 1241 | `catalog:EET 2162`: EET 2162 - Digital Electronics I. | 0.65 | 58% | found |

## q47 — Should I take an Incomplete or withdraw from my class?

| # | Draft sentence | Closest source sentence | ratio | words found | result |
|---|---|---|---|---|---|
| 1 | NO ADVICE: state the rules, do not choose for the student. | (rule, not checked) | | | |
| 2 | An Incomplete (INC) is for a student who has completed a majority of the coursework but cannot complete the whole course for reasons beyond their control, usually 1-2 assignments or exams that amount to 25% or less of the final g… | `page/registrar/incomplete#1`: An incomplete is typically assigned when a student has satisfactorily completed a majority of the coursework, but for reasons beyond their control cannot complete the entire course. | 0.62 | 60% | found |
| 3 | if no grade change form is submitted the INC converts to an FIN, a failing grade | `page/registrar/incomplete#1`: If no grade change form is submitted, the grade will convert automatically to an “FIN,” a failing grade. | 0.85 | 88% | found |
| 4 | students cannot graduate in a semester in which they have an incomplete. | `page/registrar/incomplete#1`: Students cannot graduate in a semester in which they have an incomplete. | 1.00 | 100% | found |
| 5 | A W (Official Withdrawal) is a non-punitive grade when a class is dropped via CUNYfirst during the published withdrawal period. | `page/registrar/grade-policies#1`: W - Official Withdrawal A non-punitive grade initiated by a student when a class is dropped via CUNYfirst during the published withdrawal period. | 0.89 | 100% | found |

## q48 — Should I sign up for the Nelnet payment plan?

| # | Draft sentence | Closest source sentence | ratio | words found | result |
|---|---|---|---|---|---|
| 1 | NO ADVICE: state the facts, do not say whether to enrol. | (rule, not checked) | | | |
| 2 | Payment plan options are available for Fall, Spring and Summer terms prior to the start of the semester | `page/bursar/payment-plan#1`: Payment plan options are available for Fall, Spring and Summer terms prior to the start of the semester. | 1.00 | 100% | found |
| 3 | enrol in CUNYfirst (Student Center, Financial Account, Account Balance, Payment Plan link). | `page/bursar/payment-plan#1`: On the Account Balance page, click the Payment Plan link. | 0.56 | 50% | **NOT FOUND: check** |
| 4 | Fall 2026 plans: enrolling April 8 - June 22 gives 5 payments (July - Nov), June 23 - July 22 gives 4, July 23 - Aug 24 gives 3, Aug 25 - Sept 04 gives 2 | `page/bursar/payment-plan#3`: June 23 — July 22 4 Aug — Nov | 0.28 | 42% | **NOT FOUND: check** |
| 5 | payments are due on the 5th of the month. | `page/bursar/payment-plan#3`: Enrollment Dates. (1st Payment Due Upon Enrollment) Number of payments. (Includes Down Payment) Months of payments. (5th of Month Payment Due) | 0.35 | 56% | **NOT FOUND: check** |
| 6 | There are no payment plans for past-due balances. | `page/bursar/payment-plan#3`: There are no Payment Plans for past-due balances. | 1.00 | 100% | found |

## q49 — Can I take a class at another college?

| # | Draft sentence | Closest source sentence | ratio | words found | result |
|---|---|---|---|---|---|
| 1 | CLARIFY OR BOTH: either ask whether the other college is in CUNY or outside CUNY, or answer both cases correctly from the sources; never give one answer as if it applied to both. | (rule, not checked) | | | |
| 2 | Facts | (rule, not checked) | | | |
| 3 | CUNY college: file an ePermit in CUNYfirst | `page/registrar/epermit#1`: City Tech students who wish to take a course at a CUNY College other than their HOME College will need to file for an ePermit using CUNYfirst. | 0.45 | 86% | found |
| 4 | eligibility rules include not being on Academic Probation, being matriculated and currently in attendance, not being newly admitted, no holds, immunizations complete. | `page/registrar/epermit#1`: Must be matriculated and currently in attendance. | 0.45 | 23% | **NOT FOUND: check** |
| 5 | Outside CUNY: a Non-CUNY Permit Form needs approval from the Registrar and the academic department, and a Consortium Agreement is needed for financial aid | `page/registrar/epermit#2`: The Non-CUNY Permit Form requires approval/signature of a financial aid counselor or staff member. | 0.45 | 48% | **NOT FOUND: check** |
| 6 | only a grade of C or higher is acceptable. | `page/registrar/epermit#2`: Only a grade of C or higher is acceptable from a non-CUNY school course. | 0.73 | 100% | found |

## q50 — How much of my tuition do I get back if I drop a class?

| # | Draft sentence | Closest source sentence | ratio | words found | result |
|---|---|---|---|---|---|
| 1 | CLARIFY OR STATE THE TERM: ask which term and when, or state the Fall 2026 (current term) schedule with the term named and say it differs by term and date; never give one percentage without the term. | (rule, not checked) | | | |
| 2 | Facts, Fall 2026 (Bursar page) | (rule, not checked) | | | |
| 3 | drop by August 27, 2026 for a 100% refund | `page/bursar/refund-policy#4`: August 27, 2026 Last day to drop classes for 100% tuition refund; 0% Liability | 0.51 | 78% | found |
| 4 | by September 03 75% | `page/bursar/refund-policy#4`: September 03, 2026 Last day for 75% tuition refund; 25% Liability | 0.38 | 75% | found |
| 5 | by September 10 50% | `page/bursar/refund-policy#4`: September 10, 2026 Last day for 50% tuition refund; 50% Liability | 0.38 | 75% | found |
| 6 | by September 17 25% | `page/bursar/refund-policy#4`: September 17, 2026 Last day for 25% tuition refund: 75% Liability | 0.38 | 75% | found |
| 7 | withdrawing September 18 and after means 100% liability. | `page/bursar/refund-policy#4`: 100% Liability Withdraw September 18th and thereafter | 0.58 | 50% | **NOT FOUND: check** |
| 8 | No portion of the student activity fee, special fees or penalty fees is refundable. | `page/bursar/refund-policy#1`: No portion of the student activity fee, special fees or penalty fees is refundable, except in cases where the student's registration or courses are canceled by the College. | 0.65 | 100% | found |

## q51 — How many times a year does the clinical Dental Hygiene program accept a class, and when are students told?

| # | Draft sentence | Closest source sentence | ratio | words found | result |
|---|---|---|---|---|---|
| 1 | The program accepts one class each year, beginning in the Fall semester. | `page/DENT-NYT/faq#25`: The clinical Dental Hygiene program accepts one class each year, beginning in the Fall semester. | 0.85 | 100% | found |
| 2 | The class is selected after Spring final grades are submitted, and the entering Fall class is notified within the first two weeks of June. | `page/DENT-NYT/faq#24`: The entering Fall class is notified within the first two weeks of June. | 0.68 | 67% | found |
| 3 | Students taking summer classes or planning to transfer during the summer are not eligible for the entering Fall class. | `page/DENT-NYT/faq#24`: Students taking summer classes or planning to transfer during the summer will not be eligible for admission to the entering Fall class. | 0.91 | 95% | found |

## q52 — Do the science prerequisites for the Dental Hygiene program expire?

| # | Draft sentence | Closest source sentence | ratio | words found | result |
|---|---|---|---|---|---|
| 1 | Yes. | `page/DENT-NYT/faq#12`: Yes. | 1.00 | 100% | found |
| 2 | All science courses, including BIO2311, BIO2312, and CHEM, must have been completed within five years of acceptance into the program. | `page/DENT-NYT/faq#12`: All science courses, including BIO2311, BIO2312, and CHEM, must have been completed within five years of acceptance into the program. | 1.00 | 100% | found |

## q53 — Who advises continuing students and readmitted students, and what happens to TAP if my major is still undeclared?

| # | Draft sentence | Closest source sentence | ratio | words found | result |
|---|---|---|---|---|---|
| 1 | Continuing students (second semester and onward) and newly readmitted students are advised by their current academic department. | `page/advisement/continuing-students#1`: Continuing students (second semester and onward), as well as our newly readmitted student population, are advised by their current academic department. | 0.90 | 100% | found |
| 2 | If your major is listed as undeclared, TAP eligibility can be jeopardized if you have more than 30 credits in an associate program, or more than 60 credits in a bachelor's program. | `page/advisement/continuing-students#1`: If your major is currently listed as undeclared, TAP eligibility can be jeopardized if you have more than 30 credits in an associate program, or more than 60 credits in a bachelor's program. | 0.97 | 100% | found |
| 3 | If you have reached 30 or 60 credits, you must formally declare a major before the 21st day of the semester. | `page/advisement/continuing-students#1`: If you have reached 30 or 60 credits, you must formally declare a major before the 21st day of the semester. | 1.00 | 100% | found |

## q54 — What happens if I fail a math course?

| # | Draft sentence | Closest source sentence | ratio | words found | result |
|---|---|---|---|---|---|
| 1 | When you pass the course again, a grade of C or higher replaces the failing grade in your GPA calculations, but the failed course remains on your transcript. | `page/MATH-NYT/faqs#12`: When you pass the course, a grade of "C" or higher will replace the failing grade in your grade point average (GPA) calculations (however, the failed course will remain on your transcript). | 0.86 | 86% | found |
| 2 | The FAQ recommends re-taking the course the very next semester (or over the summer if you fail it in the spring), using the tutoring services and your professor's office hours, looking at the prerequisites to your other required … | `page/MATH-NYT/faqs#12`: You will also need to look at the prerequisites to your other required courses and talk with a faculty advisor in your department to make adjustments to your plan for the next semester. | 0.53 | 53% | **NOT FOUND: check** |

## q55 — Which community colleges have articulation agreements with the Computer Systems Technology department?

| # | Draft sentence | Closest source sentence | ratio | words found | result |
|---|---|---|---|---|---|
| 1 | Borough of Manhattan, Queensborough, LaGuardia, Guttman, Kingsborough and Bronx. | `page/CST-NYT/transfer-policies#1`: The department has articulation agreements with the following community colleges: Borough of Manhattan, Queensborough, LaGuardia, Guttman, Kingsborough and Bronx. | 0.65 | 100% | found |
| 2 | Students from these colleges who finished an AAS in a computer major named in the agreement are exempt from the CST AAS-level courses, except that a missing prerequisite for the chosen track must be completed at the BTech level, … | `page/CST-NYT/transfer-policies#1`: Students from these colleges who have completed an AAS degree in a computer major indicated in the articulation agreement, will be exempt from completing the CST AAS level course with the following exceptions: | 0.14 | 57% | **NOT FOUND: check** |

## q56 — What internship and research opportunities does the Electrical and Telecommunications Engineering Technology department list for students?

| # | Draft sentence | Closest source sentence | ratio | words found | result |
|---|---|---|---|---|---|
| 1 | Names at least 3 opportunities from this list and invents none | (rule, not checked) | | | |
| 2 | Reaching a New Energy Sciences Workforce (RENEW) | `page/EET-NYT/student-resources#14`: Reaching a New Energy Sciences Workforce (RENEW) | 1.00 | 100% | found |
| 3 | Brookhaven National Laboratory: A Research Opportunity | `page/EET-NYT/student-resources#14`: Brookhaven National Laboratory: A Research Opportunity | 1.00 | 100% | found |
| 4 | NASA Pathways Programs and OSSI SOLAR Internships | `page/EET-NYT/student-resources#14`: NASA Pathways Programs and OSSI SOLAR Internships | 1.00 | 100% | found |
| 5 | PVEDI Engineering, Architecture & Geology, DPC. | `page/EET-NYT/student-resources#14`: PVEDI Engineering, Architecture & Geology, DPC. | 1.00 | 100% | found |
| 6 | Making a Successful Transition from College to Career | `page/EET-NYT/student-resources#14`: Making a Successful Transition from College to Career | 1.00 | 100% | found |
| 7 | National Oceanic and Atmospheric Administration (NOAA) | `page/EET-NYT/student-resources#14`: National Oceanic and Atmospheric Administration (NOAA) | 1.00 | 100% | found |
| 8 | NASA Applied Sciences Develop National Program | `page/EET-NYT/student-resources#14`: NASA Applied Sciences Develop National Program | 1.00 | 100% | found |
| 9 | Dr. | `page/EET-NYT/student-resources#14`: Dr. | 1.00 | 100% | found |
| 10 | Baruh's Presentation | `page/EET-NYT/student-resources#14`: Baruh's Presentation | 1.00 | 100% | found |
| 11 | EPA - Fellowship Programs | `page/EET-NYT/student-resources#14`: EPA - Fellowship Programs | 1.00 | 100% | found |
| 12 | Internship and Fellowship Opportunities | `page/EET-NYT/student-resources#14`: Internship and Fellowship Opportunities | 1.00 | 100% | found |
| 13 | EPA P3 Competition | `page/EET-NYT/student-resources#14`: EPA P3 Competition | 1.00 | 100% | found |
| 14 | Internship and Fellowship Seminar | `page/EET-NYT/student-resources#14`: Internship and Fellowship Seminar | 1.00 | 100% | found |
| 15 | NASA Student Opportunities | `page/EET-NYT/student-resources#14`: NASA Student Opportunities | 1.00 | 100% | found |
| 16 | CIPAIR Presentation | `page/EET-NYT/student-resources#14`: CIPAIR Presentation | 1.00 | 100% | found |
| 17 | Internship-Research Opportunities. | `page/EET-NYT/student-resources#14`: Internship-Research Opportunities | 1.00 | 100% | found |

## q57 — What is the Fresh Start program for students who were dismissed from City Tech?

| # | Draft sentence | Closest source sentence | ratio | words found | result |
|---|---|---|---|---|---|
| 1 | Students dismissed for failing to meet academic standards may appeal for readmission through Fresh Start if they graduated with an Associate's Degree after their dismissal, and must be readmitted into a Baccalaureate program. | `page/registrar/readmission#4`: Students who are dismissed from City Tech for failure to meet the academic standards of the college may appeal for readmission through the Fresh Start Program if they fulfill the following criteria: | 0.59 | 50% | **NOT FOUND: check** |
| 2 | Apply at the Registrar's office in room NG-15 with a readmission form with the Fresh Start box checked and pay the readmission fee. | `page/registrar/readmission#4`: To apply, go to the Registrar's office in room NG-15 and submit a readmission from with the Fresh Start Box checked. | 0.80 | 84% | found |
| 3 | The failing grades from the original record are forgiven and successfully completed coursework counts as transfer credit | `page/registrar/readmission#4`: Once the registrar's office has received all appropriate documentation your record will be updated to forgive all of the failing grades from your original academic record at City Tech. | 0.32 | 41% | **NOT FOUND: check** |
| 4 | this may affect SAP for Federal Title IV funding. | `page/registrar/readmission#4`: If you receive financial aid, this may have an adverse impact on your Satisfactory Academic Progress (SAP) for Federal Title IV Funding. | 0.51 | 89% | found |

## q58 — What is the "What If" feature in DegreeWorks?

| # | Draft sentence | Closest source sentence | ratio | words found | result |
|---|---|---|---|---|---|
| 1 | "What if" is an option on the audit that lets students see how the courses they have taken would apply toward other majors. | `page/registrar/faqs#11`: "What if" is an option on the Audit that allows students to look at how the courses they have taken would apply toward other majors. | 0.92 | 91% | found |
| 2 | It does not change your major or your course history. | `page/registrar/faqs#11`: It does not change your major or your course history; | 1.00 | 100% | found |

## q59 — What happens if I don't pay my tuition bill?

| # | Draft sentence | Closest source sentence | ratio | words found | result |
|---|---|---|---|---|---|
| 1 | Failure to pay tuition and fees by the due date could result in cancellation of course enrollment, and if the tuition remains unpaid after enrollment a hold is placed on the account that prevents adding or swapping courses. | `page/bursar/payment-deadlines#1`: Failure to pay tuition and fees by the due date could result in cancellation of course enrollment. | 0.61 | 58% | found |
| 2 | A student who fails to pay tuition or other obligations is denied access to their records and prevented from registering in the future, and the account is turned over to the College's collection agency. | `page/admissions/tuition-penalty#3`: A student who fails to pay tuition or other obligations will be denied access to his/her records and will be prevented from registering in the future. | 0.75 | 71% | found |
| 3 | The student is responsible for all collection costs, including agency fees, attorney fees and court costs, and non-payment or a default judgment may be reported to credit bureaus. | `page/admissions/tuition-penalty#3`: The student will be responsible for all collection costs, including agency fees, attorney fees and court costs, in addition to whatever amount you owe the College. | 0.69 | 62% | found |
| 4 | Non-payment and not attending courses are NOT considered an official drop. | `page/bursar/payment-deadlines#1`: Also, nonpayment and not attending courses are NOT considered an official drop. | 0.96 | 83% | found |

## q60 — What is the TAP waiver and who can get one?

| # | Draft sentence | Closest source sentence | ratio | words found | result |
|---|---|---|---|---|---|
| 1 | A one-time waiver of the good academic standing requirement in the TAP regulations. | `page/financial-aid/tap-appeal#2`: Students can receive a one-time waiver of the good academic standing requirement specified in TAP regulations as of 1981 and amended in 1996. | 0.70 | 100% | found |
| 2 | It is not automatic: it may only be granted in extraordinary or unusual circumstances beyond the student's control and with a reasonable expectation that the student will meet future requirements. | `page/financial-aid/tap-appeal#2`: It may only be granted in extraordinary or unusual circumstances that are beyond the student's control, and with reasonable expectation that the student will meet future requirements. | 0.92 | 87% | found |
| 3 | To request it, speak to a TAP Counselor in the Financial Aid Office and submit the completed TAP waiver/appeal form. | `page/financial-aid/tap-appeal#2`: Speak to a TAP Counselor in the Financial Aid Office | 0.63 | 62% | found |

## Summary

| Candidate | sentences checked | NOT FOUND |
|---|---|---|
| q40 | 7 | 3 |
| q42 | 5 | 2 |
| q43 | 4 | 2 |
| q47 | 4 | 0 |
| q48 | 5 | 3 |
| q49 | 4 | 2 |
| q50 | 6 | 1 |
| q51 | 3 | 0 |
| q52 | 2 | 0 |
| q53 | 3 | 0 |
| q54 | 2 | 1 |
| q55 | 2 | 1 |
| q56 | 16 | 0 |
| q57 | 4 | 2 |
| q58 | 2 | 0 |
| q59 | 4 | 0 |
| q60 | 3 | 0 |
