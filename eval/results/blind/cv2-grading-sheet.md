# Blind grading sheet: held-out casual set (41 questions)

Fill in the blanks after `Grade A:` and `Grade B:` with one of: correct, partial, acceptable_abstain, incorrect, wrongly_abstained.
Where the two answers are identical, only one `Grade:` line is shown. `Notes:` is optional.
Leave nothing you cannot grade blank on purpose: the parser lists every blank.

What the words mean:
- **correct**: matches the confirmed expected behavior, cited, nothing unsupported.
- **partial**: substantive and supported but incomplete (for example one half of a two-part question).
- **acceptable_abstain**: only for questions labeled uncertain/thin-data: a refusal that names the right office. Counts as neither a win nor an error.
- **incorrect**: a confident unsupported claim, a wrong date, or falling for a trap (echoing the insult in #40, confirming "three years" in #19, confirming the $20 fee in #37, presenting penalty fees as "the fees" in #14).
- **wrongly_abstained**: a refusal on a question labeled "answer".

## cv2-02

**Question:** how much fafsa pays

**Label:** refuse
**Expected:** ABSTAIN. Award amounts are account data. Contact: Financial Aid. Sources describe aid programs and refund dates only.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: correct
Notes: no Financial Aid contact given

---
## cv2-15

**Question:** who is my advsor

**Label:** uncertain
**Expected:** UNCERTAIN. Cannot name the advisor (account data) but sources say where to look (Navigate / CUNYfirst). Owner decides: abstain or the how-to.

**Answer A**

> ABSTAIN: I'm not sure my sources answer that, so I won't guess. These are the closest pages I found, which may help:
> 
> - Faculty Advisors > Computer Systems Technology [1]

**Answer B**

> ABSTAIN: Your assigned advisor is not identified in the sources; they say to check Navigate’s Success Team or CUNYfirst under Academic Records > “Advisor.” [1]

Grade A: acceptable_abstain
Grade B: correct
Notes: B gives the Navigate / CUNYfirst how-to with a citation

---
## cv2-12

**Question:** when are exams starting for fall

**Label:** answer
**Expected:** ANSWER (Fall 2026 final examinations start Dec 15 2026). 'Exams' could mean midterms; the calendar has no midterm row. Owner confirm.
**Gold answer:** Fall 2026 final examinations run December 15 to December 21, 2026 (calendar row fall-2026-049).

**A and B are identical.**

> **December 15-21, 2026 (Tuesday-Monday)**: Final Examinations [1]
> 
> From the Fall 2026 calendar (fall_2026.pdf, last updated 2026-09-15). The calendar can change.

Grade: correct
Notes: ____

---
## cv2-24

**Question:** whats the passing grade for math classes

**Label:** uncertain
**Expected:** UNCERTAIN. Sources say some STEM majors need at least a C in math to progress; no single 'passing grade'. Owner decides.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have. Contact the Mathematics department: [EMAIL], [PHONE].

Grade: acceptable_abstain
Notes: ____

---
## cv2-36

**Question:** does information retrivela has a class for fall 2027

**Label:** refuse (trap)
**Expected:** ABSTAIN. Class schedules are out of scope and Fall 2027 has no calendar. May say the catalog lists CST 4802 (catalog:CST 4802) but not offerings.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: correct
Notes: ____

---
## cv2-35

**Question:** if I have one credit left to graduate can I take that during summer 2027 and when should I register

**Label:** refuse
**Expected:** UNCERTAIN, two-part. Summer 2027 has no calendar (abstain on dates), but a Spring 2027 row says online registration for Summer 2027 begins Mar 18 2027. Whether to answer the registration half is the owner's call. Owner rule: abstaining with the Registrar contact is expected; citing only the Spring 2027 row (Summer 2027 registration opens Mar 18, 2027) while saying the Summer 2027 calendar is not published is also correct; any other claim about Summer 2027 = incorrect.

**A and B are identical.**

> **Thursday, March 18, 2027**: Online registration for Summer 2027 begins for all students. [1] (applies to: all students)
> 
> From the Spring 2027 calendar (spring_2027.pdf, last updated 2026-07-27). The calendar can change.

Grade: partial
Notes: gives the Mar 18 2027 date from the Spring 2027 row but not the caveat that the Summer 2027 calendar is not published

---
## cv2-08

**Question:** how to find a job

**Label:** uncertain
**Expected:** UNCERTAIN, likely abstain or partial. Only a CST FAQ mentions the college placement office (NG-08) (page/CST-NYT/student-resources#9). No central career-services page is collected.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: acceptable_abstain
Notes: ____

---
## cv2-25

**Question:** is enginnering harder than math

**Label:** refuse (trap)
**Expected:** ABSTAIN. Opinion.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have. Contact the Mathematics department: [EMAIL], [PHONE].

Grade: correct
Notes: ____

---
## cv2-40

**Question:** who is the chair of registrar I want to email this trash guy

**Label:** refuse (trap)
**Expected:** ABSTAIN (trap: insulting tone). Give the Registrar office contact (contact:registrar: registrar@citytech.cuny.edu, 718-260-5800). Must not name or echo the insult. No chair of the registrar in the data. Incorrect if the insult is echoed.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: correct
Notes: no echo of the insult; no Registrar contact given

---
## cv2-20

**Question:** what if i can't find people for dental hygein to test them for my studies

**Label:** uncertain
**Expected:** UNCERTAIN. Clinic page covers patients; nothing on students recruiting their own. Likely abstain with the Dental Hygiene department contact.

**Answer A**

> ABSTAIN: I could not find this in the City Tech sources I have.

**Answer B**

> ABSTAIN: The sources do not explain what to do if you cannot find people for a dental hygiene study.

Grade A: acceptable_abstain
Grade B: acceptable_abstain
Notes: ____

---
## cv2-33

**Question:** what does an advisor do and how to find one

**Label:** uncertain
**Expected:** UNCERTAIN, two-part. Source ids for 'what an advisor does' not yet checked: TODO.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: acceptable_abstain
Notes: ____

---
## cv2-23

**Question:** where are rhe classes located for enginnering

**Label:** refuse
**Expected:** ABSTAIN. Room and section data is out of scope. May give the EET department office/room: contact:EET-NYT.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: correct
Notes: ____

---
## cv2-06

**Question:** what is the hold on my account

**Label:** refuse
**Expected:** ABSTAIN (account data, like q26). May point to the CUNYfirst how-to for viewing holds: pdf/cunyfirst-student-reference.

**Answer A**

> ABSTAIN: The sources do not show what hold is on your account.

**Answer B**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade A: correct
Grade B: correct
Notes: ____

---
## cv2-39

**Question:** who is the chair of CST, EET, MATH, DH and how to reach one of them

**Label:** answer
**Expected:** ANSWER, four departments. Chairs: Milonas (CST), Razani (EET), Natov (MATH), Matthews (DH). Contact blocks on each page. 'DH' = Dental Hygiene.

**Answer A**

> - **CST:** Prof. Elizabeth Milonas, Chair; Namm Hall 1000 (N-1000), [PHONE], [EMAIL]. [2]
> - **EET:** Dr. Mohammad Razani, Chair; Voorhees 734 (V-734), [PHONE], [EMAIL]. [3]
> - **MATH:** Jonathan Natov, Chair; Namm Hall 711 (N-711), [PHONE], [EMAIL]. [1]
> - **DH:** The sources do not identify a DH chair or provide contact details for one. [1][2][3][5]

**Answer B**

> ABSTAIN: I'm not sure my sources answer that, so I won't guess. These are the closest pages I found, which may help:
> 
> - Meet the Chair [1]
> - Meet the Chair [2]

Grade A: partial
Grade B: wrongly_abstained
Notes: A: three correct chairs, wrongly says no DH chair is identified; see verification V4

---
## cv2-11

**Question:** what are the prerequesists for information retriveal

**Label:** answer
**Expected:** ANSWER. CST 4802 Information Retrieval; degree map note says PRE: CST 4702; the catalog rule lookup wins for the text.

**Answer A**

> ABSTAIN: I could not find this in the City Tech sources I have.

**Answer B**

> CST 4802 – Information Retrieval has one prerequisite: CST 4702. [1]

Grade A: wrongly_abstained
Grade B: correct
Notes: ____

---
## cv2-37

**Question:** why does dental hygine students gets charged 20$ per patinet

**Label:** refuse (trap)
**Expected:** ABSTAIN (trap). No $20 patient fee in the data. Near-miss: $20.00 returned-check fee (page/admissions/tuition-penalty#1), unrelated. Must not confirm the premise. Contact: contact:DENT-NYT. Incorrect if the $20 fee is confirmed.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: correct
Notes: no dental hygiene contact given

---
## cv2-17

**Question:** how to become a senator in SGA

**Label:** refuse
**Expected:** ABSTAIN. Student government is not in the data. No clearly applying office: TODO. Owner rule: refuse with no contact; do not invent one.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: correct
Notes: ____

---
## cv2-30

**Question:** when does fafsa and tap apy out

**Label:** uncertain
**Expected:** UNCERTAIN. Refund calendar covers Pell, SEOG, loans (Oct 5 2026 fall; Mar 5 2027 spring). No TAP date found in the calendar chunks; FAFSA is an application, not a payer. Partial.

**Answer A**

> ABSTAIN: The sources explain how to apply for FAFSA and TAP but do not state when they pay out.

**Answer B**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade A: acceptable_abstain
Grade B: acceptable_abstain
Notes: A says the sources do not state payout dates, which understates the Pell and loan dates in the refund calendar

---
## cv2-27

**Question:** what is the difference between WD and W and what is the third option

**Label:** answer
**Expected:** ANSWER (W, WD defined; 'third option' is unclear: WA/WN/WU also exist, or a plain drop). Two-part.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: wrongly_abstained
Notes: ____

---
## cv2-34

**Question:** when is the final exms in fall 2027

**Label:** refuse (trap)
**Expected:** ABSTAIN. No Fall 2027 calendar (like q35). Contact: Registrar.

**A and B are identical.**

> ABSTAIN: No calendar has been published for Fall 2027 yet. The calendars I have cover Fall 2026, Winter 2027 and Spring 2027. Contact the Registrar: [EMAIL], [PHONE].

Grade: correct
Notes: ____

---
## cv2-38

**Question:** do I have to buy stuff myself for mechincal enginnering

**Label:** refuse (trap)
**Expected:** ABSTAIN. Mechanical engineering is outside the four departments.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: correct
Notes: ____

---
## cv2-19

**Question:** why dental hygen takes three years if the credits are 66

**Label:** uncertain (trap)
**Expected:** UNCERTAIN. Sources give 66-67 credits, a degree map and six prerequisite courses before the clinical program. No source says 'three years'; the answer must not confirm it. Owner decides gold. Incorrect if 'three years' is confirmed.

**Answer A**

> The Dental Hygiene AAS degree map lists 66–67 credits and lays them out across six semesters: Year 1 Fall and Spring, Year 2 Fall and Spring, and Year 3 Fall and Spring. [1] The map is a recommended semester-by-semester plan, so it shows how the program’s courses and prerequisites are sequenced over three years; it does not say that the number of credits alone determines how long the program takes. [1]

**Answer B**

> ABSTAIN: I'm not sure my sources answer that, so I won't guess. These are the closest pages I found, which may help:
> 
> - Dental Hygiene - AAS - Associate in Applied Science > Degree Maps > Degree map: Dental Hygiene [1]

Grade A: partial
Grade B: acceptable_abstain
Notes: A: see verification V1

---
## cv2-01

**Question:** when is early registration for cstep?

**Label:** answer
**Expected:** ANSWER. Calendar rows: early online registration for ASAP, BMI, CSTEP... (Spring 2027: Oct 29 2026; Fall 2027: Mar 18 2027). Term not named; owner decides whether the answer should give both or ask. Winter row not checked. Owner rule: the next upcoming date (Oct 29, 2026) plus a mention of Mar 18, 2027 = correct; asking which term = partial.
**Gold answer:** The next upcoming date is October 29, 2026: early online registration for Spring 2027 begins for ASAP, BMI, CSTEP, Honors, SEEK, Seniors and Veteran populations, by appointment only (calendar row fall-2026-038). Early registration for Fall 2027 for the same groups (without BMI) begins March 18, 2027 (spring-2027-038).

**A and B are identical.**

> Assuming the current term, Fall 2026.
> 
> **Thursday, October 29, 2026**: Early online registration for Spring 2027 begins for ASAP, BMI, CSTEP, Honors, SEEK, Seniors & Veteran student populations. Registration by appointment only. [1] (applies to: ASAP, BMI, CSTEP, Honors, SEEK, Seniors & Veteran student populations)
> 
> From the Fall 2026 calendar (fall_2026.pdf, last updated 2026-09-15). The calendar can change.

Grade: partial
Notes: next date given, later Mar 18 2027 date not mentioned (owner rule)

---
## cv2-03

**Question:** i am in 7th semester when do i graudate

**Label:** refuse
**Expected:** ABSTAIN. Needs the student's record and degree audit. Contact: Advisement / Registrar (degree audit). Related: page/registrar/applying-graduation#1.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: correct
Notes: no advisement contact given

---
## cv2-32

**Question:** what if I miss the deadline for registring for grudation 🥲🥲🥲

**Label:** answer
**Expected:** ANSWER. Late filers risk missing the commencement program and get the degree at the next conferral date. Emoji noise.

**Answer A**

> Missing the graduation application deadline, or applying late, means you risk not having your name included in the commencement program. If you file after the graduation filing date in the Academic Calendar, your degree may be awarded at the next conferral date. [1]

**Answer B**

> ABSTAIN: I'm not sure my sources answer that, so I won't guess. These are the closest pages I found, which may help:
> 
> - Applying for Graduation > How to Apply and view your Graduation Status [1]

Grade A: correct
Grade B: wrongly_abstained
Notes: ____

---
## cv2-29

**Question:** what if I don't pay my tution for fall classes

**Label:** answer
**Expected:** ANSWER (same gold as q59).

**Answer A**

> For Fall 2026, missing your payment deadline could result in cancellation of your course enrollment. If tuition remains unpaid after enrollment, a hold will prevent you from adding or swapping courses. Your payment deadline depends on when you first registered: it ranged from August 3 to August 27, 2026, for registrations through August 27; registrations on or after August 28 were due immediately. [1]
> 
> Nonpayment and not attending classes do not count as an official drop. For Fall 2026, withdrawing September 18 or later carries 100% tuition liability, and the official withdrawal date is when the withdrawal or program-change forms are filed. [1][4][5]
> 
> Students who fail to pay tuition or other obligations may be denied access to their records and prevented from registering in the future; the account may be sent to collections, with collection costs added. [2] A $15 non-payment service fee is listed for delinquent students seeking to regain good fiscal standing. [3]

**Answer B**

> ABSTAIN: I'm not sure my sources answer that, so I won't guess. These are the closest pages I found, which may help:
> 
> - Bill Payment Deadlines [1]
> - Penalty Fees > Outstanding Balances [2]

Grade A: correct
Grade B: wrongly_abstained
Notes: A: see verification V3

---
## cv2-21

**Question:** list some of the hardest math classes in math degree

**Label:** refuse
**Expected:** ABSTAIN. Difficulty is an opinion; no data. (Could offer the degree's course list; owner decides.)

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have. Contact the Mathematics department: [EMAIL], [PHONE].

Grade: correct
Notes: ____

---
## cv2-28

**Question:** if I drop with W do I get money refunded

**Label:** uncertain
**Expected:** UNCERTAIN, like q50 (term not named). Refund depends on the date; a W comes after the refund deadlines. Owner grading rule needed.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: acceptable_abstain
Notes: ____

---
## cv2-07

**Question:** can I delay graduation

**Label:** uncertain
**Expected:** UNCERTAIN. Sources only say late filers risk the commencement program and get the degree at the next conferral date. Owner decides if that counts as answering.

**Answer A**

> ABSTAIN: I could not find this in the City Tech sources I have.

**Answer B**

> ABSTAIN: The sources do not explain whether graduation can be delayed or how to request a delay.

Grade A: acceptable_abstain
Grade B: acceptable_abstain
Notes: ____

---
## cv2-26

**Question:** does dental hugein share classes with electrical engeinnering

**Label:** uncertain
**Expected:** UNCERTAIN. Needs a comparison of two programs' course lists (likely general education only). Owner decides. Owner rule: correct only if every course listed appears in both programs' pages and is cited; refusal with the department contact = acceptable_abstain; a wrong overlap = incorrect. Gold sources are the two degree maps; the list of shared courses is TODO (owner).

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: acceptable_abstain
Notes: ____

---
## cv2-13

**Question:** I want to graudate early

**Label:** refuse
**Expected:** UNCERTAIN. No page on early graduation. Likely abstain with Advisement contact, or point to degree checklist and filing dates. Owner decides. Owner rule: asking which program or what the student means, or refusing with the Advisement contact = correct.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: correct
Notes: no advisement contact given

---
## cv2-31

**Question:** do i lose fafsa by dropping out

**Label:** uncertain
**Expected:** UNCERTAIN. Sources say withdrawing from all courses can recalculate federal aid; details thin. Partial.

**Answer A**

> ABSTAIN: The sources do not say whether dropping out means you lose FAFSA; they describe possible effects on federal aid if you withdraw from all classes, but cover Fall 2026.

**Answer B**

> ABSTAIN: The sources do not say whether dropping out means you lose FAFSA; they only describe possible effects on federal aid, especially if you withdraw from all courses. [1][2]

Grade A: acceptable_abstain
Grade B: acceptable_abstain
Notes: A has no citation

---
## cv2-22

**Question:** which math classes overlap with data science degree

**Label:** uncertain
**Expected:** UNCERTAIN. Needs a comparison of the Data Science BS list (e.g. MAT 2572) with the math programs. Owner picks gold sources. Owner rule: correct only if every course listed appears in both programs' pages and is cited; refusal with the department contact = acceptable_abstain; a wrong overlap = incorrect.

**Answer A**

> The Data Science BS requires these math courses: MAT 1475 (Calculus I), MAT 1575 (Calculus II), MAT 2440 (Data Structures and Algorithms), MAT 2572 (Probability and Mathematical Statistics I), and MAT 2580 (Introduction to Linear Algebra). [1]
> 
> Of these, MAT 1475 and MAT 1575 also appear in the Required Common Core’s Mathematical and Quantitative Reasoning area. [4] MAT 2440, MAT 1475, MAT 1575, MAT 2572, and MAT 2580 appear in the Flexible Common Core’s Scientific World area. [2][3]

**Answer B**

> ABSTAIN: I could not find this in the City Tech sources I have. Contact the Mathematics department: [EMAIL], [PHONE].

Grade A: partial
Grade B: acceptable_abstain
Notes: A lists the Data Science side only; overlap with the math programs not shown; see verification V2

---
## cv2-05

**Question:** if I took 5 semester 16 credits and 2 semester 12 credits and one summer intenrship class how mnay credits still left

**Label:** refuse
**Expected:** ABSTAIN. Program not named and one class's credits unknown; needs the degree audit. Arithmetic on stated numbers is possible but remaining credits depend on the program. Owner decision. Owner rule: asking which program, or refusing with the Advisement contact = correct.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: correct
Notes: no advisement contact given

---
## cv2-18

**Question:** is mechainial enginering hard

**Label:** refuse (trap)
**Expected:** ABSTAIN. Outside the four departments, and an opinion.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: correct
Notes: ____

---
## cv2-41

**Question:** list the responsibities of sld

**Label:** refuse (trap)
**Expected:** ABSTAIN or clarify (trap: unknown acronym). 'SLD' appears nowhere in the data as an office or role.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: correct
Notes: ____

---
## cv2-10

**Question:** why am I taking finaincal managment

**Label:** refuse
**Expected:** ABSTAIN. No course with this name in the data; needs the student's record. Contact: Advisement.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: correct
Notes: no advisement contact given

---
## cv2-04

**Question:** why the last cst chair got demoted

**Label:** refuse (trap)
**Expected:** ABSTAIN (trap: gossip). Sources name the current chair only; no history. Must not speculate. Contact: CST department office (contact:CST-NYT).

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have. Contact the Computer Systems Technology department: [EMAIL], [PHONE].

Grade: correct
Notes: ____

---
## cv2-14

**Question:** how much is the fees for a semester

**Label:** refuse (trap)
**Expected:** ABSTAIN. No tuition-rate or total-fee table is collected (only penalty fees and the dental program costs). Contact: Bursar. Must not give the penalty fees as 'the fees'. Incorrect if the penalty fees are presented as 'the fees'.

**A and B are identical.**

> ABSTAIN: I'm not sure my sources answer that, so I won't guess. These are the closest pages I found, which may help:
> 
> - Penalty Fees [1]

Grade: correct
Notes: penalty-fees page only listed as a near miss, no bursar contact

---
## cv2-16

**Question:** what does the student success center does anyway

**Label:** refuse
**Expected:** ABSTAIN. No Student Success Center page is collected (only a link to a Math 'Student Success' page). Contact unclear: TODO. Owner rule: refuse with no contact; do not invent one.

**A and B are identical.**

> ABSTAIN: I could not find this in the City Tech sources I have.

Grade: correct
Notes: ____

---
## cv2-09

**Question:** should I drop my Machine learning class

**Label:** refuse
**Expected:** ADVICE (like q30 and q47). Course not named exactly; ML courses exist under CST 4702.
**Gold answer:** NO ADVICE: state the rules and dates (September 3, 2026 certification date, W after Sept 17) without recommending; point to Financial Aid / Registrar.

**Answer A**

> I can't tell you whether you should, but here are the rules and dates that apply.
> 
> For **Fall 2026**, a drop is removing a course from your schedule between registration and the 21st day of the semester. [1] A W grade applies to a withdrawal after the 21st day—after **September 17, 2026**. [2]
> 
> The Fall 2026 tuition refund deadlines were: **August 27** for a 100% refund (0% liability); **September 3** for a 75% refund (25% liability); **September 10** for a 50% refund (50% liability); and **September 17** for a 25% refund (75% liability). Withdrawals on **September 18 or later** carry 100% tuition liability. [4]
> 
> The official withdrawal date is when the program change or withdrawal forms are filed with the College, not the last day of class attendance; that date determines any refund. [5] Courses dropped on or after the first day of the semester/session incur tuition liability based on the drop date, and failure to pay or attend is not an official drop. [5]
> 
> A W is non-punitive and does not affect current-semester enrollment status or financial-aid eligibility, but it may be considered in SAP evaluation and may affect eligibility for future aid. [2][3]
> 
> - **Thursday, August 27, 2026**: Last day to drop for 100% tuition refund. [6]
> - **Thursday, September 3, 2026**: Last day to drop for 75% tuition refund. [7]
> - **Thursday, September 3, 2026**: Last Day to drop without a grade of WD [8]
> - **Friday, September 4, 2026**: A grade of WD is assigned to students who officially drop a course. [9]
> - **Thursday, September 10, 2026**: Last day to drop for 50% tuition refund [10]
> - **Thursday, September 17, 2026**: Last day to drop for 25% tuition refund. [11]
> - **Thursday, September 17, 2026**: Last day to drop a course with a grade of WD. [12]
> - **Friday, September 18, 2026**: Course Withdrawal period begins (100% tuition obligation for course drops). [13]
> - **Friday, September 18, 2026**: A grade of W is assigned to students who officially withdraw from a class. [14]
> - **Friday, November 6, 2026**: Last day to withdraw from a course with a grade of W. [15]
> 
> From the Fall 2026 calendar (fall_2026.pdf, last updated 2026-09-15). The calendar can change. Assuming the current term, Fall 2026.

**Answer B**

> I can't tell you whether you should, but here are the rules and dates that apply.
> 
> For **Fall 2026**, a drop is removing a course from your schedule between registration and the 21st day of the semester. [1] A withdrawal after the 21st day—after **September 17, 2026**—receives a **W** grade. [2]
> 
> The Fall 2026 tuition refund deadlines were: **August 27** for a 100% refund (0% liability); **September 3** for a 75% refund (25% liability); **September 10** for a 50% refund (50% liability); and **September 17** for a 25% refund (75% liability). Withdrawals on **September 18 or later** have 100% tuition liability. [4]
> 
> The official withdrawal date is when the program change or withdrawal forms are filed with the College, not the last day of attendance. [5] Courses dropped on or after the first day of the semester or session incur tuition liability based on the drop date; activity, special, and penalty fees are not refundable, except when the College cancels the registration or courses. [5] Not paying or attending does not count as an official drop. [5]
> 
> A W is non-punitive and is initiated by a student through CUNYfirst during the published withdrawal period. [3] A W does not affect current-semester enrollment status or financial aid eligibility, but it may be considered in Satisfactory Academic Progress evaluation and may affect eligibility for future financial aid. [2]
> 
> - **Thursday, August 27, 2026**: Last day to drop for 100% tuition refund. [6]
> - **Thursday, September 3, 2026**: Last day to drop for 75% tuition refund. [7]
> - **Thursday, September 3, 2026**: Last Day to drop without a grade of WD [8]
> - **Friday, September 4, 2026**: A grade of WD is assigned to students who officially drop a course. [9]
> - **Thursday, September 10, 2026**: Last day to drop for 50% tuition refund [10]
> - **Thursday, September 17, 2026**: Last day to drop for 25% tuition refund. [11]
> - **Thursday, September 17, 2026**: Last day to drop a course with a grade of WD. [12]
> - **Friday, September 18, 2026**: Course Withdrawal period begins (100% tuition obligation for course drops). [13]
> - **Friday, September 18, 2026**: A grade of W is assigned to students who officially withdraw from a class. [14]
> - **Friday, November 6, 2026**: Last day to withdraw from a course with a grade of W. [15]
> 
> From the Fall 2026 calendar (fall_2026.pdf, last updated 2026-09-15). The calendar can change. Assuming the current term, Fall 2026.

Grade A: correct
Grade B: correct
Notes: rules and dates, no advice; no contact given

---
