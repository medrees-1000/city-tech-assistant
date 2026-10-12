# Judge hand-check sheet for the step 3b answers (rubric v3)

Items in the order requested: q22 and q40 (the stored baseline answer, arm OFF run 1, with its rubric v3 verdicts, and `on-run1`), q52 (same two), q15 (`on-run1`, then the stored baseline answer). Answers come from `request_logs` (stored with personal data redacted, none here); sources are the chunks the answerer received, in the order it received them, with their full text. The judge's reasons are copied unedited. This sheet does not say which verdict is right. Fill the blank verdict lines.

## q22 (multi_chunk): stored baseline answer, arm OFF run 1 (rubric v3 verdicts), run `baseline-dev-60-v3`

**Question:** What do I need to take before Calculus III (MAT 2675)?

**Gold answer:** MAT 2675 (Calculus III) requires MAT 1575 (Calculus II) and MAT 2580 (Introduction to Linear Algebra). MAT 2580 requires MAT 1475 (Calculus I). MAT 1575's catalog text reads 'PREREQUISITE OF MAT 1475, MUST NOT HAVE PASSED MAT 2675', so its prerequisite is MAT 1475 and MAT 2675 is an exclusion, not a prerequisite. MAT 1475 requires MAT 1375 (Precalculus) or meeting the math placement for MAT 1475. MAT 1375 requires MAT 1275 (or MAT 1275CO) or meeting the math placement for MAT 1375. MAT 1275 requires CUNY proficiency in mathematics plus the listed high school GPA or Regents score criteria.

**Model's answer:** MAT 2675 requires the prerequisites of both MAT 1575 and MAT 2580. The sources do not specify what those prerequisites are. [2]

**Judge, correctness:** partial: It correctly identifies that MAT 2675 requires the prerequisites of MAT 1575 and MAT 2580, but it fails to state the required courses and incorrectly says the sources do not specify them.

**Judge, faithfulness:** no: The claim that the sources do not specify the prerequisites is unsupported/contradicted by the provided catalog information, which specifies prerequisite chains for MAT 1475 and MAT 1375 (though MAT 1575 and MAT 2580 details are not shown).

**What the judge names, copied from its reasons:**

- correctness (partial): It correctly identifies that MAT 2675 requires the prerequisites of MAT 1575 and MAT 2580, but it fails to state the required courses and incorrectly says the sources do not specify them.
- faithfulness (no): The claim that the sources do not specify the prerequisites is unsupported/contradicted by the provided catalog information, which specifies prerequisite chains for MAT 1475 and MAT 1375 (though MAT 1575 and MAT 2580 details are not shown).

**Sources the answerer received (5):**

<details><summary>[1] https://www.citytech.cuny.edu/mathematics/faqs.aspx | Frequently Asked Questions > PLANNING YOUR MATH SEQUENCE > Algebra to Calculus II Sequence | rank 1</summary>

```
[1] id: page/MATH-NYT/faqs#10
source: https://www.citytech.cuny.edu/mathematics/faqs.aspx
heading: Frequently Asked Questions > PLANNING YOUR MATH SEQUENCE > Algebra to Calculus II Sequence

Frequently Asked Questions > PLANNING YOUR MATH SEQUENCE > Algebra to Calculus II Sequence

- MAT 0650 (+ MAT 0650 CO) Elementary Algebra Developmental
- MAT 1275 (+ MAT 1275 CO) College Algebra and Trigonometry
- MAT 1375 Precalculus
- MAT 1475 Calculus I
- MAT 1575 Calculus II

If you're in STEM math, you may need to take MAT 1275 and/or MAT 1375 to prepare for the first math course explicitly listed in your degree checklist.
```

</details>

<details><summary>[2] catalog_course | MAT 2675 - Calculus III | rank 2</summary>

```
[2] id: catalog:MAT 2675
source: Course catalog: MAT 2675
heading: MAT 2675 - Calculus III

MAT 2675 - Calculus III
Credits: 4
Department: Mathematics
Description: A continuation of MAT 1575. Topics include parametric curves, partial derivatives, differentiable multi-variable functions, chain rule for multi-variable functions, vector fields, gradients, divergence, curl, Lagrange multipliers, multiple integrals, line integrals, Green's Theorem, and Stokes' Theorem.
Prerequisites: Prerequisites of MAT 1575 AND MAT 2580
Programs that list this course: Cybersecurity - BS - Bachelor of Science (requirements); Applied Mathematics - BS - Bachelor of Science (degree map, requirements); Computer Science - (requirements); Mathematics Education - BS - Bachelor of Science (degree map, requirements)
```

</details>

<details><summary>[3] catalog_course | MAT 1475 - Calculus I | rank 3</summary>

```
[3] id: catalog:MAT 1475
source: Course catalog: MAT 1475
heading: MAT 1475 - Calculus I

MAT 1475 - Calculus I
Credits: 4
Department: Mathematics
Description: Topics include functions, limits, differentiation, tangent lines, L'Hopital's Rule, Fundamental Theorem of Calculus and applications. (An honors section, designated MAT 1475/MA 475H, may be offered as demand indicates. The same material will be covered as in MAT 1475/MA 475, but from a more advanced perspective).SATISFIES REQUIRED CORE- MATH & QUANTITATIVE REASONING
Prerequisites: PRE: MAT 1375 OR Meet the Math Placement for MAT 1475
Programs that list this course: Computer Systems - BTECH - Bachelor of Technology (degree map, requirements); Cybersecurity - BS - Bachelor of Science (degree map, requirements); Data Science - BS - Bachelor of Science (degree map, requirements); Electrical Engineering Technology - AAS - Associate in Applied Science (degree map, requirements); Electrical Engineering Technology - BTECH - Bachelor of Technology (degree map, requirements); Applied Mathematics - BS - Bachelor of Science (degree map, requirements); Computer Science - AS - Associate in Science (degree map, requirements); Mathematics Education - BS - Bachelor of Science (degree map, requirements)
```

</details>

<details><summary>[4] catalog_course | MAT 1375 - Precalculus | rank 4</summary>

```
[4] id: catalog:MAT 1375
source: Course catalog: MAT 1375
heading: MAT 1375 - Precalculus

MAT 1375 - Precalculus
Credits: 4
Department: Mathematics
Description: A pre-calculus functions course including topics from advanced algebra and theory of equations such as solutions of polynomial equations, DeMoivre's Theorem, vectors, lines, conic sections, and progressions.
Prerequisites: PRE: MAT 1275 or MAT 1275CO OR Meet the Math Placement for MAT 1375
Programs that list this course: Computer Systems - BTECH - Bachelor of Technology (degree map, requirements); Computer Information Systems - AAS - Associate in Applied Science (degree map, requirements); Cybersecurity - BS - Bachelor of Science (degree map, requirements); Data Science - BS - Bachelor of Science (degree map); Electrical Engineering Technology - AAS - Associate in Applied Science (degree map, requirements); Electrical Engineering Technology - BTECH - Bachelor of Technology (degree map, requirements)
```

</details>

<details><summary>[5] catalog_course | MAT 2630 - Numerical Methods Math Core | rank 5</summary>

```
[5] id: catalog:MAT 2630
source: Course catalog: MAT 2630
heading: MAT 2630 - Numerical Methods Math Core

MAT 2630 - Numerical Methods Math Core
Credits: 3
Department: Mathematics
Description: An introduction to solving mathematical problems on the computer, using a symbolic algebra program with applications drawn from science and engineering. Topics include roots of non-linear functions, interpolation, numerical differentiation and numerical integration.
Prerequisites: PRE-Requisite of  MAT 1575, MAT 2580 & ( CST 1101 or higher, MAT 1475H, MAT 1476L or MAT 1630)
Programs that list this course: Applied Mathematics - BS - Bachelor of Science (degree map, requirements); Computer Science - (requirements)
```

</details>

**My verdict:** correctness  / faithfulness 

## q22 (multi_chunk): arm ON run 1, run `on-run1`

**Question:** What do I need to take before Calculus III (MAT 2675)?

**Gold answer:** MAT 2675 (Calculus III) requires MAT 1575 (Calculus II) and MAT 2580 (Introduction to Linear Algebra). MAT 2580 requires MAT 1475 (Calculus I). MAT 1575's catalog text reads 'PREREQUISITE OF MAT 1475, MUST NOT HAVE PASSED MAT 2675', so its prerequisite is MAT 1475 and MAT 2675 is an exclusion, not a prerequisite. MAT 1475 requires MAT 1375 (Precalculus) or meeting the math placement for MAT 1475. MAT 1375 requires MAT 1275 (or MAT 1275CO) or meeting the math placement for MAT 1375. MAT 1275 requires CUNY proficiency in mathematics plus the listed high school GPA or Regents score criteria.

**Model's answer:** MAT 2675 requires the prerequisites of both MAT 1575 (Calculus II) and MAT 2580. [1] The sources do not specify MAT 2580’s prerequisites. [1]

**Judge, correctness:** partial: It correctly identifies that Calculus III requires the prerequisites of MAT 1575 and MAT 2580, but it omits the actual prerequisite chain and incorrectly says MAT 2580's prerequisites are unspecified despite the gold answer identifying MAT 1475.

**Judge, faithfulness:** yes: The answer accurately restates source [1], and source [1] itself does not specify MAT 2580's prerequisites.

**What the judge names, copied from its reasons:**

- correctness (partial): It correctly identifies that Calculus III requires the prerequisites of MAT 1575 and MAT 2580, but it omits the actual prerequisite chain and incorrectly says MAT 2580's prerequisites are unspecified despite the gold answer identifying MAT 1475.

**Sources the answerer received (5):**

<details><summary>[1] catalog_course | MAT 2675 - Calculus III | rank 1</summary>

```
[1] id: catalog:MAT 2675
source: Course catalog: MAT 2675
heading: MAT 2675 - Calculus III

MAT 2675 - Calculus III
Credits: 4
Department: Mathematics
Description: A continuation of MAT 1575. Topics include parametric curves, partial derivatives, differentiable multi-variable functions, chain rule for multi-variable functions, vector fields, gradients, divergence, curl, Lagrange multipliers, multiple integrals, line integrals, Green's Theorem, and Stokes' Theorem.
Prerequisites: Prerequisites of MAT 1575 AND MAT 2580
Programs that list this course: Cybersecurity - BS - Bachelor of Science (requirements); Applied Mathematics - BS - Bachelor of Science (degree map, requirements); Computer Science - (requirements); Mathematics Education - BS - Bachelor of Science (degree map, requirements)
```

</details>

<details><summary>[2] catalog_course | MAT 1575 - Calculus II | rank 2</summary>

```
[2] id: catalog:MAT 1575
source: Course catalog: MAT 1575
heading: MAT 1575 - Calculus II

MAT 1575 - Calculus II
Credits: 4
Department: Mathematics
Description: A continuation of MAT 1475. Topics include Taylor polynomials, Mean Value Theorem, Taylor and Maclaurin series, tests of convergence, techniques of integration, improper integrals, areas, volumes and arclength.SATISFIES FLEXIBLE CORE- SCIENTIFIC WORLD
Prerequisites: PREREQUISITE OF MAT 1475, MUST NOT HAVE PASSED MAT 2675
Programs that list this course: Cybersecurity - BS - Bachelor of Science (degree map, requirements); Data Science - BS - Bachelor of Science (degree map, requirements); Electrical Engineering Technology - BTECH - Bachelor of Technology (degree map, requirements); Applied Mathematics - BS - Bachelor of Science (degree map, requirements); Computer Science - AS - Associate in Science (degree map, requirements); Mathematics Education - BS - Bachelor of Science (degree map, requirements)
```

</details>

<details><summary>[3] https://www.citytech.cuny.edu/mathematics/faqs.aspx | Frequently Asked Questions > PLANNING YOUR MATH SEQUENCE > Algebra to Calculus II Sequence | rank 3</summary>

```
[3] id: page/MATH-NYT/faqs#10
source: https://www.citytech.cuny.edu/mathematics/faqs.aspx
heading: Frequently Asked Questions > PLANNING YOUR MATH SEQUENCE > Algebra to Calculus II Sequence

Frequently Asked Questions > PLANNING YOUR MATH SEQUENCE > Algebra to Calculus II Sequence

- MAT 0650 (+ MAT 0650 CO) Elementary Algebra Developmental
- MAT 1275 (+ MAT 1275 CO) College Algebra and Trigonometry
- MAT 1375 Precalculus
- MAT 1475 Calculus I
- MAT 1575 Calculus II

If you're in STEM math, you may need to take MAT 1275 and/or MAT 1375 to prepare for the first math course explicitly listed in your degree checklist.
```

</details>

<details><summary>[4] catalog_course | MAT 1475 - Calculus I | rank 4</summary>

```
[4] id: catalog:MAT 1475
source: Course catalog: MAT 1475
heading: MAT 1475 - Calculus I

MAT 1475 - Calculus I
Credits: 4
Department: Mathematics
Description: Topics include functions, limits, differentiation, tangent lines, L'Hopital's Rule, Fundamental Theorem of Calculus and applications. (An honors section, designated MAT 1475/MA 475H, may be offered as demand indicates. The same material will be covered as in MAT 1475/MA 475, but from a more advanced perspective).SATISFIES REQUIRED CORE- MATH & QUANTITATIVE REASONING
Prerequisites: PRE: MAT 1375 OR Meet the Math Placement for MAT 1475
Programs that list this course: Computer Systems - BTECH - Bachelor of Technology (degree map, requirements); Cybersecurity - BS - Bachelor of Science (degree map, requirements); Data Science - BS - Bachelor of Science (degree map, requirements); Electrical Engineering Technology - AAS - Associate in Applied Science (degree map, requirements); Electrical Engineering Technology - BTECH - Bachelor of Technology (degree map, requirements); Applied Mathematics - BS - Bachelor of Science (degree map, requirements); Computer Science - AS - Associate in Science (degree map, requirements); Mathematics Education - BS - Bachelor of Science (degree map, requirements)
```

</details>

<details><summary>[5] catalog_course | MAT 1375 - Precalculus | rank 5</summary>

```
[5] id: catalog:MAT 1375
source: Course catalog: MAT 1375
heading: MAT 1375 - Precalculus

MAT 1375 - Precalculus
Credits: 4
Department: Mathematics
Description: A pre-calculus functions course including topics from advanced algebra and theory of equations such as solutions of polynomial equations, DeMoivre's Theorem, vectors, lines, conic sections, and progressions.
Prerequisites: PRE: MAT 1275 or MAT 1275CO OR Meet the Math Placement for MAT 1375
Programs that list this course: Computer Systems - BTECH - Bachelor of Technology (degree map, requirements); Computer Information Systems - AAS - Associate in Applied Science (degree map, requirements); Cybersecurity - BS - Bachelor of Science (degree map, requirements); Data Science - BS - Bachelor of Science (degree map); Electrical Engineering Technology - AAS - Associate in Applied Science (degree map, requirements); Electrical Engineering Technology - BTECH - Bachelor of Technology (degree map, requirements)
```

</details>

**My verdict:** correctness  / faithfulness 

## q40 (multi_chunk): stored baseline answer, arm OFF run 1 (rubric v3 verdicts), run `baseline-dev-60-v3`

**Question:** Starting from CST 3613 (Application Development with Database), which courses do I have to take first, and what do those courses require?

**Gold answer:** CST 3613 (App. Development with Database) requires CST 1201 (Programming Fundamentals) and CST 1204 (Database Systems Fundamentals); catalog text: “PREREQUISITE OF CST 1201, CST 1204 WITH A GRADE OF C OR HIGHER”. CST 1201 (Programming Fundamentals) requires CST 1100 (Intro to Computer Systems) and CST 1101 (Problem Solving Comp. Program); catalog text: “PRE: FOR CST MAJORS: CST 1100 & 1101, C GRADE / PRE: FOR NON-CST MAJORS: CST 1101”. CST 1100 (Intro to Computer Systems) has no prerequisite course. CST 1101 (Problem Solving Comp. Program) has no prerequisite course. CST 1204 (Database Systems Fundamentals) requires CST 1100 (Intro to Computer Systems).

**Model's answer:** CST 3613 requires CST 1201 and CST 1204, each with a grade of C or higher. [1]

Of those courses, the sources give a prerequisite for CST 1204: CST 1100 and CST 1101. [5] The sources do not state prerequisites for CST 1201. [1]

**Judge, correctness:** partial: It correctly identifies CST 3613's direct prerequisites but incorrectly says CST 1204 requires both CST 1100 and CST 1101 and omits CST 1201's prerequisite chain.

**Judge, faithfulness:** no: It contradicts source [5], which states that CST 1204 requires CST 1100 and CST 1101, while its claim that no prerequisites are stated for CST 1201 is unsupported by the provided sources.

**What the judge names, copied from its reasons:**

- correctness (partial): It correctly identifies CST 3613's direct prerequisites but incorrectly says CST 1204 requires both CST 1100 and CST 1101 and omits CST 1201's prerequisite chain.
- faithfulness (no): It contradicts source [5], which states that CST 1204 requires CST 1100 and CST 1101, while its claim that no prerequisites are stated for CST 1201 is unsupported by the provided sources.

**Sources the answerer received (5):**

<details><summary>[1] catalog_course | CST 3613 - App. Development with Database | rank 1</summary>

```
[1] id: catalog:CST 3613
source: Course catalog: CST 3613
heading: CST 3613 - App. Development with Database

CST 3613 - App. Development with Database
Credits: 3
Department: Computer Systems Tech
Description: This course is an overview of the design and implementation of 2-tier Java Applications. It will explore the concepts and processes that connect a Graphic User Interface (GUI) developed in Java programming language to a database using JDBC. Working through projects, students will learn to create applications that connect to databases, execute SQL commands and manipulate data sets retrieved from databases. Several advanced Java database applications will be studied, such as stored procedures, scrollable and updateable result sets, row sets and storing/retrieving images from a database.
Prerequisites: PREREQUISITE OF CST 1201, CST 1204 WITH A GRADE OF C OR HIGHER
Programs that list this course: Computer Systems - BTECH - Bachelor of Technology (degree map, requirements)
```

</details>

<details><summary>[2] catalog_course | CST 3615 - Enterprise Applications | rank 2</summary>

```
[2] id: catalog:CST 3615
source: Course catalog: CST 3615
heading: CST 3615 - Enterprise Applications

CST 3615 - Enterprise Applications
Credits: 3
Department: Computer Systems Tech
Description: This is a survey course in which students will learn how different enterprise applications integrate with other systems commonly used by an organization, and how to select, deploy, configure and manage enterprise applications including communication software (email, internet telephony/VoIP), messaging and collaboration systems, business intelligence and analytics, customer relationship management (CRM), enterprise resource planning (ERP), content management systems as well as the cloud computing, a widely used architecture to deploy enterprise app
Prerequisites: PRE: CST3507 & 2400/2405/2415
Programs that list this course: Computer Systems - BTECH - Bachelor of Technology (degree map, requirements)
```

</details>

<details><summary>[3] catalog_course | CST 4714 - Database Administration | rank 3</summary>

```
[3] id: catalog:CST 4714
source: Course catalog: CST 4714
heading: CST 4714 - Database Administration

CST 4714 - Database Administration
Credits: 3
Department: Computer Systems Tech
Description: "This course is the last course of the ""Databases"" module and is concentrated on the advanced issues of database management and administration.  The course discusses activities needed to sustain reliable and secure database with good performance, Managing database storage (data, log, and backup files), database objects (tables, indexes, clusters, etc) and procedural objecs (triggers, stored procedures) for delivering the database properties mentioned above are discussed in details.  Also issues such a security, administrating users and recourses, tuning the applications, and monitoring the performance of database are included."
Prerequisites: P:CST2402 or CST2405 or CST2415 or CST 3604
Programs that list this course: Computer Systems - BTECH - Bachelor of Technology (degree map, requirements)
```

</details>

<details><summary>[4] catalog_course | CST 3504 - Database Design | rank 4</summary>

```
[4] id: catalog:CST 3504
source: Course catalog: CST 3504
heading: CST 3504 - Database Design

CST 3504 - Database Design
Credits: 3
Department: Computer Systems Tech
Description: "This course provides a general introduction to database design.  The three main phases in database design are covered; that is conceptual, using Entity Relational Diagram (ERD) and Unified Modeling Language (UML); logical, using relational model, and physical, using a Database Management Systems.  The basics of relational data model (concepts of relation, attribute, primary key, and foreign key) are reviewed, and mapping the conceptual model to the relational model is discussed.  Advanced concepts of relational theory; normalization and denormalization are included.  Physical implementation is described with the help of a particular Relational Database Management System (RDBMS).  The students must be familiar with SQL."
Prerequisites: PRE: CST 1204 C OR HIGHER
Programs that list this course: Computer Systems - BTECH - Bachelor of Technology (degree map, requirements)
```

</details>

<details><summary>[5] catalog_course | CST 1204 - Database Systems Fundamentals | rank 5</summary>

```
[5] id: catalog:CST 1204
source: Course catalog: CST 1204
heading: CST 1204 - Database Systems Fundamentals

CST 1204 - Database Systems Fundamentals
Credits: 3
Department: Computer Systems Tech
Description: This course will introduce the student to ANSI standard Structured Query Language (SQL).  The course will cover the various syntax that governs this language.  In depth discussions and practice will be given so that the students will be able to manipulate (insert, update, delete and retrieve) data in a relational database.
Prerequisites: PRE: CST 1100 & 1101
Programs that list this course: Computer Systems - BTECH - Bachelor of Technology (degree map, requirements); Computer Information Systems - AAS - Associate in Applied Science (degree map, requirements); Data Science - BS - Bachelor of Science (degree map, requirements); Computer Science - (requirements)
```

</details>

**My verdict:** correctness  / faithfulness 

## q40 (multi_chunk): arm ON run 1, run `on-run1`

**Question:** Starting from CST 3613 (Application Development with Database), which courses do I have to take first, and what do those courses require?

**Gold answer:** CST 3613 (App. Development with Database) requires CST 1201 (Programming Fundamentals) and CST 1204 (Database Systems Fundamentals); catalog text: “PREREQUISITE OF CST 1201, CST 1204 WITH A GRADE OF C OR HIGHER”. CST 1201 (Programming Fundamentals) requires CST 1100 (Intro to Computer Systems) and CST 1101 (Problem Solving Comp. Program); catalog text: “PRE: FOR CST MAJORS: CST 1100 & 1101, C GRADE / PRE: FOR NON-CST MAJORS: CST 1101”. CST 1100 (Intro to Computer Systems) has no prerequisite course. CST 1101 (Problem Solving Comp. Program) has no prerequisite course. CST 1204 (Database Systems Fundamentals) requires CST 1100 (Intro to Computer Systems).

**Model's answer:** CST 3613 requires CST 1201 and CST 1204, each with a grade of C or higher. [1]

CST 1204 requires CST 1100 and CST 1101. [2] The sources do not state the prerequisites for CST 1201, CST 1100, or CST 1101.

**Judge, correctness:** partial: It correctly identifies CST 3613's direct prerequisites and CST 1204's prerequisites, but incorrectly says the sources do not state the prerequisites for CST 1201, CST 1100, or CST 1101 and omits the required prerequisite chain described in the gold answer.

**Judge, faithfulness:** yes: All affirmative prerequisite claims are supported by sources [1] and [2], and the statement that the provided sources do not state prerequisites for CST 1201, CST 1100, or CST 1101 is accurate.

**What the judge names, copied from its reasons:**

- correctness (partial): It correctly identifies CST 3613's direct prerequisites and CST 1204's prerequisites, but incorrectly says the sources do not state the prerequisites for CST 1201, CST 1100, or CST 1101 and omits the required prerequisite chain described in the gold answer.

**Sources the answerer received (5):**

<details><summary>[1] catalog_course | CST 3613 - App. Development with Database | rank 1</summary>

```
[1] id: catalog:CST 3613
source: Course catalog: CST 3613
heading: CST 3613 - App. Development with Database

CST 3613 - App. Development with Database
Credits: 3
Department: Computer Systems Tech
Description: This course is an overview of the design and implementation of 2-tier Java Applications. It will explore the concepts and processes that connect a Graphic User Interface (GUI) developed in Java programming language to a database using JDBC. Working through projects, students will learn to create applications that connect to databases, execute SQL commands and manipulate data sets retrieved from databases. Several advanced Java database applications will be studied, such as stored procedures, scrollable and updateable result sets, row sets and storing/retrieving images from a database.
Prerequisites: PREREQUISITE OF CST 1201, CST 1204 WITH A GRADE OF C OR HIGHER
Programs that list this course: Computer Systems - BTECH - Bachelor of Technology (degree map, requirements)
```

</details>

<details><summary>[2] catalog_course | CST 1204 - Database Systems Fundamentals | rank 2</summary>

```
[2] id: catalog:CST 1204
source: Course catalog: CST 1204
heading: CST 1204 - Database Systems Fundamentals

CST 1204 - Database Systems Fundamentals
Credits: 3
Department: Computer Systems Tech
Description: This course will introduce the student to ANSI standard Structured Query Language (SQL).  The course will cover the various syntax that governs this language.  In depth discussions and practice will be given so that the students will be able to manipulate (insert, update, delete and retrieve) data in a relational database.
Prerequisites: PRE: CST 1100 & 1101
Programs that list this course: Computer Systems - BTECH - Bachelor of Technology (degree map, requirements); Computer Information Systems - AAS - Associate in Applied Science (degree map, requirements); Data Science - BS - Bachelor of Science (degree map, requirements); Computer Science - (requirements)
```

</details>

<details><summary>[3] catalog_course | CST 3615 - Enterprise Applications | rank 3</summary>

```
[3] id: catalog:CST 3615
source: Course catalog: CST 3615
heading: CST 3615 - Enterprise Applications

CST 3615 - Enterprise Applications
Credits: 3
Department: Computer Systems Tech
Description: This is a survey course in which students will learn how different enterprise applications integrate with other systems commonly used by an organization, and how to select, deploy, configure and manage enterprise applications including communication software (email, internet telephony/VoIP), messaging and collaboration systems, business intelligence and analytics, customer relationship management (CRM), enterprise resource planning (ERP), content management systems as well as the cloud computing, a widely used architecture to deploy enterprise app
Prerequisites: PRE: CST3507 & 2400/2405/2415
Programs that list this course: Computer Systems - BTECH - Bachelor of Technology (degree map, requirements)
```

</details>

<details><summary>[4] catalog_course | CST 4714 - Database Administration | rank 4</summary>

```
[4] id: catalog:CST 4714
source: Course catalog: CST 4714
heading: CST 4714 - Database Administration

CST 4714 - Database Administration
Credits: 3
Department: Computer Systems Tech
Description: "This course is the last course of the ""Databases"" module and is concentrated on the advanced issues of database management and administration.  The course discusses activities needed to sustain reliable and secure database with good performance, Managing database storage (data, log, and backup files), database objects (tables, indexes, clusters, etc) and procedural objecs (triggers, stored procedures) for delivering the database properties mentioned above are discussed in details.  Also issues such a security, administrating users and recourses, tuning the applications, and monitoring the performance of database are included."
Prerequisites: P:CST2402 or CST2405 or CST2415 or CST 3604
Programs that list this course: Computer Systems - BTECH - Bachelor of Technology (degree map, requirements)
```

</details>

<details><summary>[5] catalog_course | CST 3504 - Database Design | rank 5</summary>

```
[5] id: catalog:CST 3504
source: Course catalog: CST 3504
heading: CST 3504 - Database Design

CST 3504 - Database Design
Credits: 3
Department: Computer Systems Tech
Description: "This course provides a general introduction to database design.  The three main phases in database design are covered; that is conceptual, using Entity Relational Diagram (ERD) and Unified Modeling Language (UML); logical, using relational model, and physical, using a Database Management Systems.  The basics of relational data model (concepts of relation, attribute, primary key, and foreign key) are reviewed, and mapping the conceptual model to the relational model is discussed.  Advanced concepts of relational theory; normalization and denormalization are included.  Physical implementation is described with the help of a particular Relational Database Management System (RDBMS).  The students must be familiar with SQL."
Prerequisites: PRE: CST 1204 C OR HIGHER
Programs that list this course: Computer Systems - BTECH - Bachelor of Technology (degree map, requirements)
```

</details>

**My verdict:** correctness  / faithfulness 

## q52 (lookup): stored baseline answer, arm OFF run 1 (rubric v3 verdicts), run `baseline-dev-60-v3`

**Question:** Do the science prerequisites for the Dental Hygiene program expire?

**Gold answer:** Yes. All science courses, including BIO2311, BIO2312, and CHEM, must have been completed within five years of acceptance into the program.

**Model's answer:** ABSTAIN: The sources do not state whether the science prerequisites expire; they only give a five-year limit for chemistry courses [5].

**Judge, correctness:** incorrect: The answer abstains despite the requested conclusion being that all science prerequisites, including BIO2311, BIO2312, and CHEM, expire after five years.

**Judge, faithfulness:** no: It falsely claims the sources only provide a five-year limit for chemistry, whereas source [5] does state that chemistry expires but the broader assertion about what the sources state is unsupported by the provided excerpts.

**What the judge names, copied from its reasons:**

- correctness (incorrect): The answer abstains despite the requested conclusion being that all science prerequisites, including BIO2311, BIO2312, and CHEM, expire after five years.
- faithfulness (no): It falsely claims the sources only provide a five-year limit for chemistry, whereas source [5] does state that chemistry expires but the broader assertion about what the sources state is unsupported by the provided excerpts.

**Sources the answerer received (5):**

<details><summary>[1] https://www.citytech.cuny.edu/dental/faq.aspx | FAQs > Advisement FAQs > I have a certificate from the dental assisting program. Will the dental assisting courses be accepted as prerequisites for the Dental Hygiene program? | rank 1</summary>

```
[1] id: page/DENT-NYT/faq#8
source: https://www.citytech.cuny.edu/dental/faq.aspx
heading: FAQs > Advisement FAQs > I have a certificate from the dental assisting program. Will the dental assisting courses be accepted as prerequisites for the Dental Hygiene program?

FAQs > Advisement FAQs > I have a certificate from the dental assisting program. Will the dental assisting courses be accepted as prerequisites for the Dental Hygiene program?

No.
```

</details>

<details><summary>[2] https://www.citytech.cuny.edu/dental/apply.aspx | How to Apply > Criteria for Admission into The Dental Hygiene Program | rank 2</summary>

```
[2] id: page/DENT-NYT/apply#1
source: https://www.citytech.cuny.edu/dental/apply.aspx
heading: How to Apply > Criteria for Admission into The Dental Hygiene Program

How to Apply > Criteria for Admission into The Dental Hygiene Program

All new and transfer students must first complete the required six prerequisite courses to be considered for acceptance into the dental hygiene program. During the introductory courses sequence, students will register for developmental skills and credit courses in general education and science, which are required for the degree in dental hygiene.

Students will be considered for acceptance into the clinical program during the Fall semester if they:

- Are CUNY proficient in writing and math and proficient at or above the 12th grade level in reading.
- Have completed 21 or 22 required general education credits as delineated in the NYCCT college catalog and departmental literature with at least a "C" in biology and chemistry and a minimum combined average of 2.5. Grades in repeated courses will be averaged.
```

</details>

<details><summary>[3] https://www.citytech.cuny.edu/dental/advisement.aspx | Advisement Information | rank 3</summary>

```
[3] id: page/DENT-NYT/advisement#1
source: https://www.citytech.cuny.edu/dental/advisement.aspx
heading: Advisement Information

Advisement Information

Dental Hygiene Department Advisement Hours – Fall 2026
(September 8, 2026 – December 11, 2026)

All Dental Hygiene advisement is by appointment ONLY, after completing the advisement request form and scheduling with the assigned faculty advisor.

To request advisement, students must complete [Dental Hygiene Advisement Request Form](https://forms.cloud.microsoft/r/H7k2zjmu7e).

NOTE: if you have already been advised by our DH faculty advisor, please reach out to them directly and do not complete a new request form.

Please read carefully our detailed program information on the [Dental Hygiene website](https://www.citytech.cuny.edu/dental/), including the Frequently Asked Questions section, as this will answer most of the questions you might have.

| Professor | Office | Day | Time | Location |
| --- | --- | --- | --- | --- |
| Prof. Ruben Anzola | Suite A702A | Tuesday | 8:00 am - 9:00 am | In-person / Virtual |
| Wednesday | 12:30 pm - 1:30 pm | In-person / Virtual |  |  |
| Prof. Susan Davide | Suite A702J | Monday | 11:30 am - 12:30 pm | In-person / Virtual |
| Wednesday | 8:00 am - 9:00 am | In-person / Virtual |  |  |
| Prof. Cristina Masino | Suite A702M | Tuesday | 12:30 pm - 1:30 pm | In-person / Virtual |
| Friday | 4:00 pm - 5:00 pm | Virtual |  |  |
| Prof. Dora-Ann Oddo | Suite A702L | Monday | 10:45 am - 11:45 am | In-person / Virtual |
| Tuesday | 5:30 pm - 6:30 pm | Virtual |  |  |
| Prof. Jessica Sheridan | Suite A702D | Tuesday | 4:45 pm - 5:45 pm | Virtual |
| Thursday | 11:45 am - 12:45 pm | In-person / Virtual |  |  |
| Prof. Khrystyna Vyprynyuk | Suite A701D | Tuesday | 11:30 am - 12:30 pm | Virtual |
| Wednesday | 8:30 am - 9:30 am | In-person / Virtual |  |  |

To apply for the Fall 2027 Clinical Dental Hygiene Program, the following are required:

- Meeting in person with a Dental Hygiene faculty advisor during the Fall 2026 or Spring 2027 semester
- Review of progress toward completion of all pre-requisite courses
- Review of City Tech student transcript (if the student transferred from another institution, all transfer credits must be evaluated by the Transfer Office and grades/credits must be available for the advisor's review)
- Calculation of GPA in the required pre-requisite courses
- Completion of the Dental Hygiene student advisement information form

## Degree Requirements

COMMON CORE COURSES

At least 1 course designated WI is required from Gen Ed Flexible Common Core.

| Course | Course Name | Credit |
| --- | --- | --- |
| *ENG1101 or ENG1121 | English Composition I or II (EC) | 3 |
| *MQR | Mathematical and Quantitative Reasoning | 3 to 4 |
| *BIO 2311 | Human Anatomy and Physiology I ^2 (LPS) | 4 |
| *BIO 2312 | Human Anatomy and Physiology II ^1 (SW, WI) | 4 |
| *CHEM 1000 | Principles of Chemistry or higher | 4 |
| PSY 1101 | Introduction to Psychology^1 (IS) | 3 |
| *SOC 1101 | Elements of Sociology^1 (IS) | 3 |
| COM 1330 | Public Speaking^3 | 3 |
|  | OR |  |
| COM 1320 | Voice and Diction^3 | 3 |

*We are currently using the GPA of the 21 credits in the six preclinical courses to rank applicants for admission into the dental hygiene program.

*For any course with a designation of "CR", a "D" grade will be used in the calculation of the applicant's GPA per the College Policy. "NC" grade will be calculated as an "F". If the course with a CR or NC grade is repeated, the corresponding D or F grades will be averaged with the new grades.

*Acceptance into the dental hygiene program is based on the GPA of the 6 required preclinical courses. A grade of “C” will lower the GPA of the preclinical courses and affect ranking.
```

</details>

<details><summary>[4] data/pdfs/DENT-NYT-2026-09-10-19-16-25.pdf | Dental Hygiene - AAS - Associate in Applied Science > Requirements > Simple Requirements > Progression and Graduation Requirements | rank 4</summary>

```
[4] id: dept/DENT-NYT/program-dental-hygiene-aas#10
source: data/pdfs/DENT-NYT-2026-09-10-19-16-25.pdf
heading: Dental Hygiene - AAS - Associate in Applied Science > Requirements > Simple Requirements > Progression and Graduation Requirements

Dental Hygiene - AAS - Associate in Applied Science > Requirements > Simple Requirements > Progression and Graduation Requirements

**Type** Completion Requirement

- A minimum grade of C in each course designated with the prefix DEN is required for progression in and graduation from the dental hygiene program.
- DEN 1100 may not be repeated in the event of failure or a grade of “D” and the student will be required to choose another major.
- Students who withdraw will be considered for readmission on an individual basis only if they withdraw in good standing (passing all courses at time of withdrawal).
- No dental hygiene course may be repeated more than once. In addition:
  - No more than two dental hygiene courses may be repeated during the entire course of study.
  - A student may not fail more than one course in any one semester.
- If a student fails to meet any of these provisions, they will be required to withdraw from the dental hygiene curriculum.

Students must complete all requirements for the AAS degree within five years of the date of their matriculation into the dental hygiene program.

**Grading Policy for all DEN courses:**

| DEFINITION | GRADE |
| --- | --- |
| 93-100% | A |
| 90-92.9% | A- |
| 87-89.9% | B+ |
| 83-86.9% | B |
| 80-82.9% | B- |
| 77-79.9% | C+ |
| 75-76.9% | C |
| 60-74.9% | D |
| Below 60% | F |

**Clinical Policies and Procedures**

Once students are admitted to the clinical phase of the program, they must comply with all program policies and procedures.

**Attend Classes:** All Dental Hygiene classes (lectures/laboratories/ clinics) are in-person only. The dental hygiene program runs under a block schedule; students must take the courses in the order in which they are given. The program offers a day and evening options; students are given the opportunity to state a preference during the application process. Due to limited clinic space and faculty to student ratio, students cannot switch between day and evening sections while in the program.

**Day Students:** Fall and Spring sessions are full-time. Students need to be flexible Monday to Friday between the hours of 7:30 am and 6 pm.

**Evening Students:** Fall, Spring, and Summer (June or July) sessions as a full-time student. Students need to be flexible Monday to Friday between the hours of 5 pm and 10 pm, as well as Saturday from 8 am to 5 pm.

**Vaccinations:** Submit documented evidence of a complete physical examination demonstrating good health. The First and Second-Year Student Medical Examination Form is provided by the department. Students are responsible for satisfying NYS immunization and department immunization requirements to be permitted into the clinical portion of the courses to meet CDC guidelines for Health Care Providers. These include:

- T-dap
- Varicella
- MMR
- Hepatitis B (if in-progress, documentation must be provided)
- Influenza - annually
- Tuberculosis baseline screening - blood test (skin test not accepted)

**Any missing or incomplete immunizations will void the student from clinical participation and prevent them from entering the program.**

**Bloodborne Pathogens:** As a healthcare provider, you will have the potential for exposure to respiratory and bloodborne pathogens. Dental hygienists encounter saliva and blood while working on patients. Bloodborne pathogens are infectious microorganisms in human blood that can cause disease. The most common bloodborne pathogens are

Hepatitis B, C & HIV. How to manage bloodborne pathogens is taught to dental hygiene students to help protect everyone against occupational transmission of bloodborne disease.
```

</details>

<details><summary>[5] https://www.citytech.cuny.edu/dental/faq.aspx | FAQs > Advisement FAQs > What Chemistry course is acceptable for the Dental Hygiene program? | rank 5</summary>

```
[5] id: page/DENT-NYT/faq#16
source: https://www.citytech.cuny.edu/dental/faq.aspx
heading: FAQs > Advisement FAQs > What Chemistry course is acceptable for the Dental Hygiene program?

FAQs > Advisement FAQs > What Chemistry course is acceptable for the Dental Hygiene program?

Any Chemistry course numbered CHEM 1000 or higher can be considered. The course must be no older than five years, must be four credits, and must include a laboratory. Please note that a CHEM course higher than CHEM 1000 requires MAT 1275 or higher.
```

</details>

**My verdict:** correctness  / faithfulness 

## q52 (lookup): arm ON run 1, run `on-run1`

**Question:** Do the science prerequisites for the Dental Hygiene program expire?

**Gold answer:** Yes. All science courses, including BIO2311, BIO2312, and CHEM, must have been completed within five years of acceptance into the program.

**Model's answer:** Yes. All science courses, including BIO 2311, BIO 2312, and chemistry, must have been completed within five years of acceptance into the program. [1]

**Judge, correctness:** correct: It accurately states that all science courses, including BIO 2311, BIO 2312, and chemistry, must be completed within five years of acceptance.

**Judge, faithfulness:** yes: The answer directly matches source [1], with only harmless spacing and wording normalization for course names.

**Sources the answerer received (5):**

<details><summary>[1] https://www.citytech.cuny.edu/dental/faq.aspx | FAQs > Advisement FAQs > Is there a five-year expiration rule for all preclinical science courses? | rank 1</summary>

```
[1] id: page/DENT-NYT/faq#12
source: https://www.citytech.cuny.edu/dental/faq.aspx
heading: FAQs > Advisement FAQs > Is there a five-year expiration rule for all preclinical science courses?

FAQs > Advisement FAQs > Is there a five-year expiration rule for all preclinical science courses?

Yes. All science courses, including BIO2311, BIO2312, and CHEM, must have been completed within five years of acceptance into the program.
```

</details>

<details><summary>[2] https://www.citytech.cuny.edu/dental/faq.aspx | FAQs > Advisement FAQs > What Chemistry course is acceptable for the Dental Hygiene program? | rank 2</summary>

```
[2] id: page/DENT-NYT/faq#16
source: https://www.citytech.cuny.edu/dental/faq.aspx
heading: FAQs > Advisement FAQs > What Chemistry course is acceptable for the Dental Hygiene program?

FAQs > Advisement FAQs > What Chemistry course is acceptable for the Dental Hygiene program?

Any Chemistry course numbered CHEM 1000 or higher can be considered. The course must be no older than five years, must be four credits, and must include a laboratory. Please note that a CHEM course higher than CHEM 1000 requires MAT 1275 or higher.
```

</details>

<details><summary>[3] https://www.citytech.cuny.edu/dental/faq.aspx | FAQs > Advisement FAQs > I have a certificate from the dental assisting program. Will the dental assisting courses be accepted as prerequisites for the Dental Hygiene program? | rank 3</summary>

```
[3] id: page/DENT-NYT/faq#8
source: https://www.citytech.cuny.edu/dental/faq.aspx
heading: FAQs > Advisement FAQs > I have a certificate from the dental assisting program. Will the dental assisting courses be accepted as prerequisites for the Dental Hygiene program?

FAQs > Advisement FAQs > I have a certificate from the dental assisting program. Will the dental assisting courses be accepted as prerequisites for the Dental Hygiene program?

No.
```

</details>

<details><summary>[4] https://www.citytech.cuny.edu/dental/apply.aspx | How to Apply > Criteria for Admission into The Dental Hygiene Program | rank 4</summary>

```
[4] id: page/DENT-NYT/apply#1
source: https://www.citytech.cuny.edu/dental/apply.aspx
heading: How to Apply > Criteria for Admission into The Dental Hygiene Program

How to Apply > Criteria for Admission into The Dental Hygiene Program

All new and transfer students must first complete the required six prerequisite courses to be considered for acceptance into the dental hygiene program. During the introductory courses sequence, students will register for developmental skills and credit courses in general education and science, which are required for the degree in dental hygiene.

Students will be considered for acceptance into the clinical program during the Fall semester if they:

- Are CUNY proficient in writing and math and proficient at or above the 12th grade level in reading.
- Have completed 21 or 22 required general education credits as delineated in the NYCCT college catalog and departmental literature with at least a "C" in biology and chemistry and a minimum combined average of 2.5. Grades in repeated courses will be averaged.
```

</details>

<details><summary>[5] https://www.citytech.cuny.edu/dental/advisement.aspx | Advisement Information | rank 5</summary>

```
[5] id: page/DENT-NYT/advisement#1
source: https://www.citytech.cuny.edu/dental/advisement.aspx
heading: Advisement Information

Advisement Information

Dental Hygiene Department Advisement Hours – Fall 2026
(September 8, 2026 – December 11, 2026)

All Dental Hygiene advisement is by appointment ONLY, after completing the advisement request form and scheduling with the assigned faculty advisor.

To request advisement, students must complete [Dental Hygiene Advisement Request Form](https://forms.cloud.microsoft/r/H7k2zjmu7e).

NOTE: if you have already been advised by our DH faculty advisor, please reach out to them directly and do not complete a new request form.

Please read carefully our detailed program information on the [Dental Hygiene website](https://www.citytech.cuny.edu/dental/), including the Frequently Asked Questions section, as this will answer most of the questions you might have.

| Professor | Office | Day | Time | Location |
| --- | --- | --- | --- | --- |
| Prof. Ruben Anzola | Suite A702A | Tuesday | 8:00 am - 9:00 am | In-person / Virtual |
| Wednesday | 12:30 pm - 1:30 pm | In-person / Virtual |  |  |
| Prof. Susan Davide | Suite A702J | Monday | 11:30 am - 12:30 pm | In-person / Virtual |
| Wednesday | 8:00 am - 9:00 am | In-person / Virtual |  |  |
| Prof. Cristina Masino | Suite A702M | Tuesday | 12:30 pm - 1:30 pm | In-person / Virtual |
| Friday | 4:00 pm - 5:00 pm | Virtual |  |  |
| Prof. Dora-Ann Oddo | Suite A702L | Monday | 10:45 am - 11:45 am | In-person / Virtual |
| Tuesday | 5:30 pm - 6:30 pm | Virtual |  |  |
| Prof. Jessica Sheridan | Suite A702D | Tuesday | 4:45 pm - 5:45 pm | Virtual |
| Thursday | 11:45 am - 12:45 pm | In-person / Virtual |  |  |
| Prof. Khrystyna Vyprynyuk | Suite A701D | Tuesday | 11:30 am - 12:30 pm | Virtual |
| Wednesday | 8:30 am - 9:30 am | In-person / Virtual |  |  |

To apply for the Fall 2027 Clinical Dental Hygiene Program, the following are required:

- Meeting in person with a Dental Hygiene faculty advisor during the Fall 2026 or Spring 2027 semester
- Review of progress toward completion of all pre-requisite courses
- Review of City Tech student transcript (if the student transferred from another institution, all transfer credits must be evaluated by the Transfer Office and grades/credits must be available for the advisor's review)
- Calculation of GPA in the required pre-requisite courses
- Completion of the Dental Hygiene student advisement information form

## Degree Requirements

COMMON CORE COURSES

At least 1 course designated WI is required from Gen Ed Flexible Common Core.

| Course | Course Name | Credit |
| --- | --- | --- |
| *ENG1101 or ENG1121 | English Composition I or II (EC) | 3 |
| *MQR | Mathematical and Quantitative Reasoning | 3 to 4 |
| *BIO 2311 | Human Anatomy and Physiology I ^2 (LPS) | 4 |
| *BIO 2312 | Human Anatomy and Physiology II ^1 (SW, WI) | 4 |
| *CHEM 1000 | Principles of Chemistry or higher | 4 |
| PSY 1101 | Introduction to Psychology^1 (IS) | 3 |
| *SOC 1101 | Elements of Sociology^1 (IS) | 3 |
| COM 1330 | Public Speaking^3 | 3 |
|  | OR |  |
| COM 1320 | Voice and Diction^3 | 3 |

*We are currently using the GPA of the 21 credits in the six preclinical courses to rank applicants for admission into the dental hygiene program.

*For any course with a designation of "CR", a "D" grade will be used in the calculation of the applicant's GPA per the College Policy. "NC" grade will be calculated as an "F". If the course with a CR or NC grade is repeated, the corresponding D or F grades will be averaged with the new grades.

*Acceptance into the dental hygiene program is based on the GPA of the 6 required preclinical courses. A grade of “C” will lower the GPA of the preclinical courses and affect ranking.
```

</details>

**My verdict:** correctness  / faithfulness 

## q15 (time_sensitive): arm ON run 1, run `on-run1`

**Question:** What are the student hours for the Electrical Engineering Technology department?

**Gold answer:** The only student-hours page lists hours labeled Fall 2024 (a table by faculty member and weekday, with times and rooms or Zoom). That is not the current term (Fall 2026), so the answer must say the hours are labeled Fall 2024 and not present them as current, and should point the student to the department office to confirm. (Abstaining with the department contact is also acceptable.)

**Model's answer:** ABSTAIN: The sources do not list the Electrical Engineering Technology department’s student hours.

**Judge, correctness:** incorrect: The gold answer indicates that a student-hours page exists and is labeled Fall 2024, whereas the response incorrectly says the sources do not list student hours.

**Judge, faithfulness:** no: The response's claim that the sources do not list student hours is contradicted by source 1, which lists a Summer 2026 advisement schedule with dates and times for Electrical Engineering Technology-related advisors.

**What the judge names, copied from its reasons:**

- correctness (incorrect): The gold answer indicates that a student-hours page exists and is labeled Fall 2024, whereas the response incorrectly says the sources do not list student hours.
- faithfulness (no): The response's claim that the sources do not list student hours is contradicted by source 1, which lists a Summer 2026 advisement schedule with dates and times for Electrical Engineering Technology-related advisors.

**Sources the answerer received (5):**

<details><summary>[1] https://www.citytech.cuny.edu/advisement/virtual-advisors.aspx | Faculty Advisors > Electrical Engineering & Telecommunication Technologies | rank 1</summary>

```
[1] id: page/advisement/virtual-advisors#15
source: https://www.citytech.cuny.edu/advisement/virtual-advisors.aspx
heading: Faculty Advisors > Electrical Engineering & Telecommunication Technologies
terms: Summer 2026

Faculty Advisors > Electrical Engineering & Telecommunication Technologies

(AAS & BTech in Electrical Engineering Technology; AAS & BTech in Telecommunication Engineering Technology)

Please connect with one of our full-time faculty advisors.

| Summer 2026 Advisement Schedule<br>Please email advisors prior to advisement date to schedule |  |  |  |  |
| --- | --- | --- | --- | --- |
| **Date** | **Time** | **Mode** | **Advisor** | **Email** |
| **JULY ADVISEMENT** |  |  |  |  |
| Wednesday, July 8 | 11a - 5p | Virtual | Prof. A. D. Hossain | ahossain@citytech.cuny.edu |
| Wednesday, July 15 | 10a - 5p | Virtual | Prof. Z. Marantz | zmarantz@citytech.cuny.edu |
| Monday, July 20 | 10a - 5p | Virtual | Prof. M. Razani | mrazani@citytech.cuny.edu |
| **AUGUST ADVISEMENT** |  |  |  |  |
| Tuesday, August 11 | 10a - 5p | In-Person | Prof. Z. Marantz | zmarantz@citytech.cuny.edu |
| Wednesday, August 12 | 10a - 5p | Virtual | Prof. Z. Marantz | zmarantz@citytech.cuny.edu |
| Tuesday, August 18 | 10a - 5p | In-Person | Prof. M. Razani | mrazani@citytech.cuny.edu |
| Wednesday, August 19 | 10a - 5p | In-Person | Prof. M. Razani | mrazani@citytech.cuny.edu |
| Wednesday, August 19 | 10a - 5p | Virtual | Prof. Z. Marantz | zmarantz@citytech.cuny.edu |
| Thursday, August 20 | 10a - 5p | In-Person | Prof. M. Razani | mrazani@citytech.cuny.edu |
| Wednesday, August 26 | 10a - 5p | Virtual | Prof. Z. Marantz | zmarantz@citytech.cuny.edu |
| Thursday, August 27 | 10a - 5p | Virtual | Prof. M. Razani | mrazani@citytech.cuny.edu |

| Advisor | Email |
| --- | --- |
| Prof. L. Geng | lgeng@citytech.cuny.edu |
| Prof. A. Goykadosh | AGoykadosh@citytech.cuny.edu |
| Prof. Hassebo | ahmed.hassebo10@citytech.cuny.edu |
| Prof. D. Hossain | AHossain@citytech.cuny.edu |
| Prof. M. Kalechman | mkalechman@citytech.cuny.edu |
| Prof. H. Marandi | hamid.marandi02@citytech.cuny.edu |
| Prof. Z. Marantz | zmarantz@citytech.cuny.edu |
| Prof. M. Razani | mrazani@citytech.cuny.edu |
| Prof. MA. Ummy | maummy@citytech.cuny.edu |
| Prof. V. Vladutescu | vvladutescu@citytech.cuny.edu |
| Prof. X. Wei | xwei@citytech.cuny.edu |
```

</details>

<details><summary>[2] data/pdfs/EET-NYT-2026-09-10-19-16-28.pdf | Electrical Engineering Technology - BTECH - Bachelor of Technology > General > Advisement Information | rank 2</summary>

```
[2] id: dept/EET-NYT/program-electrical-engineering-technology-btech#6
source: data/pdfs/EET-NYT-2026-09-10-19-16-28.pdf
heading: Electrical Engineering Technology - BTECH - Bachelor of Technology > General > Advisement Information

Electrical Engineering Technology - BTECH - Bachelor of Technology > General > Advisement Information

Advising hours are scheduled each semester, posted on the college and department websites and the department's bulletin boards, and emailed to all students.

Explore the Electrical and Telecommunications Engineering Technology Department on the City Tech website.

**Certifications** are granted by the NSPE (National Society of Professional Engineers), ETA (Electronics Technicians Association), and IEEE (Institute of Electrical and Electronics Engineers) student chapters at ETET-NYCCT.

These chapters play important roles for engineering technology students at the New York City College of Technology.

The main goal of these student chapters is to benefit all its student members through industry exposure and support in achieving several professional engineering licensure-categories for those who are interested.
```

</details>

<details><summary>[3] data/pdfs/EET-NYT-2026-09-10-19-16-28.pdf | Electrical Engineering Technology - AAS - Associate in Applied Science > General > Advisement Information | rank 3</summary>

```
[3] id: dept/EET-NYT/program-electrical-engineering-technology-aas#5
source: data/pdfs/EET-NYT-2026-09-10-19-16-28.pdf
heading: Electrical Engineering Technology - AAS - Associate in Applied Science > General > Advisement Information

Electrical Engineering Technology - AAS - Associate in Applied Science > General > Advisement Information

Advising hours are scheduled each semester, posted on the college and department websites and the department's bulletin boards, and emailed to all students.

Explore the Electrical and Telecommunications Engineering Technology Department on the City Tech website.

**Certifications** are granted by the NSPE (National Society of Professional Engineers), ETA (Electronics Technicians Association), and IEEE (Institute of Electrical and Electronics Engineers) student chapters at ETET-NYCCT.

These chapters play important roles for engineering technology students at the New York City College of Technology.

The main goal of these student chapters is to benefit all its student members through industry exposure and support in achieving several professional engineering licensure-categories for those who are interested.
```

</details>

<details><summary>[4] data/pdfs/EET-NYT-2026-09-10-19-16-28.pdf | Electrical Engineering Technology - AAS - Associate in Applied Science > Degree Maps > Degree map: Electrical Engineering Technology | rank 4</summary>

```
[4] id: dept/EET-NYT/program-electrical-engineering-technology-aas#9
source: data/pdfs/EET-NYT-2026-09-10-19-16-28.pdf
heading: Electrical Engineering Technology - AAS - Associate in Applied Science > Degree Maps > Degree map: Electrical Engineering Technology

Electrical Engineering Technology - AAS - Associate in Applied Science > Degree Maps > Degree map: Electrical Engineering Technology

Total degree map credits: 67 - 69. Effective catalog year (as printed): 2027 -.

A recommended semester-by-semester plan for full-time students.

#### Year 1 Fall (18 - 19 actual credits, 18 - 21 progress credits)

| Requirement | Rule notes | Notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- | --- |
| ENG 1101 - English Composition I OR ENG 1101CO - English Composition I (with corequisite support) OR ENG 1101ML - English Composition I (with support for multilingual writers) | CUNY proficiency in English; ENG 1101 Corequisite; Pre-requisite of English Proficiency Index scores from 51 to 64 OR CATW scores from 90 to 104 OR ESOL 21W (earned 'S' grade) OR department approval is required. | fulfills English Composition requirement | 3 | 3 - 5 | 4 - 6 |
| MAT 1375 - Precalculus | PRE: MAT 1275 or MAT 1275CO OR Meet the Math Placement for MAT 1375 | fulfills Mathematical and Quantitative Reasoning requirement | 4 | 4 | 4 |
| EET 1102 - Techniques of Electrical Technology | Pre/corequisite of MAT 1275 OR prerequisite of MAT1275CO. | - | 2 | 2 | 3 |
| EET 1122 - Circuit Analysis I | Pre- corequisites of EET 1102 AND MAT 1275 or higher AND PHYS 1433 or PHYS 1441. | - | 4 | 4 | 6 |
| EET 1202 - Electrical Drafting | Pre/Co-requisite of EET 1102 is required. | - | 1 | 1 | 3 |
| PHYS 1433 - General Physics I: Algebra Based OR PHYS 1441 - General Physics I: Calculus Based | PRE: MAT 1275CO or higher or PRE/CO: MAT 1275; Pre/Co-requisite of MAT 1475 is required. | fulfills Life and Physical Sciences requirement | 4 - 5 | 4 - 5 | 6 - 7 |

#### Year 1 Spring (18 - 19 credits)

| Requirement | Rule notes | Notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- | --- |
| EET 1222 - Circuit Analysis II | PREREQUISITE OF EET 1122, PREREQUISITE OR COREQUISITE OF MAT 1375 OR HIGHER, ENG 1101, PHYS 1434 OR PHYS 1442 | - | 5 | 5 | 6 |
| EET 1240 - Electronics | Pre/Co-requisite of EET 1222 is required. | - | 4 | 4 | 4 |
| EET 1241 - Electronics Laboratory | Pre or corequisites of EET 1240 and EET 1222. | - | 1 | 1 | 3 |
| MAT 1475 - Calculus I | PRE: MAT 1375 OR Meet the Math Placement for MAT 1475 | fulfills Scientific World requirement | 4 | 4 | 4 |
| PHYS 1434 - General Physics II: Algebra Based OR PHYS 1441 - General Physics I: Calculus Based | Pre-requisite of PHYS 1433 is required.; Pre/Co-requisite of MAT 1475 is required. | fulfills Scientific World requirement | 4 - 5 | 4 - 5 | 6 - 7 |

#### Year 2 Fall (17 credits)

| Requirement | Rule notes | Notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- | --- |
| EET 2122 - Advanced Circuit Analysis | PRE: EET 1222 CO: MAT 1475 OR HIGHER | - | 3 | 3 | 4 |
| EET 2140 - Communications Electronics | PRE: EET 1240 | - | 3 | 3 | 3 |
| EET 2141 - Communications Electronics Laboratory | Prerequisite: EET 1241; Pre- or corequisite: EET 2140 | - | 1 | 1 | 3 |
| EET 2150 - Electric Machines Theory | PRE: EET 1222, PHYS 1433 | - | 3 | 3 | 3 |
| EET 2162 - Digital Electronics I | PRE: EET 1240, EET 1241 | - | 3 | 3 | 5 |
| EET 2171 - Projects Laboratory | PRE: EET 1202, EET 1241 | - | 1 | 1 | 3 |
| ENG 1121 - English Composition II | PRE: ENG1101 or ENG1101CO or ENG1101ML | fulfills English Composition requirement | 3 | 3 | 3 |

#### Year 2 Spring (14 credits)

| Requirement | Rule notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- |
| EET 2220 - Electronic Controls | PREREQUISITE OF EET 2122 & MAT 1475 OR HIGHER | 3 | 3 | 3 |
| EET 2251 - Electric Machines Laboratory | PRE: EET 2150 | 1 | 1 | 3 |
| EET 2262 - Digital Electronic II | Prerequisite: EET 2162; Pre- or corequisite: EET 2271 | 3 | 3 | 5 |
| EET 2271 - Circuit Analysis Laboratory | Prerequisite: EET 2171; Pre- or corequisite: EET 2162 | 1 | 1 | 3 |
| Flexible Core Creative Expression | - | 3 | 3 | - |
| Flexible Core World Cultures and Global Issues | - | 3 | 3 | - |
```

</details>

<details><summary>[5] data/pdfs/EET-NYT-2026-09-10-19-16-28.pdf | Electrical Engineering Technology - BTECH - Bachelor of Technology > Degree Maps > Degree map: Electrical Engineering Technology | rank 5</summary>

```
[5] id: dept/EET-NYT/program-electrical-engineering-technology-btech#10
source: data/pdfs/EET-NYT-2026-09-10-19-16-28.pdf
heading: Electrical Engineering Technology - BTECH - Bachelor of Technology > Degree Maps > Degree map: Electrical Engineering Technology

Electrical Engineering Technology - BTECH - Bachelor of Technology > Degree Maps > Degree map: Electrical Engineering Technology

Total degree map credits: 131 - 133. Effective catalog year (as printed): 2027 -.

A recommended semester-by-semester plan for full-time students.

#### Year 1 Fall (18 - 19 actual credits, 18 - 21 progress credits)

| Requirement | Rule notes | Notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- | --- |
| ENG 1101 - English Composition I OR ENG 1101CO - English Composition I (with corequisite support) OR ENG 1101ML - English Composition I (with support for multilingual writers) | CUNY proficiency in English; ENG 1101 Corequisite; Pre-requisite of English Proficiency Index scores from 51 to 64 OR CATW scores from 90 to 104 OR ESOL 21W (earned 'S' grade) OR department approval is required. | fulfills English Composition requirement | 3 | 3 - 5 | 4 - 6 |
| MAT 1375 - Precalculus | PRE: MAT 1275 or MAT 1275CO OR Meet the Math Placement for MAT 1375 | fulfills Mathematical and Quantitative Reasoning requirement | 4 | 4 | 4 |
| EET 1102 - Techniques of Electrical Technology | Pre/corequisite of MAT 1275 OR prerequisite of MAT1275CO. | - | 2 | 2 | 3 |
| EET 1122 - Circuit Analysis I | Pre- corequisites of EET 1102 AND MAT 1275 or higher AND PHYS 1433 or PHYS 1441. | - | 4 | 4 | 6 |
| EET 1202 - Electrical Drafting | Pre/Co-requisite of EET 1102 is required. | - | 1 | 1 | 3 |
| PHYS 1433 - General Physics I: Algebra Based OR PHYS 1441 - General Physics I: Calculus Based | PRE: MAT 1275CO or higher or PRE/CO: MAT 1275; Pre/Co-requisite of MAT 1475 is required. | fulfills Life and Physical Sciences requirement | 4 - 5 | 4 - 5 | 6 - 7 |

#### Year 1 Spring (18 - 19 credits)

| Requirement | Rule notes | Notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- | --- |
| EET 1222 - Circuit Analysis II | PREREQUISITE OF EET 1122, PREREQUISITE OR COREQUISITE OF MAT 1375 OR HIGHER, ENG 1101, PHYS 1434 OR PHYS 1442 | - | 5 | 5 | 6 |
| EET 1240 - Electronics | Pre/Co-requisite of EET 1222 is required. | - | 4 | 4 | 4 |
| EET 1241 - Electronics Laboratory | Pre or corequisites of EET 1240 and EET 1222. | - | 1 | 1 | 3 |
| MAT 1475 - Calculus I | PRE: MAT 1375 OR Meet the Math Placement for MAT 1475 | fulfills Scientific World requirement | 4 | 4 | 4 |
| PHYS 1434 - General Physics II: Algebra Based OR PHYS 1441 - General Physics I: Calculus Based | Pre-requisite of PHYS 1433 is required.; Pre/Co-requisite of MAT 1475 is required. | fulfills Scientific World requirement | 4 - 5 | 4 - 5 | 6 - 7 |

#### Year 2 Fall (17 credits)

| Requirement | Rule notes | Notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- | --- |
| EET 2122 - Advanced Circuit Analysis | PRE: EET 1222 CO: MAT 1475 OR HIGHER | - | 3 | 3 | 4 |
| EET 2140 - Communications Electronics | PRE: EET 1240 | - | 3 | 3 | 3 |
| EET 2141 - Communications Electronics Laboratory | Prerequisite: EET 1241; Pre- or corequisite: EET 2140 | - | 1 | 1 | 3 |
| EET 2150 - Electric Machines Theory | PRE: EET 1222, PHYS 1433 | - | 3 | 3 | 3 |
| EET 2162 - Digital Electronics I | PRE: EET 1240, EET 1241 | - | 3 | 3 | 5 |
| EET 2171 - Projects Laboratory | PRE: EET 1202, EET 1241 | - | 1 | 1 | 3 |
| ENG 1121 - English Composition II | PRE: ENG1101 or ENG1101CO or ENG1101ML | fulfills English Composition requirement | 3 | 3 | 3 |

#### Year 2 Spring (14 credits)

| Requirement | Rule notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- |
| EET 2220 - Electronic Controls | PREREQUISITE OF EET 2122 & MAT 1475 OR HIGHER | 3 | 3 | 3 |
| EET 2251 - Electric Machines Laboratory | PRE: EET 2150 | 1 | 1 | 3 |
| EET 2262 - Digital Electronic II | Prerequisite: EET 2162; Pre- or corequisite: EET 2271 | 3 | 3 | 5 |
| EET 2271 - Circuit Analysis Laboratory | Prerequisite: EET 2171; Pre- or corequisite: EET 2162 | 1 | 1 | 3 |
| Flexible Core Creative Expression | - | 3 | 3 | - |
| Flexible Core World Cultures and Global Issues | - | 3 | 3 | - |

#### Year 3 Fall (17 credits)

| Requirement | Rule notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- |
| EET 3102 - Signals & Systems | Pre/Co-requisite of MAT 1575 AND A.A.S. degree in Electrical Engineering Technology or departmental approval are required. | 4 | 4 | 6 |
| EET 3112 - Advanced Microcontroller & Embedded System Design | Pre/Co-requisite of MAT 1575 AND A.A.S. degree in Electrical Engineering Technology or departmental approval are required. | 3 | 3 | 5 |
| EET 3122 - Sensors and Instruments | Pre/Co-requisite of MAT 1575 AND A.A.S. degree in Electrical Engineering Technology or departmental approval are required. | 3 | 3 | 4 |
| ENG 2575 - Technical Writing | Pre-requisite of ENG 1121 is required. | 3 | 3 | 3 |
| MAT 1575 - Calculus II | PREREQUISITE OF MAT 1475, MUST NOT HAVE PASSED MAT 2675 | 4 | 4 | 4 |

#### Year 3 Spring (17 credits)

| Requirement | Rule notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- |
| EET 3202 - Principles of Communication Systems | PRE:EET 3102 CO:MAT 1372/2572 | 4 | 4 | 6 |
| EET 3212 - Control Systems | PRE: EET 3102, MAT 1575 | 4 | 4 | 6 |
| EET 3222 - Power Electronics | PRE: EET 3102 | 3 | 3 | 5 |
| MAT 1372 - Statistics with Probability | Prerequisite of MAT 1275CO OR MAT 1275 OR higher. Must not have taken MAT 2572. | 3 | 3 | 4 |
| Speech/Oral Communication | - | 3 | 3 | - |

#### Year 4 Fall (15 credits)

| Requirement | Rule notes | Notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- | --- |
| ECON 1101 - Macroeconomics | CUNY proficiency in English and Mathematics | fulfills US Experience in Its Diversity requirement | 3 | 3 | 3 |
| EET 4102 - Electrical Power Systems | PRE: EET 3222 | - | 3 | 3 | 3 |
| EET 4112 - Applied Mechatronics | PRE: EET3212 | - | 3 | 3 | 4 |
| Electrical Engineering Technical Elective | - | - | 3 | 3 | - |
| Interdisciplinary Course | - | - | 3 | 3 | - |

#### Year 4 Spring (15 credits)

| Requirement | Rule notes | Notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- | --- |
| EET 4202 - Digital Signal Processing | PRE: EET 4112 | - | 3 | 3 | 4 |
| EET 4212 - Capstone Project | PRE: EET4112 CO: EET4202 | - | 3 | 3 | 4 |
| ENG 2570 - Writing in the Workplace | PRE: ENG 1121 OR ENG 1133 | - | 3 | 3 | 3 |
| PHIL 2106 - Philosophy of Technology | PRE: ENG1101 or ENG1101CO or ENG1101ML | fulfills Individual and Society requirement | 3 | 3 | 3 |
| Electrical Engineering Technical Elective | - | - | 3 | 3 | - |
```

</details>

**My verdict:** correctness  / faithfulness 

## q15 (time_sensitive): stored baseline answer, arm OFF run 1 (rubric v3 verdicts), run `baseline-dev-60-v3`

**Question:** What are the student hours for the Electrical Engineering Technology department?

**Gold answer:** The only student-hours page lists hours labeled Fall 2024 (a table by faculty member and weekday, with times and rooms or Zoom). That is not the current term (Fall 2026), so the answer must say the hours are labeled Fall 2024 and not present them as current, and should point the student to the department office to confirm. (Abstaining with the department contact is also acceptable.)

**Model's answer:** ABSTAIN: The sources do not provide the Electrical Engineering Technology department’s student hours.

**Judge, correctness:** incorrect: The gold answer requires noting that the available student-hours page is labeled Fall 2024 and advising confirmation, whereas the response simply says no hours are provided.

**Judge, faithfulness:** yes: The supplied numbered sources do not provide specific Electrical Engineering Technology student hours, so the abstention's factual statement is supported by their absence.

**What the judge names, copied from its reasons:**

- correctness (incorrect): The gold answer requires noting that the available student-hours page is labeled Fall 2024 and advising confirmation, whereas the response simply says no hours are provided.

**Sources the answerer received (5):**

<details><summary>[1] data/pdfs/EET-NYT-2026-09-10-19-16-28.pdf | Electrical Engineering Technology - BTECH - Bachelor of Technology > General > Advisement Information | rank 1</summary>

```
[1] id: dept/EET-NYT/program-electrical-engineering-technology-btech#6
source: data/pdfs/EET-NYT-2026-09-10-19-16-28.pdf
heading: Electrical Engineering Technology - BTECH - Bachelor of Technology > General > Advisement Information

Electrical Engineering Technology - BTECH - Bachelor of Technology > General > Advisement Information

Advising hours are scheduled each semester, posted on the college and department websites and the department's bulletin boards, and emailed to all students.

Explore the Electrical and Telecommunications Engineering Technology Department on the City Tech website.

**Certifications** are granted by the NSPE (National Society of Professional Engineers), ETA (Electronics Technicians Association), and IEEE (Institute of Electrical and Electronics Engineers) student chapters at ETET-NYCCT.

These chapters play important roles for engineering technology students at the New York City College of Technology.

The main goal of these student chapters is to benefit all its student members through industry exposure and support in achieving several professional engineering licensure-categories for those who are interested.
```

</details>

<details><summary>[2] data/pdfs/EET-NYT-2026-09-10-19-16-28.pdf | Electrical Engineering Technology - AAS - Associate in Applied Science > General > Advisement Information | rank 2</summary>

```
[2] id: dept/EET-NYT/program-electrical-engineering-technology-aas#5
source: data/pdfs/EET-NYT-2026-09-10-19-16-28.pdf
heading: Electrical Engineering Technology - AAS - Associate in Applied Science > General > Advisement Information

Electrical Engineering Technology - AAS - Associate in Applied Science > General > Advisement Information

Advising hours are scheduled each semester, posted on the college and department websites and the department's bulletin boards, and emailed to all students.

Explore the Electrical and Telecommunications Engineering Technology Department on the City Tech website.

**Certifications** are granted by the NSPE (National Society of Professional Engineers), ETA (Electronics Technicians Association), and IEEE (Institute of Electrical and Electronics Engineers) student chapters at ETET-NYCCT.

These chapters play important roles for engineering technology students at the New York City College of Technology.

The main goal of these student chapters is to benefit all its student members through industry exposure and support in achieving several professional engineering licensure-categories for those who are interested.
```

</details>

<details><summary>[3] data/pdfs/EET-NYT-2026-09-10-19-16-28.pdf | Electrical Engineering Technology - AAS - Associate in Applied Science > Degree Maps > Degree map: Electrical Engineering Technology | rank 3</summary>

```
[3] id: dept/EET-NYT/program-electrical-engineering-technology-aas#9
source: data/pdfs/EET-NYT-2026-09-10-19-16-28.pdf
heading: Electrical Engineering Technology - AAS - Associate in Applied Science > Degree Maps > Degree map: Electrical Engineering Technology

Electrical Engineering Technology - AAS - Associate in Applied Science > Degree Maps > Degree map: Electrical Engineering Technology

Total degree map credits: 67 - 69. Effective catalog year (as printed): 2027 -.

A recommended semester-by-semester plan for full-time students.

#### Year 1 Fall (18 - 19 actual credits, 18 - 21 progress credits)

| Requirement | Rule notes | Notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- | --- |
| ENG 1101 - English Composition I OR ENG 1101CO - English Composition I (with corequisite support) OR ENG 1101ML - English Composition I (with support for multilingual writers) | CUNY proficiency in English; ENG 1101 Corequisite; Pre-requisite of English Proficiency Index scores from 51 to 64 OR CATW scores from 90 to 104 OR ESOL 21W (earned 'S' grade) OR department approval is required. | fulfills English Composition requirement | 3 | 3 - 5 | 4 - 6 |
| MAT 1375 - Precalculus | PRE: MAT 1275 or MAT 1275CO OR Meet the Math Placement for MAT 1375 | fulfills Mathematical and Quantitative Reasoning requirement | 4 | 4 | 4 |
| EET 1102 - Techniques of Electrical Technology | Pre/corequisite of MAT 1275 OR prerequisite of MAT1275CO. | - | 2 | 2 | 3 |
| EET 1122 - Circuit Analysis I | Pre- corequisites of EET 1102 AND MAT 1275 or higher AND PHYS 1433 or PHYS 1441. | - | 4 | 4 | 6 |
| EET 1202 - Electrical Drafting | Pre/Co-requisite of EET 1102 is required. | - | 1 | 1 | 3 |
| PHYS 1433 - General Physics I: Algebra Based OR PHYS 1441 - General Physics I: Calculus Based | PRE: MAT 1275CO or higher or PRE/CO: MAT 1275; Pre/Co-requisite of MAT 1475 is required. | fulfills Life and Physical Sciences requirement | 4 - 5 | 4 - 5 | 6 - 7 |

#### Year 1 Spring (18 - 19 credits)

| Requirement | Rule notes | Notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- | --- |
| EET 1222 - Circuit Analysis II | PREREQUISITE OF EET 1122, PREREQUISITE OR COREQUISITE OF MAT 1375 OR HIGHER, ENG 1101, PHYS 1434 OR PHYS 1442 | - | 5 | 5 | 6 |
| EET 1240 - Electronics | Pre/Co-requisite of EET 1222 is required. | - | 4 | 4 | 4 |
| EET 1241 - Electronics Laboratory | Pre or corequisites of EET 1240 and EET 1222. | - | 1 | 1 | 3 |
| MAT 1475 - Calculus I | PRE: MAT 1375 OR Meet the Math Placement for MAT 1475 | fulfills Scientific World requirement | 4 | 4 | 4 |
| PHYS 1434 - General Physics II: Algebra Based OR PHYS 1441 - General Physics I: Calculus Based | Pre-requisite of PHYS 1433 is required.; Pre/Co-requisite of MAT 1475 is required. | fulfills Scientific World requirement | 4 - 5 | 4 - 5 | 6 - 7 |

#### Year 2 Fall (17 credits)

| Requirement | Rule notes | Notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- | --- |
| EET 2122 - Advanced Circuit Analysis | PRE: EET 1222 CO: MAT 1475 OR HIGHER | - | 3 | 3 | 4 |
| EET 2140 - Communications Electronics | PRE: EET 1240 | - | 3 | 3 | 3 |
| EET 2141 - Communications Electronics Laboratory | Prerequisite: EET 1241; Pre- or corequisite: EET 2140 | - | 1 | 1 | 3 |
| EET 2150 - Electric Machines Theory | PRE: EET 1222, PHYS 1433 | - | 3 | 3 | 3 |
| EET 2162 - Digital Electronics I | PRE: EET 1240, EET 1241 | - | 3 | 3 | 5 |
| EET 2171 - Projects Laboratory | PRE: EET 1202, EET 1241 | - | 1 | 1 | 3 |
| ENG 1121 - English Composition II | PRE: ENG1101 or ENG1101CO or ENG1101ML | fulfills English Composition requirement | 3 | 3 | 3 |

#### Year 2 Spring (14 credits)

| Requirement | Rule notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- |
| EET 2220 - Electronic Controls | PREREQUISITE OF EET 2122 & MAT 1475 OR HIGHER | 3 | 3 | 3 |
| EET 2251 - Electric Machines Laboratory | PRE: EET 2150 | 1 | 1 | 3 |
| EET 2262 - Digital Electronic II | Prerequisite: EET 2162; Pre- or corequisite: EET 2271 | 3 | 3 | 5 |
| EET 2271 - Circuit Analysis Laboratory | Prerequisite: EET 2171; Pre- or corequisite: EET 2162 | 1 | 1 | 3 |
| Flexible Core Creative Expression | - | 3 | 3 | - |
| Flexible Core World Cultures and Global Issues | - | 3 | 3 | - |
```

</details>

<details><summary>[4] data/pdfs/EET-NYT-2026-09-10-19-16-28.pdf | Electrical Engineering Technology - BTECH - Bachelor of Technology > Degree Maps > Degree map: Electrical Engineering Technology | rank 4</summary>

```
[4] id: dept/EET-NYT/program-electrical-engineering-technology-btech#10
source: data/pdfs/EET-NYT-2026-09-10-19-16-28.pdf
heading: Electrical Engineering Technology - BTECH - Bachelor of Technology > Degree Maps > Degree map: Electrical Engineering Technology

Electrical Engineering Technology - BTECH - Bachelor of Technology > Degree Maps > Degree map: Electrical Engineering Technology

Total degree map credits: 131 - 133. Effective catalog year (as printed): 2027 -.

A recommended semester-by-semester plan for full-time students.

#### Year 1 Fall (18 - 19 actual credits, 18 - 21 progress credits)

| Requirement | Rule notes | Notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- | --- |
| ENG 1101 - English Composition I OR ENG 1101CO - English Composition I (with corequisite support) OR ENG 1101ML - English Composition I (with support for multilingual writers) | CUNY proficiency in English; ENG 1101 Corequisite; Pre-requisite of English Proficiency Index scores from 51 to 64 OR CATW scores from 90 to 104 OR ESOL 21W (earned 'S' grade) OR department approval is required. | fulfills English Composition requirement | 3 | 3 - 5 | 4 - 6 |
| MAT 1375 - Precalculus | PRE: MAT 1275 or MAT 1275CO OR Meet the Math Placement for MAT 1375 | fulfills Mathematical and Quantitative Reasoning requirement | 4 | 4 | 4 |
| EET 1102 - Techniques of Electrical Technology | Pre/corequisite of MAT 1275 OR prerequisite of MAT1275CO. | - | 2 | 2 | 3 |
| EET 1122 - Circuit Analysis I | Pre- corequisites of EET 1102 AND MAT 1275 or higher AND PHYS 1433 or PHYS 1441. | - | 4 | 4 | 6 |
| EET 1202 - Electrical Drafting | Pre/Co-requisite of EET 1102 is required. | - | 1 | 1 | 3 |
| PHYS 1433 - General Physics I: Algebra Based OR PHYS 1441 - General Physics I: Calculus Based | PRE: MAT 1275CO or higher or PRE/CO: MAT 1275; Pre/Co-requisite of MAT 1475 is required. | fulfills Life and Physical Sciences requirement | 4 - 5 | 4 - 5 | 6 - 7 |

#### Year 1 Spring (18 - 19 credits)

| Requirement | Rule notes | Notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- | --- |
| EET 1222 - Circuit Analysis II | PREREQUISITE OF EET 1122, PREREQUISITE OR COREQUISITE OF MAT 1375 OR HIGHER, ENG 1101, PHYS 1434 OR PHYS 1442 | - | 5 | 5 | 6 |
| EET 1240 - Electronics | Pre/Co-requisite of EET 1222 is required. | - | 4 | 4 | 4 |
| EET 1241 - Electronics Laboratory | Pre or corequisites of EET 1240 and EET 1222. | - | 1 | 1 | 3 |
| MAT 1475 - Calculus I | PRE: MAT 1375 OR Meet the Math Placement for MAT 1475 | fulfills Scientific World requirement | 4 | 4 | 4 |
| PHYS 1434 - General Physics II: Algebra Based OR PHYS 1441 - General Physics I: Calculus Based | Pre-requisite of PHYS 1433 is required.; Pre/Co-requisite of MAT 1475 is required. | fulfills Scientific World requirement | 4 - 5 | 4 - 5 | 6 - 7 |

#### Year 2 Fall (17 credits)

| Requirement | Rule notes | Notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- | --- |
| EET 2122 - Advanced Circuit Analysis | PRE: EET 1222 CO: MAT 1475 OR HIGHER | - | 3 | 3 | 4 |
| EET 2140 - Communications Electronics | PRE: EET 1240 | - | 3 | 3 | 3 |
| EET 2141 - Communications Electronics Laboratory | Prerequisite: EET 1241; Pre- or corequisite: EET 2140 | - | 1 | 1 | 3 |
| EET 2150 - Electric Machines Theory | PRE: EET 1222, PHYS 1433 | - | 3 | 3 | 3 |
| EET 2162 - Digital Electronics I | PRE: EET 1240, EET 1241 | - | 3 | 3 | 5 |
| EET 2171 - Projects Laboratory | PRE: EET 1202, EET 1241 | - | 1 | 1 | 3 |
| ENG 1121 - English Composition II | PRE: ENG1101 or ENG1101CO or ENG1101ML | fulfills English Composition requirement | 3 | 3 | 3 |

#### Year 2 Spring (14 credits)

| Requirement | Rule notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- |
| EET 2220 - Electronic Controls | PREREQUISITE OF EET 2122 & MAT 1475 OR HIGHER | 3 | 3 | 3 |
| EET 2251 - Electric Machines Laboratory | PRE: EET 2150 | 1 | 1 | 3 |
| EET 2262 - Digital Electronic II | Prerequisite: EET 2162; Pre- or corequisite: EET 2271 | 3 | 3 | 5 |
| EET 2271 - Circuit Analysis Laboratory | Prerequisite: EET 2171; Pre- or corequisite: EET 2162 | 1 | 1 | 3 |
| Flexible Core Creative Expression | - | 3 | 3 | - |
| Flexible Core World Cultures and Global Issues | - | 3 | 3 | - |

#### Year 3 Fall (17 credits)

| Requirement | Rule notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- |
| EET 3102 - Signals & Systems | Pre/Co-requisite of MAT 1575 AND A.A.S. degree in Electrical Engineering Technology or departmental approval are required. | 4 | 4 | 6 |
| EET 3112 - Advanced Microcontroller & Embedded System Design | Pre/Co-requisite of MAT 1575 AND A.A.S. degree in Electrical Engineering Technology or departmental approval are required. | 3 | 3 | 5 |
| EET 3122 - Sensors and Instruments | Pre/Co-requisite of MAT 1575 AND A.A.S. degree in Electrical Engineering Technology or departmental approval are required. | 3 | 3 | 4 |
| ENG 2575 - Technical Writing | Pre-requisite of ENG 1121 is required. | 3 | 3 | 3 |
| MAT 1575 - Calculus II | PREREQUISITE OF MAT 1475, MUST NOT HAVE PASSED MAT 2675 | 4 | 4 | 4 |

#### Year 3 Spring (17 credits)

| Requirement | Rule notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- |
| EET 3202 - Principles of Communication Systems | PRE:EET 3102 CO:MAT 1372/2572 | 4 | 4 | 6 |
| EET 3212 - Control Systems | PRE: EET 3102, MAT 1575 | 4 | 4 | 6 |
| EET 3222 - Power Electronics | PRE: EET 3102 | 3 | 3 | 5 |
| MAT 1372 - Statistics with Probability | Prerequisite of MAT 1275CO OR MAT 1275 OR higher. Must not have taken MAT 2572. | 3 | 3 | 4 |
| Speech/Oral Communication | - | 3 | 3 | - |

#### Year 4 Fall (15 credits)

| Requirement | Rule notes | Notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- | --- |
| ECON 1101 - Macroeconomics | CUNY proficiency in English and Mathematics | fulfills US Experience in Its Diversity requirement | 3 | 3 | 3 |
| EET 4102 - Electrical Power Systems | PRE: EET 3222 | - | 3 | 3 | 3 |
| EET 4112 - Applied Mechatronics | PRE: EET3212 | - | 3 | 3 | 4 |
| Electrical Engineering Technical Elective | - | - | 3 | 3 | - |
| Interdisciplinary Course | - | - | 3 | 3 | - |

#### Year 4 Spring (15 credits)

| Requirement | Rule notes | Notes | Actual Credits | Progress Credits | Contact Hours |
| --- | --- | --- | --- | --- | --- |
| EET 4202 - Digital Signal Processing | PRE: EET 4112 | - | 3 | 3 | 4 |
| EET 4212 - Capstone Project | PRE: EET4112 CO: EET4202 | - | 3 | 3 | 4 |
| ENG 2570 - Writing in the Workplace | PRE: ENG 1121 OR ENG 1133 | - | 3 | 3 | 3 |
| PHIL 2106 - Philosophy of Technology | PRE: ENG1101 or ENG1101CO or ENG1101ML | fulfills Individual and Society requirement | 3 | 3 | 3 |
| Electrical Engineering Technical Elective | - | - | 3 | 3 | - |
```

</details>

<details><summary>[5] catalog_course | EET 2000 - Internship | rank 5</summary>

```
[5] id: catalog:EET 2000
source: Course catalog: EET 2000
heading: EET 2000 - Internship

EET 2000 - Internship
Credits: 3
Department: Electrical Engineering Tech
Description: Assigned field/study work applying classroom principles and theory to real-world electrical engineering technology problems. Interns assist engineers in building and testing circuits, performing hardware and software diagnostics, testing/measurements and preventive maintenance as well as generating supporting documentation. Students must maintain a log/journal to be shared in group seminars. 2 bi-weekly class hours and 130 total field hours required.        
Prerequisites: none listed in the catalog
Programs that list this course: none found
```

</details>

**My verdict:** correctness  / faithfulness 
