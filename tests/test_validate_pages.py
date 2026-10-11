from cta.validate.pages import (
    check_bodies,
    check_chairs,
    check_cleaned_text,
    check_contacts,
    check_hashes_and_log,
    check_index_flags,
    check_links,
    check_redirects,
    check_sections,
    check_status,
    counts_per_owner,
    email_repairs,
    run_page_checks,
)

U = "https://www.citytech.cuny.edu/a.aspx"


def manifest_entry(**over):
    base = {"url": U, "final_url": U, "status": 200, "error": "", "content_hash": "h1",
            "kind": "office", "owner": "bursar"}  # fmt: skip
    return {**base, **over}


def record(**over):
    base = {
        "pdf_links": [], "index": True, "index_reason": None,
        "source_url": U, "http_status": 200, "status": "collected", "reason": "", "kind": "office",
        "owner": "bursar", "sections": [{"heading": "H", "level": 1, "markdown": "body text"}],
        "contact": {"panels": [], "emails": [], "phones": []}, "chair": None, "email_repairs": [],
    }  # fmt: skip
    return {**base, **over}


def log_row(**over):
    base = {
        "timestamp": "t",
        "method": "GET",
        "url": U,
        "status": 200,
        "content_hash": "h1",
        "note": "",
    }
    return {**base, **over}


def test_status_200():
    assert check_status([manifest_entry()]) == []
    found = check_status([manifest_entry(status=404), manifest_entry(status=None, error="boom")])
    assert [f.check for f in found] == ["status_200", "status_200"]


def test_redirect_must_end_at_200_on_the_same_host():
    moved = U.replace("a.aspx", "b.aspx")
    assert check_redirects([manifest_entry(final_url=moved)]) == []
    assert len(check_redirects([manifest_entry(final_url=moved, status=404)])) == 1
    assert len(check_redirects([manifest_entry(final_url="https://other.example.com/x")])) == 1


def test_empty_body_fails_and_placeholder_only_is_a_warning():
    empty = record(status="not_collected", reason="main content empty in raw HTML", sections=[])
    placeholder = record(status="not_collected", reason="only template placeholders", sections=[])
    assert [(f.check, f.severity) for f in check_bodies([empty])] == [("body_non_empty", "fail")]
    assert [(f.check, f.severity) for f in check_bodies([placeholder])] == [
        ("not_collected", "warning")
    ]
    assert check_bodies([record()]) == []


def test_blank_text_after_stripping_fails():
    blank = record(sections=[{"heading": None, "level": 0, "markdown": "  "}])
    assert [f.check for f in check_bodies([blank])] == ["body_non_empty"]


def test_non_200_page_is_not_double_reported_as_empty():
    r = record(status="not_collected", reason="http 404", http_status=404, sections=[])
    assert check_bodies([r]) == []


def test_content_hash_and_fetch_log_without_gaps():
    assert check_hashes_and_log([manifest_entry()], [log_row()]) == []
    no_hash = check_hashes_and_log([manifest_entry(content_hash=None)], [log_row()])
    assert [f.check for f in no_hash] == ["content_hash", "fetch_log"]
    assert len(check_hashes_and_log([manifest_entry()], [])) == 1  # no log row at all
    assert len(check_hashes_and_log([manifest_entry()], [log_row(content_hash="other")])) == 1
    assert (
        len(check_hashes_and_log([manifest_entry()], [log_row(), log_row(status=None, note="")]))
        == 1
    )
    assert len(check_hashes_and_log([manifest_entry()], [log_row(), log_row(timestamp="")])) == 1


def test_fetch_log_row_for_a_redirect_target_counts():
    moved = U.replace("a.aspx", "b.aspx")
    rows = [log_row(status=302), log_row(url=moved)]
    assert check_hashes_and_log([manifest_entry(final_url=moved)], rows) == []


def test_blocked_row_with_a_note_is_not_a_gap():
    rows = [log_row(), log_row(status=None, content_hash=None, note="blocked: robots")]
    assert check_hashes_and_log([manifest_entry()], rows) == []


def test_cleaned_text_must_have_no_placeholders_or_spaced_emails():
    bad = record(
        sections=[
            {"heading": "H", "level": 1, "markdown": "Mail me @ x {{a.b}} joe @citytech.cuny.edu"}
        ]
    )
    assert sorted(f.check for f in check_cleaned_text([bad])) == ["emails", "placeholders"]
    assert check_cleaned_text([record()]) == []


def test_malformed_contact_email_fails():
    r = record(contact={"panels": [], "emails": ["a@b"], "phones": []})
    assert [f.check for f in check_cleaned_text([r])] == ["emails"]


CHAIR = {"name": "Prof. A", "role": "Chair", "room": "N-1 (N-1)", "phone": "718-260-0000",
         "email": "a@citytech.cuny.edu"}  # fmt: skip
CHAIR_URL = "https://www.citytech.cuny.edu/x/chairperson.aspx"


def test_chair_must_be_complete_and_well_formed():
    ok = record(source_url=CHAIR_URL, chair=CHAIR)
    assert check_chairs([ok]) == []
    assert [f.message for f in check_chairs([record(source_url=CHAIR_URL, chair=None)])] == [
        "no chair block found"
    ]
    partial = record(source_url=CHAIR_URL, chair={**CHAIR, "phone": None})
    assert "chair missing ['phone']" in check_chairs([partial])[0].message
    bad_email = record(source_url=CHAIR_URL, chair={**CHAIR, "email": "a @b.edu"})
    assert "malformed chair email" in check_chairs([bad_email])[0].message
    assert check_chairs([record()]) == []  # other pages have no chair


def test_email_repairs_listed_per_page():
    r = record(email_repairs=[{"raw": "a @b.edu", "fixed": "a@b.edu"}])
    assert email_repairs([r, record(source_url="u2")]) == {U: r["email_repairs"]}


def test_counts_per_owner():
    recs = [record(), record(status="not_collected"), record(owner="CST-NYT", kind="department")]
    assert counts_per_owner(recs) == {
        "department:CST-NYT": {"pages": 1, "collected": 1, "http_200": 1},
        "office:bursar": {"pages": 2, "collected": 1, "http_200": 2},
    }


def test_run_page_checks_clean_data():
    assert run_page_checks([manifest_entry()], [record()], [log_row()]) == []


def md(text):
    return record(sections=[{"heading": "H", "level": 1, "markdown": text}])


def test_login_links_fail_and_long_query_urls_warn():
    sso = md("[x](https://ssologin.cuny.edu/cuny.html?a=1)")
    path = md("[x](https://www.citytech.cuny.edu/login/)")
    frag = md("[x](https://cuny.coursedog.com/#/login?continue=1)")
    assert [f.check for f in check_links([sso, path, frag])] == ["login_links"] * 3
    pdf = record(pdf_links=[{"url": "https://www.citytech.cuny.edu/a/login.pdf", "text": "t"}])
    assert [f.check for f in check_links([pdf])] == ["login_links"]
    long_q = md("[x](https://example.com/p?" + "a=1&" * 30 + ")")
    found = check_links([long_q, md("[ok](https://example.com/p?a=1)")])
    assert [(f.check, f.severity) for f in found] == [("long_urls", "warning")]


def test_empty_sections_fail():
    r = record(sections=[{"heading": "H", "level": 1, "markdown": "  "}])
    assert [f.check for f in check_sections([r])] == ["empty_sections"]
    assert check_sections([record()]) == []


def test_index_flag_rules():
    assert check_index_flags([record(index=True, index_reason=None)]) == []
    assert check_index_flags([record(index=False, index_reason="links only")]) == []
    assert len(check_index_flags([record(index=False, index_reason=None)])) == 1
    no_field = {k: v for k, v in record().items() if k != "index"}
    assert len(check_index_flags([no_field])) == 1
    assert len(check_index_flags([record(index=True, status="not_collected")])) == 1


def test_inconsistent_contacts_warn():
    ok = {"owner": "bursar", "consistent": True}
    bad = {"owner": "x", "consistent": False}
    assert [(f.check, f.severity) for f in check_contacts([ok, bad])] == [("contacts", "warning")]
