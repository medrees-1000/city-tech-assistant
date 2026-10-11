# Manual check: contacts

Compare each row with the live page it came from (phone, email, room). Write the outcome in
the Result column. Office and department contacts come from `data/processed/contacts`; every
page of an owner shows the same block (the records say `consistent: true`). Chairs come from
the `chairperson.aspx` page records.

## Office and department contact blocks

| Owner | Kind | Room / address | Phone | Email | Source URL (first of N pages) | Result |
|---|---|---|---|---|---|---|
| CST-NYT | department | 300 Jay Street / Namm Hall 914 (N-914) / Brooklyn, NY 11201 | 718-260-5170 | compsystech@citytech.cuny.edu | https://www.citytech.cuny.edu/computer-systems/ (8 pages) |  |
| DENT-NYT | department | 285 Jay Street / Academic Building 701 (A-701) / Brooklyn, NY 11201 | 718-260-5070 | DentalHygiene@citytech.cuny.edu | https://www.citytech.cuny.edu/dental/ (12 pages) |  |
| EET-NYT | department | 186 Jay Street / Voorhees Hall 733 (V-733) / Brooklyn, NY 11201 | 718-254-8643, 718-260-5300 | electricaltelecomm@citytech.cuny.edu | https://www.citytech.cuny.edu/electrical-telecomm/ (7 pages) |  |
| MATH-NYT | department | 300 Jay Street / Namm Hall 711 (N-711) / Brooklyn, NY 11201 | 718-260-5380 | mathematics@citytech.cuny.edu | https://www.citytech.cuny.edu/mathematics/ (8 pages) |  |
| admissions | office | 300 Jay Street / Namm Hall, Room NG-17 / Brooklyn, NY 11201 | 718-260-5500, 718-682-7179 | admissions@citytech.cuny.edu | https://www.citytech.cuny.edu/admissions/dates-deadlines.aspx (3 pages) |  |
| advisement | office | 300 Jay Street / Brooklyn, NY 11201 | - | Advisement4u@citytech.cuny.edu, transferadvisement@citytech.cuny.edu | https://www.citytech.cuny.edu/advisement/six-steps.aspx (9 pages) |  |
| bursar | office | 300 Jay Street / Namm Hall, Room NG-06 / Brooklyn, NY 11201 | - | bursar@citytech.cuny.edu | https://www.citytech.cuny.edu/bursar/payment-deadlines.aspx (3 pages) |  |
| financial-aid | office | 300 Jay Street / Namm Hall, Room NG-13 / Brooklyn, NY 11201 | 718-254-8525, 718-260-5700 | financialaid@citytech.cuny.edu | https://www.citytech.cuny.edu/financial-aid/financial-payment-calendar.aspx (4 pages) |  |
| registrar | office | 300 Jay Street / Namm Hall, Room NG-15 / Brooklyn, NY 11201 | 718-260-5800 | registrar@citytech.cuny.edu | https://www.citytech.cuny.edu/registrar/academic-calendar.aspx (8 pages) |  |

## Department chairs (chairperson.aspx)

| Department | Name | Role | Room | Phone | Email | Source URL | Result |
|---|---|---|---|---|---|---|---|
| CST-NYT | Prof. Elizabeth Milonas | Chair | Namm Hall 1000 (N-1000) | 718-260-5038 | EMilonas@citytech.cuny.edu | https://www.citytech.cuny.edu/computer-systems/chairperson.aspx |  |
| DENT-NYT | Anna Matthews | Chair | Academic Complex 702 (A-702) | 718-260-5907 | AMatthews@citytech.cuny.edu | https://www.citytech.cuny.edu/dental/chairperson.aspx |  |
| EET-NYT | Dr. Mohammad Razani | Chair | Voorhees 734 (V-734) | 718-260-5305 | MRazani@citytech.cuny.edu | https://www.citytech.cuny.edu/electrical-telecomm/chairperson.aspx |  |
| MATH-NYT | Jonathan Natov | Chair | Namm Hall 711 (N-711) | 718-260-5928 | JNatov@citytech.cuny.edu | https://www.citytech.cuny.edu/mathematics/chairperson.aspx |  |

Look at when checking: the financial aid page's PHONE HOURS table prints Tuesday as '9:00 PM - 5:00 PM' (probably AM; left as printed). The EET and financial aid blocks also list a fax number (it is in the Phone column).

Note: the PDF 'Chair' blocks are not listed here. They are department office contacts, are not indexed, and match the department root page blocks (see `docs/validation-log.md`).
