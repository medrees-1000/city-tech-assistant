"""Department filter (Phase 3, step 2a): detection by alias and code, and the filter by scope."""

import pytest

from cta.index import departments as deps
from cta.index import search as srch
from cta.settings import load_models
from tests.test_answer import FakeChatClient
from tests.test_search import vec

CFG = load_models(
    env={"CTA_RERANK": "off", "CTA_ROUTER_MODE": "off"}
)  # the reranker has its own tests


def found(question: str) -> set[str]:
    return deps.detect_departments(question)


# ---- detection (no database) ----


def test_aliases_match_whole_words_and_ignore_case():
    assert found("What does the Electrical Engineering Technology department offer?") == {"EET-NYT"}
    assert found("what does the eet department offer") == {"EET-NYT"}
    assert found("Is there a Computer Systems Technology internship?") == {"CST-NYT"}
    assert found("How do I join the dental hygiene program?") == {"DENT-NYT"}
    assert found("What is my math placement?") == {"MATH-NYT"}
    assert found("Electrical & Telecommunications Engineering Technology degrees") == {"EET-NYT"}
    assert found("Electrical and Telecommunications Engineering Technology degrees") == {"EET-NYT"}


def test_aliases_do_not_match_inside_other_words():
    assert found("Meet the chair of the college") == set()  # "meet" is not "EET"
    assert found("How many feet is it?") == set()
    assert found("Is mathematical logic offered?") == set()  # "Math" is not "mathematical"
    assert found("What is the CSTA award?") == set()


def test_etet_and_eet_both_mean_the_electrical_department():
    assert found("ETET office hours") == {"EET-NYT"} == found("EET office hours")
    assert found("etet student hours") == {"EET-NYT"}


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What are the prerequisites for EET 3672?", {"EET-NYT"}),
        ("What are the prerequisites for EET3672?", {"EET-NYT"}),
        ("prerequisites for eet 3672", {"EET-NYT"}),
        ("What do I need before MAT 1275CO?", {"MATH-NYT"}),
        ("Can I take TCET 4102?", {"EET-NYT"}),  # a second EET-department prefix
        ("Is MEDU 4000 offered?", {"MATH-NYT"}),
        ("What is DEN 2400?", {"DENT-NYT"}),
        ("What is MST 1101?", {"CST-NYT"}),  # legacy prefix the catalog lists under CST
        ("What is CET 3672?", set()),  # a cross-listed prefix of another department: not mapped
        ("What is MECH 3672?", set()),
        ("What is the deadline for Fall 2026?", set()),  # "Fall 2026" looks like a code and is not
    ],
)
def test_course_codes_map_through_their_prefix(question, expected):
    assert found(question) == expected


def test_two_departments_in_one_question():
    assert found("Compare MAT 2675 with CST 1101") == {"MATH-NYT", "CST-NYT"}
    assert found("Do Dental Hygiene students take math?") == {"DENT-NYT", "MATH-NYT"}


def test_no_department_detected():
    assert found("How do I apply for graduation at City Tech?") == set()
    assert found("") == set()


def test_every_prefix_belongs_to_one_department_in_the_config():
    seen: dict[str, str] = {}
    for dept_id, info in deps.load_departments().items():
        for prefix in info["prefixes"]:
            assert seen.setdefault(prefix, dept_id) == dept_id
    assert set(deps.load_departments()) == {"CST-NYT", "MATH-NYT", "EET-NYT", "DENT-NYT"}


# ---- configuration ----


def test_the_filter_is_off_by_default_and_validated():
    assert load_models(env={})["retrieval"]["dept_filter"] == "off"
    assert load_models(env={"CTA_DEPT_FILTER": "on"})["retrieval"]["dept_filter"] == "on"
    with pytest.raises(ValueError, match="dept_filter"):
        load_models(env={"CTA_DEPT_FILTER": "maybe"})


# ---- the filter on chunks of each scope (database) ----


def put(conn, cid, scope, dept, embedding, text="plain text"):
    conn.execute(
        "INSERT INTO chunks (id, kind, source, source_id, doc_type, department, scope, fetched_at, "
        "heading_path, text, content_hash, meta_hash, embedding, embedding_model) "
        "VALUES (%s, 'section', 's', %s, 'faq', %s, %s, 'x', %s, %s, 'h', 'm', %s, %s)",
        (cid, cid, dept, scope, cid, text, embedding, CFG["embedding_model"]),
    )
    conn.commit()


def world(conn):
    """Query vector is vec(1, 0). The CST page is the closest chunk, then the others."""
    put(conn, "cst-page", "department", "CST-NYT", vec(1.0, 0.0), "zebra")
    put(conn, "eet-page", "department", "EET-NYT", vec(0.9, 0.1), "zebra")
    put(conn, "office", "city_tech", None, vec(0.8, 0.2), "zebra")
    put(conn, "cuny-doc", "cuny", None, vec(0.7, 0.3), "zebra")
    put(
        conn, "cst-course", "city_tech", "CST-NYT", vec(0.6, 0.4), "zebra"
    )  # a course: city_tech scope
    put(conn, "math-page", "department", "MATH-NYT", vec(0.5, 0.5), "zebra")


def run(conn, tmp_path, question, mode="vector", dept_filter="on", k=6):
    client = FakeChatClient(vec(1.0, 0.0))
    return srch.search(
        conn, question, k, cfg=CFG, client_factory=lambda: client,
        cache_path=tmp_path / "c.json", mode=mode, dept_filter=dept_filter,
    )  # fmt: skip


def ids(found_):
    return [r["id"] for r in found_.results]


@pytest.mark.integration
def test_the_filter_drops_other_departments_pages_and_keeps_every_other_scope(conn, tmp_path):
    world(conn)
    got = run(conn, tmp_path, "What does the EET department do?")
    assert got.dept_filter_applied and got.detected_departments == ["EET-NYT"]
    # CST and MATH department-scope pages are gone; the EET page, the office (city_tech, no
    # department), cuny and the CST COURSE chunk (scope city_tech: never filtered) stay
    assert ids(got) == ["eet-page", "office", "cuny-doc", "cst-course"]
    assert all(
        r["dept_filter_applied"] and r["detected_departments"] == ["EET-NYT"] for r in got.results
    )


@pytest.mark.integration
def test_two_detected_departments_keep_both(conn, tmp_path):
    world(conn)
    got = run(conn, tmp_path, "Compare EET 3672 with CST 1101")
    assert got.detected_departments == ["CST-NYT", "EET-NYT"]
    assert ids(got) == ["cst-page", "eet-page", "office", "cuny-doc", "cst-course"]


@pytest.mark.integration
def test_no_department_detected_changes_nothing(conn, tmp_path):
    world(conn)
    on = run(conn, tmp_path, "How do I apply for graduation?", dept_filter="on")
    off = run(conn, tmp_path, "How do I apply for graduation?", dept_filter="off")
    assert not on.dept_filter_applied and on.detected_departments == []
    assert (
        ids(on)
        == ids(off)
        == ["cst-page", "eet-page", "office", "cuny-doc", "cst-course", "math-page"]
    )


@pytest.mark.integration
def test_filter_off_ignores_the_department_in_the_question(conn, tmp_path):
    world(conn)
    got = run(conn, tmp_path, "What does the EET department do?", dept_filter="off")
    assert not got.dept_filter_applied and "cst-page" in ids(got)


@pytest.mark.integration
def test_the_config_default_is_off_when_the_argument_is_omitted(conn, tmp_path):
    world(conn)
    client = FakeChatClient(vec(1.0, 0.0))
    got = srch.search(conn, "What does the EET department do?", 6, cfg=CFG,
                      client_factory=lambda: client, cache_path=tmp_path / "c.json")  # fmt: skip
    assert not got.dept_filter_applied and "cst-page" in ids(got)


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["hybrid", "hybrid_bm25"])
def test_the_filter_also_applies_to_the_keyword_side(conn, tmp_path, mode):
    world(conn)
    got = run(conn, tmp_path, "zebra EET", mode=mode)
    assert got.dept_filter_applied and "cst-page" not in ids(got) and "math-page" not in ids(got)
    assert "eet-page" in ids(got)
    plain = run(conn, tmp_path, "zebra EET", mode=mode, dept_filter="off")
    assert "cst-page" in ids(plain)


@pytest.mark.integration
def test_the_threshold_similarity_is_computed_after_the_filter(conn, tmp_path):
    world(conn)
    off = run(conn, tmp_path, "What does the EET department do?", dept_filter="off")
    on = run(conn, tmp_path, "What does the EET department do?", dept_filter="on")
    assert off.top_vector_similarity > 0.99  # the CST page, another department
    assert on.top_vector_similarity == pytest.approx(on.results[0]["similarity"])  # the EET page
    assert on.top_vector_similarity < off.top_vector_similarity
