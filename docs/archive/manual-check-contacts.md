# Manual check: contacts

Compare each row with the live page it came from (phone, email, room). Write the outcome in
the Result column. Office and department contacts come from `data/processed/contacts`; every
page of an owner shows the same block (the records say `consistent: true`). Chairs come from
the `chairperson.aspx` page records.

## Office and department contact blocks

| Owner | Kind | Room / address | Phone | Fax / AI-agent line | Email | Hours | Source URL (first of N pages) | Result |
|---|---|---|---|---|---|---|---|---|
| CST-NYT | department | 300 Jay Street / Namm Hall 914 (N-914) / Brooklyn, NY 11201 | 718-260-5170 | - | compsystech@citytech.cuny.edu | OFFICE HOURS: Monday - Thursday: 9:00 AM - 7:00 PM; Friday: 9:00 AM - 5:00 PM | https://www.citytech.cuny.edu/computer-systems/ (8 pages) |  |
| DENT-NYT | department | 285 Jay Street / Academic Building 701 (A-701) / Brooklyn, NY 11201 | 718-260-5070 | - | DentalHygiene@citytech.cuny.edu | none printed | https://www.citytech.cuny.edu/dental/ (12 pages) |  |
| EET-NYT | department | 186 Jay Street / Voorhees Hall 733 (V-733) / Brooklyn, NY 11201 | 718-260-5300 | 718-254-8643 (fax) | electricaltelecomm@citytech.cuny.edu | none printed | https://www.citytech.cuny.edu/electrical-telecomm/ (7 pages) |  |
| MATH-NYT | department | 300 Jay Street / Namm Hall 711 (N-711) / Brooklyn, NY 11201 | 718-260-5380 | - | mathematics@citytech.cuny.edu | none printed | https://www.citytech.cuny.edu/mathematics/ (8 pages) |  |
| admissions | office | 300 Jay Street / Namm Hall, Room NG-17 / Brooklyn, NY 11201 | 718-260-5500 | 718-682-7179 (24/7 AI agent) | admissions@citytech.cuny.edu | none printed | https://www.citytech.cuny.edu/admissions/dates-deadlines.aspx (3 pages) |  |
| advisement | office | 300 Jay Street / Brooklyn, NY 11201 | - | - | Advisement4u@citytech.cuny.edu, transferadvisement@citytech.cuny.edu | none printed | https://www.citytech.cuny.edu/advisement/six-steps.aspx (9 pages) |  |
| bursar | office | 300 Jay Street / Namm Hall, Room NG-06 / Brooklyn, NY 11201 | - | - | bursar@citytech.cuny.edu | Bursar Service Window Hours: Monday – Friday; 9:30 AM - 4:00 PM; Saturday – Sunday; Closed<br>Bursar Office Hours: Monday – Friday; 9:30 AM - 4:00 PM; Saturday – Sunday; Closed | https://www.citytech.cuny.edu/bursar/payment-deadlines.aspx (3 pages) |  |
| financial-aid | office | 300 Jay Street / Namm Hall, Room NG-13 / Brooklyn, NY 11201 | 718-260-5700 | 718-254-8525 (fax) | financialaid@citytech.cuny.edu | CONTACT US (hours part): IN-PERSON HOURS; Monday 9:00 AM - 5:00 PM; Tuesday 9:00 AM - 5:00 PM; Wednesday 9:30 AM - 6:30 PM; Thursday 9:00 AM - 5:00 PM; Friday 9:00 AM - 5:00 PM; ZOOM HOURS; Monday 10:00 AM - 12:00 PM; Tuesday 2:00 PM - 4:00 PM; Wednesday 3:00 PM - 5:00 PM; Thursday 1:00 PM - 3:00 PM; Friday CLOSED; PHONE HOURS; Phone Number: 718-260-5700; Monday 9:00 AM - 5:00 PM; Tuesday 9:00 PM - 5:00 PM; Wednesday 9:00 AM - 5:00 PM; Thursday 9:00 AM - 5:00 PM; Friday 9:00 AM - 5:00 PM; WEB-LAB HOURS; Financial Aid Web-Lab Schedule (NG-08A):; Monday 2:00 PM - 4:00 PM; Tuesday 10:00 AM - 12:00 PM; Wednesday 11:00 AM - 1:00 PM; Thursday 3:00 PM - 4:30 PM; Friday 10:00 AM - 12:00 PM; FEDERAL WORK STUDY HOURS; Location: Room NG-08A (Financial Aid Web-Lab):; Monday 11:00 AM - 1:00 PM; Tuesday 2:00 PM - 4:00PM; Thursday 11:00 AM - 2:00 PM | https://www.citytech.cuny.edu/financial-aid/financial-payment-calendar.aspx (4 pages) |  |
| registrar | office | 300 Jay Street / Namm Hall, Room NG-15 / Brooklyn, NY 11201 | 718-260-5800 | - | registrar@citytech.cuny.edu | none printed | https://www.citytech.cuny.edu/registrar/academic-calendar.aspx (8 pages) |  |

## Department chairs (chairperson.aspx)

| Department | Name | Role | Room | Phone | Email | Hours | Source URL | Result |
|---|---|---|---|---|---|---|---|---|
| CST-NYT | Prof. Elizabeth Milonas | Chair | Namm Hall 1000 (N-1000) | 718-260-5038 | EMilonas@citytech.cuny.edu | department hours, see the department row above (none for the chair) | https://www.citytech.cuny.edu/computer-systems/chairperson.aspx |  |
| DENT-NYT | Anna Matthews | Chair | Academic Complex 702 (A-702) | 718-260-5907 | AMatthews@citytech.cuny.edu | none printed | https://www.citytech.cuny.edu/dental/chairperson.aspx |  |
| EET-NYT | Dr. Mohammad Razani | Chair | Voorhees 734 (V-734) | 718-260-5305 | MRazani@citytech.cuny.edu | none printed | https://www.citytech.cuny.edu/electrical-telecomm/chairperson.aspx |  |
| MATH-NYT | Jonathan Natov | Chair | Namm Hall 711 (N-711) | 718-260-5928 | JNatov@citytech.cuny.edu | none printed | https://www.citytech.cuny.edu/mathematics/chairperson.aspx |  |

Look at when checking: the financial aid page's PHONE HOURS table prints Tuesday as '9:00 PM - 5:00 PM' (probably AM; left as printed). The EET and financial aid blocks also print a fax number and the Admissions block prints the 24/7 AI-agent line; they are in the Fax / AI-agent line column, not in Phone (fixed in step 4c-data).

Note: the PDF 'Chair' blocks are not listed here. They are department office contacts, are not indexed, and match the department root page blocks (see `docs/validation-log.md`).
