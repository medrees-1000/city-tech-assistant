# Calendar verification

> This is the pre-verification review sheet. All 136 rows were verified by the owner on 2026-10-11.

Written by `uv run python -m cta.parse.calendar_build`. Check every row against the PDF,
tick the last column, then set `verified: true` for that event in
`data/calendar/calendar_events.json`. All rows are `verified: false` until you do.

- Printed date and day are exactly as printed. Parsed date is the resolved date (the year
  comes from the term).
- Text in **bold** in the Event column is bold in the PDF.
- Weekday check compares the printed day with the weekday of the parsed date. Dates are
  never changed to make them match.

## Fall 2026

Source: `data/pdfs/fall_2026.pdf`, title "FALL 2026 ACADEMIC CALENDAR*", last updated 2026-09-15 (printed "Last updated: 9/15/26"). 55 events.

| # | Printed date | Printed day | Event text | Parsed date | Weekday check | OK |
|---|---|---|---|---|---|---|
| 1 | July 09 | Thursday | Deadline for Course and Standards Appeals Submission (students dismissed Fall 2025 or earlier for potential Fall 2026 return). | 2026-07-09 | ok | [ ] |
| 2 | July 09 | Thursday | For more info :- www.citytech.cuny.edu/registrar/course-standard.aspx | 2026-07-09 | ok | [ ] |
| 3 | August 21 | Friday | Last day to file ePermit request | 2026-08-21 | ok | [ ] |
| 4 | August 27 | Thursday | Last day to drop for 100% tuition refund. | 2026-08-27 | ok | [ ] |
| 5 | August 28 | Friday | **Start of Fall 2026 term.** | 2026-08-28 | ok | [ ] |
| 6 | August 28 | Friday | Classes begin | 2026-08-28 | ok | [ ] |
| 7 | September 03 | Thursday | **Last day to add a course.** | 2026-09-03 | ok | [ ] |
| 8 | September 03 | Thursday | Last day to drop for 75% tuition refund. | 2026-09-03 | ok | [ ] |
| 9 | September 03 | Thursday | **Last day to opt-in for Credit/No-Credit grades for Spring 2026 and Summer 2026 classes.** | 2026-09-03 | ok | [ ] |
| 10 | September 03 | Thursday | Financial Aid Certification Enrollment Status Date. | 2026-09-03 | ok | [ ] |
| 11 | September 03 | Thursday | Last Day to drop without a grade of WD | 2026-09-03 | ok | [ ] |
| 12 | September 04 | Friday | **Verification of Enrollment (VOE) Rosters available to faculty.** | 2026-09-04 | ok | [ ] |
| 13 | September 04 | Friday | A grade of WD is assigned to students who officially drop a course. | 2026-09-04 | ok | [ ] |
| 14 | September 04 | Friday | Course substitutions for Fall 2026 submission due in DARR | 2026-09-04 | ok | [ ] |
| 15 | September 07 | Monday | **Labor Day. College Closed** | 2026-09-07 | ok | [ ] |
| 16 | September 10 | Thursday | Last day to drop for 50% tuition refund | 2026-09-10 | ok | [ ] |
| 17 | September 11-13 | Friday-Sunday | **No classes scheduled** | 2026-09-11 to 2026-09-13 | ok | [ ] |
| 18 | September 17 | Thursday | **Connect Day: Departmental Orientation** | 2026-09-17 | ok | [ ] |
| 19 | September 17 | Thursday | Last day to drop for 25% tuition refund. | 2026-09-17 | ok | [ ] |
| 20 | September 17 | Thursday | Last day to Change or Declare a Major/Minor to be effective Fall 2026. | 2026-09-17 | ok | [ ] |
| 21 | September 17 | Thursday | **Last day to drop a course with a grade of WD.** | 2026-09-17 | ok | [ ] |
| 22 | September 17 | Thursday | **Verification of Enrollment (VOE) Rosters due from faculty.** | 2026-09-17 | ok | [ ] |
| 23 | September 18 | Friday | **WN Grades assigned.** | 2026-09-18 | ok | [ ] |
| 24 | September 18 | Friday | Course Withdrawal period begins (100% tuition obligation for course drops). | 2026-09-18 | ok | [ ] |
| 25 | September 18 | Friday | A grade of W is assigned to students who officially withdraw from a class. | 2026-09-18 | ok | [ ] |
| 26 | September 21 | Monday | **No classes scheduled** | 2026-09-21 | ok | [ ] |
| 27 | September 27 | Sunday | WA grades assigned for Immunization non-compliance | 2026-09-27 | ok | [ ] |
| 28 | October 05 | Monday | Filing Period for Fall 2026 graduation begins | 2026-10-05 | ok | [ ] |
| 29 | October 12 | Monday | **College Closed** | 2026-10-12 | ok | [ ] |
| 30 | October 13 | Tuesday | Classes follow a Monday schedule | 2026-10-13 | ok | [ ] |
| 31 | October 15 | Thursday | Last day for faculty to submit updated grades for Spring 2026 and Summer 2026 “INC” grades. | 2026-10-15 | ok | [ ] |
| 32 | October 15 | Thursday | Change/Declaration of Major/Minor period opens for Spring 2027. | 2026-10-15 | ok | [ ] |
| 33 | October 15 | Thursday | Advisement begins for Winter 2027 and Spring 2027. | 2026-10-15 | ok | [ ] |
| 34 | October 15 | Thursday | Course Substitutions for Spring 2027 may now be submitted in DARR. | 2026-10-15 | ok | [ ] |
| 35 | October 19-23 | Monday-Friday | Plan Week: Students plan course registration for the following semester and connect with an advisor. | 2026-10-19 to 2026-10-23 | ok | [ ] |
| 36 | October 23 | Friday | Faculty to inform students of midterm progress reports | 2026-10-23 | ok | [ ] |
| 37 | October 29 | Thursday | Online registration for Winter 2027 begins for all students. | 2026-10-29 | ok | [ ] |
| 38 | October 29 | Thursday | Early online registration for Spring 2027 begins for ASAP, BMI, CSTEP, Honors, SEEK, Seniors & Veteran student populations. Registration by appointment only. | 2026-10-29 | ok | [ ] |
| 39 | November 02 | Monday | Online registration for Spring 2027 begins for all students. | 2026-11-02 | ok | [ ] |
| 40 | November 06 | Friday | Last day to withdraw from a course with a grade of W. | 2026-11-06 | ok | [ ] |
| 41 | November 06 | Friday | Deadline for Course and Standards Appeals Submission (students dismissed Spring 2026 or earlier for potential Spring 2027 return). | 2026-11-06 | ok | [ ] |
| 42 | November 06 | Friday | For more info :- www.citytech.cuny.edu/registrar/course-standard.aspx | 2026-11-06 | ok | [ ] |
| 43 | November 08 | Sunday | **No classes scheduled** | 2026-11-08 | ok | [ ] |
| 44 | November 13 | Friday | **Deadline to submit Satisfactory Academic Progress (SAP) Appeals for Title IV for Fall 2026** | 2026-11-13 | ok | [ ] |
| 45 | November 25 | Wednesday | **No classes scheduled** | 2026-11-25 | ok | [ ] |
| 46 | November 26-27 | Thursday-Friday | **Thanksgiving Holiday. College Closed** | 2026-11-26 to 2026-11-27 | ok | [ ] |
| 47 | November 28 | Saturday | **No classes scheduled** | 2026-11-28 | ok | [ ] |
| 48 | December 11 | Friday | Final Grade Rosters open in CUNYfirst | 2026-12-11 | ok | [ ] |
| 49 | December 15-21 | Tuesday-Monday | Final Examinations | 2026-12-15 to 2026-12-21 | ok | [ ] |
| 50 | December 21 | Monday | Filing period for Fall 2026 graduation ends | 2026-12-21 | ok | [ ] |
| 51 | December 21 | Monday | **End of Fall 2026 term** | 2026-12-21 | ok | [ ] |
| 52 | December 24-25 | Thursday-Friday | **College Closed** | 2026-12-24 to 2026-12-25 | ok | [ ] |
| 53 | December 28 | Monday | Final Grade Submission Deadline | 2026-12-28 | ok | [ ] |
| 54 | December 31 | Thursday | **College Closed** | 2026-12-31 | ok | [ ] |
| 55 | January 01, 2027 | Friday | **College Closed** | 2027-01-01 | ok | [ ] |

Rows made from two printed lines (wrapped text, joined): [35, 38, 41].
Rows with a TBA date: none. Rows where `applies_to` was filled: [1, 37, 38, 39, 41].
Weekday mismatches: none.
Text in the PDF outside the table (not events): "FALL 2026 ACADEMIC CALENDAR*"; "*The Academic Calendar is subject to change at any time by official action of the University"; "CUNY Policy on Religious Accommodations"; "All Religions and Ethnic Holidays Calendar".

## Winter 2027

Source: `data/pdfs/winter_2027.pdf`, title "WINTER 2027 ACADEMIC CALENDAR*", last updated 2026-07-27 (printed "Last updated: 7/27/26"). 26 events.

| # | Printed date | Printed day | Event text | Parsed date | Weekday check | OK |
|---|---|---|---|---|---|---|
| 1 | December 28 | Monday | Last day to file ePermit request for the Winter Session | 2026-12-28 | ok | [ ] |
| 2 | January 01 | Friday | **College Closed** | 2027-01-01 | ok | [ ] |
| 3 | January 03 | Sunday | Last day to drop for 100% tuition refund. | 2027-01-03 | ok | [ ] |
| 4 | January 04 | Monday | **Start of Winter 2027 session.** | 2027-01-04 | ok | [ ] |
| 5 | January 04 | Monday | Classes begin | 2027-01-04 | ok | [ ] |
| 6 | January 04 | Monday | **Last day to add a course.** | 2027-01-04 | ok | [ ] |
| 7 | January 04 | Monday | Last day to drop for 50% tuition refund. | 2027-01-04 | ok | [ ] |
| 8 | January 04 | Monday | Last Day to drop without a grade of WD | 2027-01-04 | ok | [ ] |
| 9 | January 05 | Tuesday | **Verification of Enrollment (VOE) Rosters available to faculty.** | 2027-01-05 | ok | [ ] |
| 10 | January 05 | Tuesday | A grade of WD is assigned to students who officially drop a course. | 2027-01-05 | ok | [ ] |
| 11 | January 06 | Wednesday | Last day to drop for 25% tuition refund. | 2027-01-06 | ok | [ ] |
| 12 | January 06 | Wednesday | **Last day to drop a course with a grade of WD.** | 2027-01-06 | ok | [ ] |
| 13 | January 06 | Wednesday | **Verification of Enrollment (VOE) Rosters due from faculty.** | 2027-01-06 | ok | [ ] |
| 14 | January 07 | Thursday | **WN Grades assigned.** | 2027-01-07 | ok | [ ] |
| 15 | January 07 | Thursday | Course Withdrawal period begins (100% tuition obligation for course drops). | 2027-01-07 | ok | [ ] |
| 16 | January 07 | Thursday | A grade of W is assigned to students who officially withdraw from a class. | 2027-01-07 | ok | [ ] |
| 17 | January 08 | Friday | Deadline for Course and Standards Appeals Submission (students dismissed Spring 2026 or earlier for potential Summer/Fall 2027 return). | 2027-01-08 | ok | [ ] |
| 18 | January 08 | Friday | For more info :- www.citytech.cuny.edu/registrar/course-standard.aspx | 2027-01-08 | ok | [ ] |
| 19 | January 17 | Sunday | Last day to withdraw from a course with a grade of W. | 2027-01-17 | ok | [ ] |
| 20 | January 18 | Monday | **Martin Luther King Jr. Day. College Closed** | 2027-01-18 | ok | [ ] |
| 21 | January 22 | Friday | Final Grade Rosters open in CUNYfirst | 2027-01-22 | ok | [ ] |
| 22 | January 25 | Monday | Final Examinations | 2027-01-25 | ok | [ ] |
| 23 | January 25 | Monday | **End of Winter 2027 Session** | 2027-01-25 | ok | [ ] |
| 24 | January 25 | Monday | Filing period for February 2027 graduation begins | 2027-01-25 | ok | [ ] |
| 25 | January 26 | Tuesday | Final Grade Submission Deadline | 2027-01-26 | ok | [ ] |
| 26 | February 01 | Monday | Filing period for February 2027 graduation ends | 2027-02-01 | ok | [ ] |

Rows made from two printed lines (wrapped text, joined): [17].
Rows with a TBA date: none. Rows where `applies_to` was filled: [17].
Weekday mismatches: none.
Text in the PDF outside the table (not events): "WINTER 2027 ACADEMIC CALENDAR*"; "*The Academic Calendar is subject to change at any time by official action of the University"; "CUNY Policy on Religious Accommodations"; "All Religions and Ethnic Holidays Calendar".

## Spring 2027

Source: `data/pdfs/spring_2027.pdf`, title "SPRING 2027 ACADEMIC CALENDAR*", last updated 2026-07-27 (printed "Last updated: 7/27/26"). 55 events.

| # | Printed date | Printed day | Event text | Parsed date | Weekday check | OK |
|---|---|---|---|---|---|---|
| 1 | January 08 | Friday | Deadline for Course and Standards Appeals Submission (students dismissed Spring 2026 or earlier for potential Summer/Fall 2027 return). | 2027-01-08 | ok | [ ] |
| 2 | January 08 | Friday | For more info :- www.citytech.cuny.edu/registrar/course-standard.aspx | 2027-01-08 | ok | [ ] |
| 3 | January 18 | Monday | **Martin Luther King Jr. Day. College Closed** | 2027-01-18 | ok | [ ] |
| 4 | January 21 | Thursday | Last day to file ePermit request | 2027-01-21 | ok | [ ] |
| 5 | January 27 | Wednesday | Last day to drop for 100% tuition refund. | 2027-01-27 | ok | [ ] |
| 6 | January 28 | Thursday | **Start of Spring 2027 term.** | 2027-01-28 | ok | [ ] |
| 7 | January 28 | Thursday | Classes begin | 2027-01-28 | ok | [ ] |
| 8 | February 03 | Wednesday | **Last day to add a course.** | 2027-02-03 | ok | [ ] |
| 9 | February 03 | Wednesday | Last day to drop for 75% tuition refund. | 2027-02-03 | ok | [ ] |
| 10 | February 03 | Wednesday | **Last day to opt-in for Credit/No-Credit grades for Fall 2026 and Winter 2027 classes.** | 2027-02-03 | ok | [ ] |
| 11 | February 03 | Wednesday | Financial Aid Certification Enrollment Status Date. | 2027-02-03 | ok | [ ] |
| 12 | February 03 | Wednesday | Last Day to drop without a grade of WD | 2027-02-03 | ok | [ ] |
| 13 | February 04 | Thursday | **Verification of Enrollment (VOE) Rosters available to faculty.** | 2027-02-04 | ok | [ ] |
| 14 | February 04 | Thursday | A grade of WD is assigned to students who officially drop a course. | 2027-02-04 | ok | [ ] |
| 15 | February 04 | Thursday | Course substitutions for Spring 2027 submission due in DARR | 2027-02-04 | ok | [ ] |
| 16 | February 06 | Saturday | **No classes scheduled** | 2027-02-06 | ok | [ ] |
| 17 | February 10 | Wednesday | Last day to drop for 50% tuition refund | 2027-02-10 | ok | [ ] |
| 18 | February 12 | Friday | **Lincoln's Birthday. College Closed** | 2027-02-12 | ok | [ ] |
| 19 | February 15 | Monday | **Presidents' Day. College Closed** | 2027-02-15 | ok | [ ] |
| 20 | February 17 | Wednesday | Last day to drop for 25% tuition refund. | 2027-02-17 | ok | [ ] |
| 21 | February 17 | Wednesday | Last day to Change or Declare a Major/Minor to be effective Spring 2027. | 2027-02-17 | ok | [ ] |
| 22 | February 17 | Wednesday | **Last day to drop a course with a grade of WD.** | 2027-02-17 | ok | [ ] |
| 23 | February 17 | Wednesday | **Verification of Enrollment (VOE) Rosters due from faculty.** | 2027-02-17 | ok | [ ] |
| 24 | February 18 | Thursday | **WN Grades assigned.** | 2027-02-18 | ok | [ ] |
| 25 | February 18 | Thursday | Course Withdrawal period begins (100% tuition obligation for course drops). | 2027-02-18 | ok | [ ] |
| 26 | February 18 | Thursday | A grade of W is assigned to students who officially withdraw from a class. | 2027-02-18 | ok | [ ] |
| 27 | February 22 | Monday | Filing Period for Spring 2027 graduation begins | 2027-02-22 | ok | [ ] |
| 28 | February 26 | Friday | WA grades assigned for Immunization non-compliance | 2027-02-26 | ok | [ ] |
| 29 | March 01 | Monday | Last day for faculty to submit updated grades for Fall 2026 and Winter 2027 “INC” grades. | 2027-03-01 | ok | [ ] |
| 30 | March 01 | Monday | Change/Declaration of Major/Minor period opens for Fall 2027. | 2027-03-01 | ok | [ ] |
| 31 | March 01 | Monday | Advisement begins for Summer 2027 and Fall 2027. | 2027-03-01 | ok | [ ] |
| 32 | March 01 | Monday | Course Substitutions for Fall 2027 may now be submitted in DARR. | 2027-03-01 | ok | [ ] |
| 33 | March 08-12 | Monday-Friday | Plan Week: Students plan course registration for the following semester and connect with an advisor. | 2027-03-08 to 2027-03-12 | ok | [ ] |
| 34 | March 10 | Wednesday | **No classes scheduled** | 2027-03-10 | ok | [ ] |
| 35 | March 11 | Thursday | Classes follow a Wednesday schedule | 2027-03-11 | ok | [ ] |
| 36 | March 17 | Wednesday | **Deadline to apply for graduation to participate fully in all commencement related activities.** | 2027-03-17 | ok | [ ] |
| 37 | March 18 | Thursday | Online registration for Summer 2027 begins for all students. | 2027-03-18 | ok | [ ] |
| 38 | March 18 | Thursday | Early online registration for Fall 2027 begins for ASAP, CSTEP, Honors, SEEK, Seniors & Veteran student populations. Registration by appointment only. | 2027-03-18 | ok | [ ] |
| 39 | March 22 | Monday | Faculty to inform students of midterm progress reports | 2027-03-22 | ok | [ ] |
| 40 | March 22 | Monday | Online registration for Fall 2027 begins for all students. | 2027-03-22 | ok | [ ] |
| 41 | March 28 | Sunday | **No classes scheduled** | 2027-03-28 | ok | [ ] |
| 42 | March 30 | Tuesday | Classes follow a Monday schedule | 2027-03-30 | ok | [ ] |
| 43 | March 31 | Wednesday | **Deadline to submit Satisfactory Academic Progress (SAP) Appeals for Title IV for Spring 2027** | 2027-03-31 | ok | [ ] |
| 44 | April 05 | Monday | Last day to withdraw from a course with a grade of W. | 2027-04-05 | ok | [ ] |
| 45 | April 21-29 | Wednesday-Thursday | **Spring Recess** | 2027-04-21 to 2027-04-29 | ok | [ ] |
| 46 | May 03 | Monday | Deadline for Course and Standards Appeals Submission (students dismissed Fall 2026 or earlier for potential Fall 2027 return). | 2027-05-03 | ok | [ ] |
| 47 | May 03 | Monday | For more info :- www.citytech.cuny.edu/registrar/course-standard.aspx | 2027-05-03 | ok | [ ] |
| 48 | May 17 | Monday | **No classes scheduled** | 2027-05-17 | ok | [ ] |
| 49 | May 20 | Thursday | Final Grade Rosters open in CUNYfirst | 2027-05-20 | ok | [ ] |
| 50 | May 21-27 | Friday-Thursday | Final Examinations | 2027-05-21 to 2027-05-27 | ok | [ ] |
| 51 | May 27 | Thursday | Filing period for Spring 2027 graduation ends | 2027-05-27 | ok | [ ] |
| 52 | May 27 | Thursday | **End of Spring 2027 term** | 2027-05-27 | ok | [ ] |
| 53 | May 31 | Monday | **Memorial Day. College Closed** | 2027-05-31 | ok | [ ] |
| 54 | June 01 | Tuesday | Final Grade Submission Deadline | 2027-06-01 | ok | [ ] |
| 55 | TBA | TBA | **87th Commencement Ceremony** | TBA | n/a | [ ] |

Rows made from two printed lines (wrapped text, joined): [1, 33, 38, 46].
Rows with a TBA date: [55]. Rows where `applies_to` was filled: [1, 37, 38, 40, 46].
Weekday mismatches: none.
Text in the PDF outside the table (not events): "SPRING 2027 ACADEMIC CALENDAR*"; "*The Academic Calendar is subject to change at any time by official action of the University"; "CUNY Policy on Religious Accommodations"; "All Religions and Ethnic Holidays Calendar".
