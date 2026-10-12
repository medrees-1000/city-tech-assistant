"""Calendar loader tests: throwaway schema (see conftest.conn), no network, real table untouched."""

import copy
import json

import pytest

from cta.index import load_calendar as lc
from cta.validate.calendar import UnverifiedCalendarError, load_events_for_indexing


def event(n, term="Fall 2026", start="2026-09-01", weekday="Tuesday", **kw):
    base = {
        "id": f"{term.lower().replace(' ', '-')}-{n:03d}", "term": term, "event": f"Event {n}",
        "date_start": start, "date_end": None, "date_raw": "raw", "weekday_raw": weekday,
        "applies_to": None, "bold": False, "source_pdf": "data/pdfs/x.pdf", "source_page": 1,
        "pdf_last_updated": "2026-09-15", "verified": True, "verified_by": "owner",
        "verified_on": "2026-10-11", "notes": None,
    }  # fmt: skip
    return base | kw


EVENTS = [
    event(1),
    event(2, start="2026-09-02", weekday="Wednesday"),
    event(1, "Winter 2027", "2026-12-21", "Monday"),
    event(2, "Winter 2027", "2027-01-04", "Monday"),
    event(3, "Winter 2027", None, "", date_raw="TBA", event="Commencement"),
]
COUNTS = {"Fall 2026": 2, "Winter 2027": 3}


def load(conn, events, **kw):
    lines: list[str] = []
    code = lc.run(
        conn, copy.deepcopy(events), kw.get("yes", True), kw.get("dry", False), lines.append
    )
    return code, "\n".join(lines)


@pytest.fixture(autouse=True)
def small_expectation(monkeypatch):
    monkeypatch.setattr(lc, "EXPECTED_COUNTS", COUNTS)
    monkeypatch.setattr(lc.integrity, "__defaults__", (COUNTS,))


def count(conn):
    return conn.execute("SELECT count(*) FROM calendar_events").fetchone()[0]


@pytest.mark.integration
def test_first_load_then_nothing_changes(conn):
    code, text = load(conn, EVENTS)
    assert code == 0 and count(conn) == 5 and "new 5, changed 0, unchanged 0, stale 0" in text
    code, text = load(conn, EVENTS)
    assert "new 0, changed 0, unchanged 5, stale 0" in text


@pytest.mark.integration
def test_tba_is_null_and_listed(conn):
    _, text = load(conn, EVENTS)
    row = conn.execute(
        "SELECT date_start, date_raw FROM calendar_events WHERE event = 'Commencement'"
    )
    assert row.fetchone() == (None, "TBA")
    assert "rows with a NULL date (TBA): 1\n  Commencement" in text


@pytest.mark.integration
def test_changed_row_updates_and_removed_row_is_deleted(conn):
    load(conn, EVENTS)
    edited = copy.deepcopy(EVENTS)
    edited[0]["event"] = "Edited"
    del edited[1]
    _, text = load(conn, edited)
    assert "new 0, changed 1, unchanged 3, stale 1" in text
    assert count(conn) == 4
    assert (
        conn.execute("SELECT event FROM calendar_events WHERE id = 'fall-2026-001'").fetchone()[0]
        == "Edited"
    )


@pytest.mark.integration
def test_without_yes_and_dry_run_write_nothing(conn):
    _, text = load(conn, EVENTS, yes=False)
    assert "run again with --yes" in text and count(conn) == 0
    _, text = load(conn, EVENTS, dry=True)
    assert "dry run" in text and count(conn) == 0


@pytest.mark.integration
def test_weekday_mismatch_is_reported_not_fixed(conn):
    bad = copy.deepcopy(EVENTS)
    bad[0]["weekday_raw"] = "Friday"  # 2026-09-01 is a Tuesday
    code, text = load(conn, bad)
    assert code == 1 and "fall-2026-001: 2026-09-01 is a Tuesday, weekday_raw 'Friday'" in text
    assert (
        conn.execute(
            "SELECT weekday_raw FROM calendar_events WHERE id = 'fall-2026-001'"
        ).fetchone()[0]
        == "Friday"
    )


def test_winter_year_check_catches_wrong_year():
    rows = [lc.to_row(event(1, "Winter 2027", "2027-12-21", "Tuesday"))]
    problems, _ = lc.integrity(rows, {"Winter 2027": 1})
    assert any("expected 2026" in p for p in problems)


def test_unverified_event_is_refused(tmp_path):
    path = tmp_path / "e.json"
    path.write_text(json.dumps([event(1, verified=False)]))
    with pytest.raises(UnverifiedCalendarError):
        load_events_for_indexing(path)
    assert lc.main(["x", "--dry-run"], path) == 1


def test_real_file_passes_every_integrity_check():
    rows = [lc.to_row(e) for e in load_events_for_indexing(lc.EVENTS_FILE)]
    problems, tba = lc.integrity(rows, {"Fall 2026": 55, "Winter 2027": 26, "Spring 2027": 55})
    assert problems == [] and len(rows) == 136 and len(tba) == 1


def test_printed_year_decides():
    ok = lc.to_row(event(1, start="2027-01-01", weekday="Friday", date_raw="January 01, 2027"))
    assert lc.integrity([ok], {"Fall 2026": 1})[0] == []
    wrong = lc.to_row(event(1, start="2026-01-01", weekday="Thursday", date_raw="January 01, 2027"))
    assert any("expected 2027" in p for p in lc.integrity([wrong], {"Fall 2026": 1})[0])
