import re
from pathlib import Path

from bs4 import BeautifulSoup

from cta.parse.html import parse_page, render_markdown

PAGES = Path(__file__).parent / "fixtures" / "pages"
HOST = "https://www.citytech.cuny.edu"


def parse(name: str, path: str = "/x.aspx", kind: str = "office", owner: str = "bursar") -> dict:
    meta = {
        "source_url": HOST + path, "final_url": HOST + path,
        "fetched_at": "2026-10-11T00:00:00+00:00", "content_hash": "abc",
        "http_status": 200, "kind": kind, "owner": owner,
    }  # fmt: skip
    html = (
        (PAGES / f"{name}.html").read_bytes()
        if (PAGES / f"{name}.html").exists()
        else name.encode()
    )
    return parse_page(html, meta)


def inline_page(main_html: str, panels_html: str = "") -> dict:
    html = (
        "<html><head><title>T</title></head><body><header>HEADER JUNK</header>"
        f'<div class="c-layout-sidebar-menu">{panels_html}</div>'
        f'<div class="c-layout-sidebar-content">{main_html}</div><footer>FOOTER JUNK</footer>'
        "</body></html>"
    )
    return parse(html)


def headings(rec: dict) -> list[tuple[int, str]]:
    return [(s["level"], s["heading"]) for s in rec["sections"] if s["heading"]]


def test_menu_banner_and_footer_text_never_reach_the_output():
    rec = parse("bursar_refund_policy", "/bursar/refund-policy.aspx")
    out = render_markdown(rec)
    soup = BeautifulSoup((PAGES / "bursar_refund_policy.html").read_bytes(), "html.parser")
    junk = [
        t.strip() for el in (soup.header, soup.footer) for t in el.stripped_strings if len(t) > 25
    ]
    assert junk  # the fixture really contains header and footer text
    assert not [t for t in junk if t in out]
    assert "{{" not in out


def test_title_sections_and_metadata():
    rec = parse("bursar_refund_policy", "/bursar/refund-policy.aspx")
    assert rec["title"] == "Tuition Refund Policy - Bursar's Office - City Tech"
    assert rec["status"] == "collected" and rec["kind"] == "office" and rec["owner"] == "bursar"
    assert headings(rec) == [
        (1, "Refund Policy"),
        (2, "Refund Policy and Deadlines for Dropping Classes"),
        (2, "Summer Session I 2026 Refund Policy"),
        (2, "Summer Session II 2026 Refund Policy"),
        (2, "Fall 2026 Refund Policy"),
    ]


def test_refund_table_th_row_labels_are_bold_and_header_row_is_the_header():
    rec = parse("bursar_refund_policy", "/bursar/refund-policy.aspx")
    fall = next(s for s in rec["sections"] if s["heading"] == "Fall 2026 Refund Policy")
    lines = fall["markdown"].splitlines()
    assert lines[0] == "| Drop Period | Tuition Refund/Liability |"
    assert lines[1] == "| --- | --- |"
    row = "| **August 27, 2026** | Last day to drop classes for 100% tuition refund; 0% Liability |"
    assert lines[2] == row
    summer1 = next(
        s for s in rec["sections"] if s["heading"] == "Summer Session I 2026 Refund Policy"
    )
    assert (
        "**June 03, 2026 (4WI)<br>June 04, 2026 (5WI)<br>June 06, 2026 (7WI)**"
        in summer1["markdown"]
    )


def test_table_without_header_row_gets_a_blank_header():
    rec = parse("admissions_tuition_refund", "/admissions/tuition-refund.aspx", owner="admissions")
    cuny = next(
        s for s in rec["sections"] if s["heading"] == "City University of New York Refund Policy"
    )
    lines = cuny["markdown"].split("\n\n")[1].splitlines()
    assert lines[0] == "|  |  |" and lines[1] == "| --- | --- |"
    assert lines[2].startswith("| Withdrawal before the scheduled opening date of the session: |")
    assert "Fall and Spring, 100%<br>Summer Session, 100%" in lines[2]


def test_contact_panel_and_hours_are_kept_and_commented_out_html_is_ignored():
    rec = parse("bursar_refund_policy", "/bursar/refund-policy.aspx")
    assert [p["heading"] for p in rec["contact"]["panels"]] == [
        "CONTACT US", "Bursar Service Window Hours", "Bursar Office Hours",
    ]  # fmt: skip
    assert rec["contact"]["emails"] == ["bursar@citytech.cuny.edu"]
    assert rec["contact"]["phones"] == []  # a phone number sits inside an HTML comment
    assert "718-260-5510" not in render_markdown(rec)


def test_promo_panels_are_dropped():
    panels = (
        '<div class="panel"><div class="panel-heading"><h2>CONTACT US</h2></div>'
        '<div class="panel-body"><p>Room 1</p></div></div>'
        '<div class="panel"><div class="panel-heading"><h2>ANNOUNCEMENTS</h2></div>'
        '<div class="panel-body"><p>Big sale</p></div></div>'
        '<div class="panel"><div class="panel-heading"><h2>Zoom Hours</h2></div>'
        '<div class="panel-body"><p>Mon 9-5</p></div></div>'
    )
    rec = inline_page("<h1>A</h1><p>x</p>", panels)
    assert [p["heading"] for p in rec["contact"]["panels"]] == ["CONTACT US", "Zoom Hours"]
    assert "Big sale" not in render_markdown(rec)


def test_faq_accordion_questions_become_sections_and_layout_tables_are_not_tables():
    rec = parse("math_faqs", "/mathematics/faqs.aspx", "department", "MATH-NYT")
    assert (2, "MATH PLACEMENT") in headings(rec)  # <p class="barTitle"> is a section label
    q = next(s for s in rec["sections"] if s["heading"] == "What determines my math placement?")
    assert q["level"] == 3
    assert q["markdown"].startswith("Your placement is based on your high school records.")
    layout = [s for s in rec["sections"] if s["level"] == 3]
    assert len(layout) >= 10
    assert not any(line.startswith("|") for s in layout for line in s["markdown"].splitlines())


def test_layout_table_with_headings_is_walked_not_rendered_as_a_table():
    rec = inline_page(
        "<h1>FAQ</h1><table><tr><td><h3>Q1?</h3><p>A1.</p></td></tr>"
        "<tr><td><h3>Q2?</h3><p>A2.</p></td></tr></table>"
    )
    assert headings(rec) == [(1, "FAQ"), (3, "Q1?"), (3, "Q2?")]
    assert rec["sections"][1]["markdown"] == "A1."


def test_data_table_header_row_th_and_colspan():
    rec = inline_page(
        "<h1>T</h1><table><tr><th>A</th><th>B</th></tr>"
        "<tr><th>row</th><td>1</td></tr><tr><td colspan='2'>wide | cell</td></tr></table>"
    )
    assert rec["sections"][0]["markdown"].splitlines() == [
        "| A | B |", "| --- | --- |", "| **row** | 1 |", "| wide \\| cell |  |",
    ]  # fmt: skip


def test_lists_nested_lists_and_links():
    rec = inline_page(
        '<h1>L</h1><ul><li>one <a href="/a.aspx">link</a><ul><li>inner</li></ul></li>'
        "<li>two</li></ul>"
        '<p><a href="http://www.citytech.cuny.edu/b.aspx">B</a> <a href="#top">anchor</a></p>'
    )
    md = rec["sections"][0]["markdown"]
    assert "- one [link](https://www.citytech.cuny.edu/a.aspx)\n  - inner\n- two" in md
    assert "[B](https://www.citytech.cuny.edu/b.aspx) anchor" in md


def test_chair_block_fields_and_repaired_email_with_a_space():
    rec = parse("cst_chairperson", "/computer-systems/chairperson.aspx", "department", "CST-NYT")
    assert rec["chair"] == {
        "name": "Prof. Elizabeth Milonas", "role": "Chair", "room": "Namm Hall 1000 (N-1000)",
        "phone": "718-260-5038", "email": "EMilonas@citytech.cuny.edu",
        "faculty_page": "https://www.citytech.cuny.edu/faculty/EMilonas",
    }  # fmt: skip
    assert rec["email_repairs"] == [
        {"raw": "EMilonas @citytech.cuny.edu", "fixed": "EMilonas@citytech.cuny.edu"}
    ]
    assert " @" not in render_markdown(rec)
    assert rec["contact"]["emails"] == [
        "compsystech@citytech.cuny.edu"
    ]  # the office, not the chair


def test_chair_email_taken_from_mailto_when_the_text_is_split():
    rec = parse("math_chairperson", "/mathematics/chairperson.aspx", "department", "MATH-NYT")
    assert rec["chair"]["email"] == "JNatov@citytech.cuny.edu"
    assert rec["chair"]["name"] == "Jonathan Natov"
    assert "JNatov@citytech.cuny.edu" in render_markdown(rec)


def test_email_link_text_split_by_br_uses_the_correct_href_without_a_repair():
    rec = parse("advisement_six_steps", "/advisement/six-steps.aspx", owner="advisement")
    assert "transferadvisement@citytech.cuny.edu" in render_markdown(rec)
    assert rec["email_repairs"] == []


def test_non_chair_pages_have_no_chair():
    assert parse("bursar_refund_policy", "/bursar/refund-policy.aspx")["chair"] is None


def test_pdf_links_are_listed_with_absolute_urls_and_not_fetched():
    rec = parse("math_faqs", "/mathematics/faqs.aspx", "department", "MATH-NYT")
    assert rec["pdf_links"] == [
        {"url": "https://www.citytech.cuny.edu/catalog/docs/catalog.pdf", "text": "College Catalog"}
    ]


def test_empty_main_content_is_not_collected_with_the_exact_reason():
    rec = parse("writing_intensive_empty", "/advisement/writing-intensive-fall26.aspx")
    assert rec["status"] == "not_collected"
    assert rec["reason"] == "main content empty in raw HTML"
    assert rec["sections"] == [] and rec["title"].startswith("General Education")


def test_placeholder_only_page_is_not_collected():
    rec = parse("placeholders_only", "/computer-systems/course-listing.aspx")
    assert rec["status"] == "not_collected" and rec["reason"] == "only template placeholders"


def test_placeholders_inside_a_real_page_are_removed():
    rec = inline_page("<h1>Hi</h1><p>Call {{employee.Phone}} now</p>")
    assert rec["status"] == "collected"
    assert render_markdown(rec).count("{{") == 0
    assert "Call now" in rec["sections"][0]["markdown"]


def test_missing_main_selector_is_not_collected():
    rec = parse("<html><head><title>x</title></head><body><p>hi</p></body></html>")
    assert rec["status"] == "not_collected" and rec["reason"] == "main content selector not found"


def test_br_inside_a_paragraph_becomes_a_newline():
    rec = inline_page("<h1>A</h1><p>line one<br>line two</p>")
    assert rec["sections"][0]["markdown"] == "line one\nline two"


def test_no_whitespace_runs_or_nbsp_in_output():
    rec = parse("math_faqs", "/mathematics/faqs.aspx", "department", "MATH-NYT")
    assert "\xa0" not in render_markdown(rec) and not re.search(
        r"[^\n ]  +[^\n ]", render_markdown(rec)
    )


def test_cells_outside_a_tr_are_kept_as_a_row():
    # the real bursar/payment-plan page has `<tr><tr>..</tr></tr><td>..</td>` markup
    rec = inline_page(
        "<h1>P</h1><table><thead><tr><th>Dates</th><th>N</th></tr></thead><tbody>"
        "<tr><tr><td>A</td><td>1</td></tr></tr>"
        "<td>Aug 25 &mdash; Sept 04</td><td>2</td></tbody></table>"
    )
    assert rec["sections"][0]["markdown"].splitlines() == [
        "| Dates | N |", "| --- | --- |", "| A | 1 |", "| Aug 25 \u2014 Sept 04 | 2 |",
    ]  # fmt: skip


def test_real_payment_plan_page_keeps_every_row():
    rec = parse("bursar_payment_plan", "/bursar/payment-plan.aspx")
    fall = next(s for s in rec["sections"] if s["heading"] == "Fall 2026 Payment Plan")
    assert "| Aug 25 \u2014 Sept 04 | 2 | Oct \u2014 Nov |" in fall["markdown"]


def test_footnote_markers_do_not_glue_onto_words_and_buttons_keep_their_text():
    rec = inline_page(
        "<h1>A</h1><p>Psychology<sup>1</sup> and Physiology I<sup>2</sup> (th<sup>th</sup>)</p>"
        '<p><a href="/x.aspx"><button>Advisement Information</button></a></p>'
    )
    md = rec["sections"][0]["markdown"]
    assert "Psychology^1 and Physiology I^2 (th^(th))" in md
    assert "[Advisement Information](https://www.citytech.cuny.edu/x.aspx)" in md


def test_p_and_table_directly_inside_a_list_are_kept():
    rec = inline_page(
        "<h1>A</h1><ul><li>one</li><p>stray paragraph</p><li>two</li></ul>"
        "<ol><table><tr><th>H</th></tr><tr><td>v</td></tr></table></ol>"
    )
    md = rec["sections"][0]["markdown"]
    assert md.split("\n\n")[:3] == ["- one", "stray paragraph", "- two"]
    assert "| H |" in md and "| v |" in md


def test_whitespace_between_list_items_keeps_one_list():
    rec = inline_page(
        "<h1>A</h1><ul>\n  <li>one</li>\n  <li>two</li>\n</ul><ol>\n<li>x</li>\n<li>y</li>\n</ol>"
    )
    assert rec["sections"][0]["markdown"] == "- one\n- two\n\n1. x\n2. y"
