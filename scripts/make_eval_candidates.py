"""Write docs/eval-candidates.md: about 30 candidate eval questions for the owner to review.

    uv run python scripts/make_eval_candidates.py

Rules (docs/phase3-plan.md, step 0):
- Questions are picked from the data and from a fixed category list (SPECS below). No baseline result,
  dev or test, was used to choose or word any of them.
- Every gold answer is a DRAFT built from the source text: calendar answers are generated from
  data/calendar/calendar_events.json, prerequisite chains from the course records, other drafts are
  written here and every claim in them must appear verbatim in the gold source text (the `evidence`
  strings; the script stops if one does not). Where the sources do not settle it, the draft is TODO.
- Nothing is written to eval/questions.jsonl.
"""

import difflib
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cta.eval.questions import (  # noqa: E402
    load_gold_data,
    load_questions,
    prerequisite_tree,
    render_tree,
    tree_courses,
)
from cta.index.section_index import heading_path  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "docs" / "eval-candidates.md"
EVIDENCE = ROOT / "docs" / "eval-evidence.md"
DRAFT = "DRAFT: owner must review"
FIRST_ID = 31
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]  # fmt: skip

DATA = load_gold_data()
EVENTS = {e["id"]: e for e in json.loads((ROOT / "data/calendar/calendar_events.json").read_text())}


# ---- sources ----


def section(sid: str) -> dict:
    """The section record and its page/PDF record for an id like page/registrar/epermit#2."""
    kind, rest = sid.split("/", 1)
    rest, n = rest.rsplit("#", 1)
    folder = {"page": "pages", "dept": "departments", "pdf": "pdfs"}[kind]
    path = PROCESSED / folder / f"{rest}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    return record, record["sections"][int(n) - 1]


def source_info(sid: str) -> dict:
    """{id, source, heading, text} for a section id, a catalog:<CODE> id or a calendar event id."""
    if sid.startswith("catalog:"):
        c = DATA.courses[sid.removeprefix("catalog:")][0]
        text = (
            f"{c['code']} - {c['title']}. Credits {c['credits']}. {c.get('description') or ''} "
            f"Prerequisites: {c.get('prerequisite_text') or 'none listed'}"
        )
        return {"id": sid, "source": "catalog_course", "heading": c["code"], "text": text}
    if sid in EVENTS:
        e = EVENTS[sid]
        return {"id": sid, "source": e["source_pdf"], "heading": f"{e['term']}: {e['event']}",
                "text": f"{e['event']} {e['date_raw']} {e['weekday_raw']}"}  # fmt: skip
    record, sec = section(sid)
    return {"id": sid, "source": record.get("source_url") or record.get("source_file"),
            "heading": heading_path(sec), "text": sec["markdown"]}  # fmt: skip


def check_evidence(spec: dict, sources: list[dict]) -> None:
    blob = " ".join(s["text"] for s in sources)
    flat = re.sub(r"\s+", " ", blob)
    for needle in spec.get("evidence", []):
        if re.sub(r"\s+", " ", needle) not in flat:
            raise SystemExit(f"{spec['question']!r}: evidence not in the sources: {needle!r}")


# ---- draft answers ----


def fmt_date(e: dict) -> str:
    """'Friday, November 6, 2026' or 'December 15-21, 2026 (Tuesday-Monday)'; TBA stays TBA."""
    if not e["date_start"]:
        return "TBA (not announced)"
    start = date.fromisoformat(e["date_start"])
    if e["date_end"]:
        end = date.fromisoformat(e["date_end"])
        span = f"{MONTHS[start.month - 1]} {start.day}-{end.day}, {start.year}"
        return f"{span} ({e['weekday_raw']})"
    return f"{e['weekday_raw']}, {MONTHS[start.month - 1]} {start.day}, {start.year}"


def calendar_draft(ids: list[str]) -> str:
    parts = [f"{fmt_date(EVENTS[i])}: {EVENTS[i]['event']} [{i}]" for i in ids]
    pdf = EVENTS[ids[0]]
    note = f" (calendar PDF last updated {pdf['pdf_last_updated']}; the calendar can change)"
    return "; ".join(parts) + note


def join_and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def label(code: str) -> str:
    return f"{code} ({DATA.courses[code][0]['title'].strip()})"


def needs_quote(text: str) -> bool:
    """Quote the catalog text only where it carries a grade requirement or a major-dependent branch."""
    return bool(re.search(r"grade (of )?[a-d]\b|\b[a-d] grade|with grade|\n", text, re.I))


def node_sentence(node: dict) -> str:
    items = node["items"]
    prereqs = [label(i["code"]) for i in items if i["kind"] == "prerequisite"]
    subject = label(node["code"])
    head = f"{subject} requires {join_and(prereqs)}" if prereqs else f"{subject} has no prerequisite course"
    extra = []
    for kind, words in (("corequisite", "corequisite (taken at the same time, not a prerequisite)"),
                        ("pre- or corequisite", "pre- or corequisite (not a prerequisite)")):  # fmt: skip
        codes = [i["code"] for i in items if i["kind"] == kind]
        if codes:
            extra.append(f"{join_and(codes)} is a {words}")
    placement = [i["text"] for i in items if i["kind"] == "placement"]
    if placement:
        extra.append("also: " + "; ".join(placement))
    for i in items:
        if i["kind"] == "exclusion":
            extra.append(f"{i['code']} is an exclusion (must not have passed it), not a prerequisite")
    equivalents = [i["code"] for i in items if i["kind"] == "equivalence"]
    if equivalents:
        extra.append(f"{join_and(equivalents)} are named as equivalents, not as prerequisites")
    text = node["text"] or ""
    if text and needs_quote(text):
        extra.append("catalog text: \u201c" + re.sub(r"\s*\n\s*", " / ", text.strip()) + "\u201d")
    return head + ("; " + "; ".join(extra) if extra else "") + "."


def chain_draft(code: str) -> str:
    """Compact prose in the style of q20 and q22: each course (first time it appears, in order) with
    its direct prerequisites; placement, equivalence and exclusion text in one clause."""
    shown: list[str] = []
    sentences: list[str] = []

    def walk(node: dict) -> None:
        if node["record"] and node["code"] not in shown:
            shown.append(node["code"])
            sentences.append(node_sentence(node))
        for item in node["items"]:
            if item.get("node"):
                walk(item["node"])

    walk(prerequisite_tree(code, DATA))
    return " ".join(sentences)


def course_line(code: str) -> str:
    c = DATA.courses[code][0]
    credits = f"{c['credits']} credit" + ("" if c["credits"] == 1 else "s")
    return f"{code} ({c['title'].strip()}, {credits}): {c.get('prerequisite_text') or 'no prerequisite text'}"


def same_description(a: str, b: str) -> str:
    """Said as found in the records, never assumed."""
    same = DATA.courses[a][0]["description"] == DATA.courses[b][0]["description"]
    return "The two courses have identical descriptions" if same else (
        "The two descriptions begin the same but are not identical")


def link_titles(sid: str) -> list[str]:
    return re.findall(r"\[([^\]]+)\]\(", section(sid)[1]["markdown"])


# ---- the candidates ----
# cat: category; q: question; type/dept/split as in eval/questions.jsonl; gold: source ids;
# draft: the DRAFT gold answer (string); evidence: strings that must occur in the sources.


def spec(cat, q, type_, dept, split, gold, draft, evidence=(), note="", tags=()):
    return {"cat": cat, "question": q, "type": type_, "department": dept, "split": split,
            "gold": gold, "draft": draft, "evidence": list(evidence), "note": note,
            "tags": list(tags)}  # fmt: skip


def chain_spec(q, dept, split, code):
    codes = tree_courses(prerequisite_tree(code, DATA))
    return spec("chained prerequisite", q, "multi_chunk", dept, split,
                [f"catalog:{c}" for c in codes], chain_draft(code),
                note="Chain question (tag chain). Gold sources are every course in the tree. Needs the prerequisite-chain tool (Phase 3, step 4).",
                tags=["chain"])  # fmt: skip


SPECS = [
    # --- calendar (8) ---
    spec("calendar", "What is the last day to withdraw from a course with a grade of W in Fall 2026?",
         "time_sensitive", None, "dev", ["fall-2026-040"], calendar_draft(["fall-2026-040"])),
    spec("calendar", "What is the last day to drop a class for a 100% tuition refund in Winter 2027?",
         "time_sensitive", None, "test", ["winter-2027-003"], calendar_draft(["winter-2027-003"]),
         note="Refund date. The Winter 2027 refund rows come only from the calendar table."),
    spec("calendar", "When do classes begin in Spring 2027?", "time_sensitive", None, "dev",
         ["spring-2027-007", "spring-2027-006"], calendar_draft(["spring-2027-007", "spring-2027-006"])
         + " Both rows have the same date: classes begin on the first day of the term."),
    spec("calendar", "What is the last day to drop for a 100% tuition refund in Summer 2027?",
         "unanswerable", None, "dev", [], "ABSTAIN",
         note="No Summer 2027 calendar is published (CLAUDE.md: only Fall 2026, Winter 2027, Spring 2027). The assistant must abstain, not borrow another term's dates."),
    spec("calendar", "When do final exams start in Fall 2027?", "unanswerable", None, "test", [], "ABSTAIN",
         note="No Fall 2027 calendar. The Spring 2027 calendar lists Fall 2027 registration dates, not exam dates."),
    spec("calendar", "When are final exams this fall?", "time_sensitive", None, "dev", ["fall-2026-049"],
         calendar_draft(["fall-2026-049"]),
         note="'this fall' must resolve to Fall 2026 from today's date (eval.today is 2026-10-11)."),
    spec("calendar", "When can I register for classes next spring?", "time_sensitive", None, "dev",
         ["fall-2026-039", "fall-2026-038"],
         calendar_draft(["fall-2026-039", "fall-2026-038"])
         + " Registration opens on November 2 for all students; the October 29 date is for the listed populations only.",
         note="'next spring' must resolve to Spring 2027 from today's date. The registration dates sit in the Fall 2026 calendar."),
    spec("calendar", "What is the deadline to apply for graduation to take part in all commencement activities in Spring 2027?",
         "time_sensitive", None, "test", ["spring-2027-036"], calendar_draft(["spring-2027-036"]),
         note="Not the same as the filing period for Spring 2027 graduation, which ends May 27 (spring-2027-051)."),
    # --- chained prerequisites (3) ---
    chain_spec("What is the full prerequisite chain for CST 3602 Data Visualization?", "CST-NYT", "dev", "CST 3602"),
    chain_spec("Starting from CST 3613 (Application Development with Database), which courses do I have to take first, and what do those courses require?", "CST-NYT", "dev", "CST 3613"),
    chain_spec("What do I need to take, step by step, before EET 4202?", "EET-NYT", "test", "EET 4202"),
    # --- cross-listed (2): same description, separate records and rules ---
    spec("related pair (co-requisite variant)", "What are the prerequisites for MAT 1190CO, and how are they different from MAT 1190?",
         "lookup", "MATH-NYT", "dev", ["catalog:MAT 1190CO", "catalog:MAT 1190"],
         "MAT 1190CO: " + DATA.courses["MAT 1190CO"][0]["prerequisite_text"].strip() + " | MAT 1190: "
         + DATA.courses["MAT 1190"][0]["prerequisite_text"].strip() + " | Difference: MAT 1190 requires CUNY proficiency in mathematics and "
         "adds a note that students with credit for MAT 1275CO, MAT 1275 or higher will not receive credit for it; MAT 1190CO lists only the pre- or corequisite of ENG 1101, ENG 1101ML or ENG 1101CO.",
         evidence=["Pre- or corequisite of ENG 1101 OR ENG 1101ML OR ENG 1101CO", "CUNY proficiency in mathematics",
                   "will not receive credit for this course"],
         note="Related pair (co-requisite variant), not cross-listed: separate records and separate rules."),
    spec("cross-listed", "What are the prerequisites for EET 2171, and are they the same as for EET 2162?",
         "lookup", "EET-NYT", "test", ["catalog:EET 2171", "catalog:EET 2162"],
         "The prerequisites differ. " + same_description("EET 2171", "EET 2162") + ", but titles, credits and rules differ. "
         + course_line("EET 2171") + " | " + course_line("EET 2162"),
         evidence=["PRE: EET 1202, EET 1241", "PRE: EET 1240, EET 1241"],
         note="Cross-listed pair: separate records, same description, different title, credits and rules (checked in the records)."),
    # --- abstain (new categories) ---
    spec("abstain: account data", "What is my GPA this semester?", "unanswerable", None, "dev", [], "ABSTAIN",
         note="Needs account data (login). Out of scope."),
    spec("abstain: sections", "What days and times does MAT 1475 meet this fall?", "unanswerable", "MATH-NYT", "dev", [], "ABSTAIN",
         note="Class meeting times and sections are out of scope (q27 asks about seats, q28 about professors)."),
    spec("abstain: other department", "Who is the chair of the Biological Sciences department?", "unanswerable", None, "test", [], "ABSTAIN",
         note="A department outside the four. The advisement page lists Biological Sciences advisors (page/advisement/virtual-advisors#3), which is not the chair; check that the assistant does not present an advisor as the chair."),
    # --- advice-seeking (2): state the rules, give no advice ---
    spec("advice", "Should I take an Incomplete or withdraw from my class?", "unanswerable", None, "dev",
         ["page/registrar/incomplete#1", "page/registrar/grade-policies#1"],
         "NO ADVICE: state the rules, do not choose for the student. An Incomplete (INC) is for a student who has completed a majority of the coursework "
         "but cannot complete the whole course for reasons beyond their control, usually 1-2 assignments or exams that amount to 25% or less of the final grade; "
         "if no grade change form is submitted the INC converts to an FIN, a failing grade; students cannot graduate in a semester in which they have an incomplete. "
         "A W (Official Withdrawal) is a non-punitive grade when a class is dropped via CUNYfirst during the published withdrawal period.",
         evidence=["25% or less of the final grade", "convert automatically to an “FIN,” a failing grade",
                   "Students cannot graduate in a semester in which they have an incomplete",
                   "A non-punitive grade initiated by a student when a class is dropped via CUNYfirst during the published withdrawal period"]),
    spec("advice", "Should I sign up for the Nelnet payment plan?", "unanswerable", None, "test",
         ["page/bursar/payment-plan#1", "page/bursar/payment-plan#3"],
         "NO ADVICE: state the facts, do not say whether to enrol. Payment plan options are available for Fall, Spring and Summer terms prior to the start of the semester; "
         "enrol in CUNYfirst (Student Center, Financial Account, Account Balance, Payment Plan link). Fall 2026 plans: enrolling April 8 - June 22 gives 5 payments (July - Nov), "
         "June 23 - July 22 gives 4, July 23 - Aug 24 gives 3, Aug 25 - Sept 04 gives 2; payments are due on the 5th of the month. There are no payment plans for past-due balances.",
         evidence=["Payment plan options are available for Fall, Spring and Summer terms prior to the start of the semester",
                   "April 8 — June 22", "There are no Payment Plans for past-due balances"]),
    # --- ambiguous (2) ---
    spec("ambiguous", "Can I take a class at another college?", "ambiguous", None, "dev",
         ["page/registrar/epermit#1", "page/registrar/epermit#2"],
         "CLARIFY OR BOTH: either ask whether the other college is in CUNY or outside CUNY, or answer both cases correctly from the sources; never give one answer as if it applied to both. "
         "Facts: CUNY college: file an ePermit in CUNYfirst; eligibility rules include not being on Academic Probation, being matriculated and currently in attendance, not being newly admitted, no holds, immunizations complete. "
         "Outside CUNY: a Non-CUNY Permit Form needs approval from the Registrar and the academic department, and a Consortium Agreement is needed for financial aid; only a grade of C or higher is acceptable.",
         evidence=["Must not be on Academic Probation", "Must not have any holds on academic record",
                   "Only a grade of C or higher is acceptable from a non-CUNY school course"]),
    spec("ambiguous", "How much of my tuition do I get back if I drop a class?", "ambiguous", None, "test",
         ["page/bursar/refund-policy#4", "page/bursar/refund-policy#1", "fall-2026-004"],
         "CLARIFY OR STATE THE TERM: ask which term and when, or state the Fall 2026 (current term) schedule with the term named and say it differs by term and date; never give one percentage without the term. "
         "Facts, Fall 2026 (Bursar page): drop by August 27, 2026 for a 100% refund; by September 03 75%; by September 10 50%; by September 17 25%; "
         "withdrawing September 18 and after means 100% liability. No portion of the student activity fee, special fees or penalty fees is refundable.",
         evidence=["Last day to drop classes for 100% tuition refund", "Last day for 50% tuition refund; 50% Liability",
                   "No portion of the student activity fee, special fees or penalty fees is refundable"]),
    # --- lookup / multi_chunk across the four departments and the central offices ---
    spec("lookup", "How many times a year does the clinical Dental Hygiene program accept a class, and when are students told?",
         "multi_chunk", "DENT-NYT", "dev", ["page/DENT-NYT/faq#25", "page/DENT-NYT/faq#24"],
         "The program accepts one class each year, beginning in the Fall semester. The class is selected after Spring final grades are submitted, and the entering Fall class is notified within the first two weeks of June. "
         "Students taking summer classes or planning to transfer during the summer are not eligible for the entering Fall class.",
         evidence=["accepts one class each year, beginning in the Fall semester", "notified within the first two weeks of June"]),
    spec("lookup", "Do the science prerequisites for the Dental Hygiene program expire?", "lookup", "DENT-NYT", "dev",
         ["page/DENT-NYT/faq#12"],
         "Yes. All science courses, including BIO2311, BIO2312, and CHEM, must have been completed within five years of acceptance into the program.",
         evidence=["must have been completed within five years of acceptance into the program"]),
    spec("lookup", "What happens to my TAP if my major is still undeclared?", "lookup", None, "dev",
         ["page/advisement/continuing-students#1"],
         "If your major is listed as undeclared, TAP eligibility can be jeopardized if you have more than 30 credits in an associate program, or more than 60 credits in a bachelor's program. "
         "If you have reached 30 or 60 credits, you must formally declare a major before the 21st day of the semester.",
         evidence=["TAP eligibility can be jeopardized if you have more than 30 credits in an associate program",
                   "you must formally declare a major before the 21st day of the semester"],
         note="Advisement page (continuing and readmitted students). Gold limited to the TAP facts."),
    spec("lookup", "What happens if I fail a math course?", "lookup", "MATH-NYT", "dev", ["page/MATH-NYT/faqs#12"],
         "When you pass the course again, a grade of C or higher replaces the failing grade in your GPA calculations, but the failed course remains on your transcript. "
         "The FAQ recommends re-taking the course the very next semester (or over the summer if you fail it in the spring), using the tutoring services and your professor's office hours, "
         "looking at the prerequisites to your other required courses and talking with a faculty advisor in your department to adjust your plan for the next semester, "
         "and checking with the financial aid office about what a D or F might mean for your financial aid.",
         evidence=["a grade of \"C\" or higher will replace the failing grade", "the failed course will remain on your transcript",
                   "re-take the course the very next semester", "check with the financial aid office"]),
    spec("lookup", "Which community colleges have articulation agreements with the Computer Systems Technology department?",
         "lookup", "CST-NYT", "test", ["page/CST-NYT/transfer-policies#1"],
         "Borough of Manhattan, Queensborough, LaGuardia, Guttman, Kingsborough and Bronx. Students from these colleges who finished an AAS in a computer major named in the agreement are exempt from the CST AAS-level courses, "
         "except that a missing prerequisite for the chosen track must be completed at the BTech level, and a prerequisite passed with a grade below C must be repeated at the BTech level.",
         evidence=["Borough of Manhattan, Queensborough, LaGuardia, Guttman, Kingsborough and Bronx", "received a grade below a C"]),
    spec("lookup", "What internship and research opportunities does the Electrical and Telecommunications Engineering Technology department list for students?",
         "lookup", "EET-NYT", "dev", ["page/EET-NYT/student-resources#14"],
         "Names at least 3 opportunities from this list and invents none: " + "; ".join(link_titles("page/EET-NYT/student-resources#14")) + ".",
         evidence=["the internships below repeat on a yearly basis", "Reaching a New Energy Sciences Workforce (RENEW)"]),
    spec("lookup", "What is the Fresh Start program for students who were dismissed from City Tech?", "lookup", None, "dev",
         ["page/registrar/readmission#4"],
         "Students dismissed for failing to meet academic standards may appeal for readmission through Fresh Start if they graduated with an Associate's Degree after their dismissal, and must be readmitted into a Baccalaureate program. "
         "Apply at the Registrar's office in room NG-15 with a readmission form with the Fresh Start box checked and pay the readmission fee. The failing grades from the original record are forgiven and successfully completed coursework counts as transfer credit; this may affect SAP for Federal Title IV funding.",
         evidence=["Graduated with an Associate's Degree after their dismissal from City Tech", "room NG-15", "forgive all of the failing grades"]),
    spec("lookup", "What is the \"What If\" feature in DegreeWorks?", "lookup", None, "dev", ["page/registrar/faqs#11"],
         "\"What if\" is an option on the audit that lets students see how the courses they have taken would apply toward other majors. It does not change your major or your course history.",
         evidence=["look at how the courses they have taken would apply toward other majors", "It does not change your major or your course history"]),
    spec("lookup", "What happens if I don't pay my tuition bill?", "multi_chunk", None, "dev",
         ["page/admissions/tuition-penalty#3", "page/bursar/payment-deadlines#1"],
         "Failure to pay tuition and fees by the due date could result in cancellation of course enrollment, and if the tuition remains unpaid after enrollment a hold is placed on the account that prevents adding or swapping courses. "
         "A student who fails to pay tuition or other obligations is denied access to their records and prevented from registering in the future, and the account is turned over to the College's collection agency. "
         "The student is responsible for all collection costs, including agency fees, attorney fees and court costs, and non-payment or a default judgment may be reported to credit bureaus. "
         "Non-payment and not attending courses are NOT considered an official drop.",
         evidence=["could result in cancellation of course enrollment", "a hold will be placed on your account that will prevent you from adding or swapping courses",
                   "denied access to his/her records and will be prevented from registering in the future", "turned over to the College’s collection agency",
                   "agency fees, attorney fees and court costs", "reported to credit bureaus", "nonpayment and not attending courses are NOT considered an official drop"],
         note="Bursar and admissions pages."),
    spec("lookup", "What is the TAP waiver and who can get one?", "multi_chunk", None, "test",
         ["page/financial-aid/tap-appeal#2", "page/financial-aid/tap-appeal#1"],
         "A one-time waiver of the good academic standing requirement in the TAP regulations. It is not automatic: it may only be granted in extraordinary or unusual circumstances beyond the student's control and with a reasonable expectation that the student will meet future requirements. "
         "To request it, speak to a TAP Counselor in the Financial Aid Office and submit the completed TAP waiver/appeal form.",
         evidence=["extraordinary or unusual circumstances that are beyond the student's control", "Speak to a TAP Counselor in the Financial Aid Office"]),
]


# ---- output ----


def norm(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def similarity(a: str, b: str) -> float:
    x, y = norm(a), norm(b)
    return len(x & y) / len(x | y) if x | y else 0.0


def table(rows: list[dict], key: str) -> Counter:
    return Counter((r.get(key) or "(none)") for r in rows)


def family(sid: str) -> str:
    """Where a question's first gold source lives: a central office, the calendar, a department or none."""
    if re.match(r"^(fall|winter|spring|summer)-\d{4}-\d+$", sid):
        return "calendar"
    if sid.startswith("catalog:"):
        return "catalog (courses)"
    for prefix, name in (("page/registrar", "registrar"), ("page/advisement", "advisement"),
                         ("page/bursar", "bursar"), ("page/financial-aid", "financial aid"),
                         ("page/admissions", "admissions")):  # fmt: skip
        if sid.startswith(prefix):
            return name
    if sid.startswith("pdf/"):
        return "aid or CUNY PDF"
    return "department pages"


def row_family(row: dict) -> str:
    gold = row.get("gold") if "gold" in row else [g["id"] for g in row["gold_sources"]]
    return family(gold[0]) if gold else "(no source: abstain)"


def coverage(existing: list[dict], cands: list[dict]) -> str:
    combined = existing + cands
    for r in combined:
        r["family"] = row_family(r)
    out = []
    for key, label in (("type", "Type"), ("department", "Department"), ("split", "Split"),
                       ("family", "Central office or source family (first gold source)")):  # fmt: skip
        names = sorted(set(table(combined, key)))
        out += [f"| {label} | existing 30 | candidates | combined |", "|---|---|---|---|"]
        e, c, t = table(existing, key), table(cands, key), table(combined, key)
        out += [f"| {n} | {e[n]} | {c[n]} | {t[n]} |" for n in names]
        out += [f"| **total** | {len(existing)} | {len(cands)} | {len(combined)} |", ""]
    return "\n".join(out)


# ---- evidence: each draft sentence against its gold source text ----

INSTRUCTION_STARTS = ("CLARIFY", "NO ADVICE")
FOUND_WORDS = 0.75  # share of the draft sentence's words found in one source sentence
FOUND_RATIO = 0.60  # or difflib similarity of the two sentences


def tokens(text: str) -> list[str]:
    text = text.replace("\u201c", '"').replace("\u201d", '"').replace("\u2019", "'").replace("\u2018", "'")
    return re.findall(r"[a-z0-9]+", text.lower())


def draft_sentences(draft: str) -> list[tuple[str, bool]]:
    """(sentence, is_instruction). Instruction sentences (the CLARIFY / NO ADVICE rule, 'Names at
    least 3 ...') are the scoring rule, not a fact, so they are listed but not checked."""
    out: list[tuple[str, bool]] = []
    # sentence ends, except after common abbreviations such as "Comp." in a course title
    chunks = re.split(r"\s\|\s|(?<!Comp\.)(?<!App\.)(?<=[.!?])\s+(?=[A-Z\"(])", draft.strip())
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk.startswith(INSTRUCTION_STARTS):  # the whole sentence is the scoring rule
            out.append((chunk, True))
            continue
        for prefix in ("Facts: ", "Names at least 3 opportunities from this list and invents none: "):
            if chunk.startswith(prefix):
                out.append((prefix.strip(" :"), True))
                chunk = chunk[len(prefix):]
        m = re.match(r"^Facts, [^:]*: ", chunk)
        if m:
            out.append((m.group(0).strip(" :"), True))
            chunk = chunk[m.end():]
        for part in re.split(r";\s+", chunk):
            if part.strip():
                out.append((part.strip(), False))
    return out


def source_sentences(sources: list[dict]) -> list[tuple[str, str]]:
    """(source id, sentence) from the gold sources: markdown stripped, split at sentence ends,
    new lines, bullets and table cells."""
    out = []
    for src in sources:
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", src["text"]).replace("**", "").replace("<br>", ". ")
        for line in re.split(r"\n+", text):
            line = line.strip(" -|*")
            if not line or set(line) <= set("-| "):
                continue
            if "|" in line:  # a table row also counts as one segment
                out.append((src["id"], re.sub(r"\s*\|\s*", " ", line)))
            for piece in re.split(r"(?<=[.!?;])\s+|\s\|\s", line):
                if piece.strip(" |"):
                    out.append((src["id"], piece.strip(" |")))
    return out


def best_match(sentence: str, pool: list[tuple[str, str]]) -> tuple[str, str, float, float]:
    """(source id, closest source sentence, difflib ratio, share of words found)."""
    words = tokens(sentence)
    best = ("", "", 0.0, 0.0)
    for sid, cand in pool:
        have = set(tokens(cand))
        found = sum(w in have for w in words) / len(words) if words else 0.0
        ratio = difflib.SequenceMatcher(None, " ".join(words), " ".join(tokens(cand))).ratio()
        if (found, ratio) > (best[3], best[2]):
            best = (sid, cand, ratio, found)
    return best


def cell(text: str, limit: int = 230) -> str:
    text = text.replace("|", "/").replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "\u2026"


def evidence_markdown(cands: list[dict]) -> str:
    out = [
        "# Gold-answer evidence check (for the owner)", "",
        "For each candidate whose gold states facts, the draft gold answer is split into sentences and each is compared with "
        "the sentences of its gold source text (standard-library `difflib` plus the share of the draft sentence's words found in "
        f"one source sentence). A sentence is **found** if at least {FOUND_WORDS:.0%} of its words appear in one source sentence or "
        f"the similarity ratio is at least {FOUND_RATIO:.2f}; otherwise it says **NOT FOUND: check**. Rule sentences "
        "(the CLARIFY / NO ADVICE scoring rule and the 'names at least 3' rule) are listed but not checked. "
        "This is an aid to your review, not a replacement: a sentence can score well and still be wrong in a detail "
        "(a number, a negation), and a combined sentence can score low and be right.", "",
    ]
    ids = {"q40", "q42", "q43", "q47", "q48", "q49", "q50", "q51", "q52", "q53", "q54", "q55", "q56", "q57", "q58", "q59", "q60"}
    summary = []
    for c in cands:
        if c["id"] not in ids:
            continue
        sources = [source_info(g) for g in c["gold"]]
        pool = source_sentences(sources)
        rows, missing = [], 0
        for n, (sentence, is_rule) in enumerate(draft_sentences(c["draft"]), 1):
            if is_rule:
                rows.append(f"| {n} | {cell(sentence)} | (rule, not checked) | | | |")
                continue
            sid, cand, ratio, found = best_match(sentence, pool)
            ok = found >= FOUND_WORDS or ratio >= FOUND_RATIO
            missing += not ok
            verdict = "found" if ok else "**NOT FOUND: check**"
            rows.append(f"| {n} | {cell(sentence)} | `{sid}`: {cell(cand)} | {ratio:.2f} | {found:.0%} | {verdict} |")
        summary.append((c["id"], len([r for r in rows if "rule, not checked" not in r]), missing))
        out += [f"## {c['id']} \u2014 {c['question']}", "",
                "| # | Draft sentence | Closest source sentence | ratio | words found | result |",
                "|---|---|---|---|---|---|", *rows, ""]  # fmt: skip
    out += ["## Summary", "", "| Candidate | sentences checked | NOT FOUND |", "|---|---|---|"]
    out += [f"| {i} | {n} | {m} |" for i, n, m in summary]
    return "\n".join(out) + "\n"


QUESTIONS = ROOT / "eval" / "questions.jsonl"
CHAIN_EXISTING = ("q20", "q22")  # existing rows that get the tag; nothing else on them changes


def gold_object(sid: str) -> dict:
    src = source_info(sid)
    if sid in EVENTS:  # a calendar row: the file is the source, the heading starts with the term
        return {"id": sid, "source": "data/calendar/calendar_events.json", "heading": src["heading"]}
    return {"id": sid, "source": src["source"], "heading": src["heading"]}


def question_row(s: dict) -> dict:
    """A row for eval/questions.jsonl: the reviewed draft becomes the gold answer (the DRAFT marker
    exists only in the review document, never in the gold text)."""
    row = {
        "id": s["id"], "question": s["question"], "gold_answer": s["draft"],
        "gold_sources": [gold_object(g) for g in s["gold"]], "type": s["type"],
        "department": s["department"], "split": s["split"], "note": s["note"],
    }  # fmt: skip
    if s["tags"]:
        row["tags"] = s["tags"]
    return row


def merge(cands: list[dict]) -> None:
    """Append the candidates to eval/questions.jsonl and add the chain tag to q20 and q22."""
    lines = QUESTIONS.read_text(encoding="utf-8").splitlines()
    if any(json.loads(ln)["id"] == cands[0]["id"] for ln in lines):
        raise SystemExit(f"{cands[0]['id']} is already in {QUESTIONS.name}: nothing merged")
    out = []
    for ln in lines:
        if json.loads(ln)["id"] in CHAIN_EXISTING:  # textual insert: no other byte of the row changes
            assert ln.endswith("}") and '"tags"' not in ln
            ln = ln[:-1] + ',"tags":["chain"]}'
        out.append(ln)
    for s in cands:
        text = s["draft"]
        if "TODO" in text or "DRAFT" in text:
            raise SystemExit(f"{s['id']}: the gold text still has a TODO or DRAFT marker")
        out.append(json.dumps(question_row(s), separators=(",", ":")))
    QUESTIONS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"merged {len(cands)} questions into {QUESTIONS.relative_to(ROOT)}")


def main() -> None:
    # the questions that existed before the candidates (q01-q30); after a merge the file also holds q31 on
    existing = [q for q in load_questions() if int(q["id"][1:]) < FIRST_ID]
    assert len(existing) == 30, "expected the 30 existing questions"
    seen = {q["question"].strip().lower() for q in existing}
    lines = [
        "# Eval candidates (for the owner to review)",
        "",
        f"Generated by `scripts/make_eval_candidates.py`. **{len(SPECS)} candidates, ids from q{FIRST_ID}. Nothing here is in "
        "`eval/questions.jsonl`.** Questions were chosen from the data and a fixed category list; no baseline result (dev or test) "
        "was used to pick or word any of them. Every gold answer is a **DRAFT**: calendar answers are generated from "
        "`data/calendar/calendar_events.json`, prerequisite chains from the course records. The other drafts were written from the source text; "
        "the script checks that their key phrases occur verbatim in the gold sources (it stops if one does not), but the rest of each draft "
        "is not machine-checked, so read each against its sources. Where the sources do not settle the answer the draft says TODO. "
        "Please review wording, type, split and gold sources before anything is added.",
        "",
        "Things to know before reviewing:",
        "- **No TBA candidate.** The only TBA row in the calendar is `spring-2027-055` (the 87th Commencement Ceremony), and it is already "
        "q11. A second question about it would be a paraphrase, so none is proposed. If you want another \"not announced\" case, the data has none.",
        "- Summer 2027 and Fall 2027 abstain candidates ask about things q25 does not (a refund deadline, exam dates).",
        "- \"This fall\" and \"next spring\" candidates need `eval.today` (2026-10-11) to resolve the term.",
        "- Chained-prerequisite gold sources list every course in the tree; the draft answer is compact prose (each course with its direct "
        "prerequisites in order, placement and equivalence text in one clause). Planned tag `chain`: q20, q22, q39, q40, q41.",
        "- Review applied (step 0b): q32 test, q52 dev; q33 has spring-2027-006 as a second source; q39 and q41 in prose; q40 replaced "
        "(CST 3613, a chain with no MAT course in it); q42 is now a related pair (co-requisite variant), not cross-listed, so q43 is the only "
        "cross-listed candidate; q49 and q50 use the CLARIFY OR BOTH / CLARIFY OR STATE THE TERM gold; q54 reworded; q56 asks for at least 3 "
        "named opportunities; q53 and q59 replaced (advisement, and bursar/admissions). q53 is now the single question about TAP and an undeclared major (lookup).",
        "- `docs/eval-evidence.md` compares each fact-stating draft with its source text sentence by sentence.",
        "- The NO ADVICE candidates use `type: unanswerable` like q30; the CLARIFY candidates use `type: ambiguous` like q23 and q24.",
        "",
    ]
    cands = []
    for n, s in enumerate(SPECS, FIRST_ID):
        qid = f"q{n}"
        if s["question"].strip().lower() in seen:
            raise SystemExit(f"{qid}: duplicates an existing question")
        closest = max(existing, key=lambda q: similarity(s["question"], q["question"]))
        sim = similarity(s["question"], closest["question"])
        if sim > 0.7:
            raise SystemExit(f"{qid}: too close to {closest['id']} (word overlap {sim:.2f})")
        sources = [source_info(g) for g in s["gold"]]
        check_evidence(s, sources)
        s["id"] = qid
        cands.append(s)
        lines += [
            f"## {qid} — {s['cat']}",
            "",
            f"- **Question:** {s['question']}",
            f"- **Type:** {s['type']}  |  **Department:** {s['department'] or '(none)'}  |  **Proposed split:** {s['split']}",
            f"- **Closest existing question:** {closest['id']} (word overlap {sim:.2f})",
        ]
        if s["note"]:
            lines.append(f"- **Note:** {s['note']}")
        lines.append("- **Gold sources:**")
        if sources:
            lines += [f"  - `{x['id']}` — {x['heading']}" for x in sources]
        else:
            lines.append("  - (none: the assistant should abstain)")
        lines += ["", f"**Draft gold answer — {DRAFT}:**", ""]
        lines += ["> " + ln if ln.strip() else ">" for ln in s["draft"].splitlines()]
        lines.append("")
    lines += ["## Coverage", "", coverage(existing, cands)]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    EVIDENCE.write_text(evidence_markdown(cands), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} with {len(cands)} candidates and {EVIDENCE.relative_to(ROOT)}")
    if "--merge" in sys.argv:
        merge(cands)


if __name__ == "__main__":
    main()
