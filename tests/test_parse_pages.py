import json
import shutil

from cta.parse.pages import build_pages, slug_of
from tests.test_parse_html import PAGES

HOST = "https://www.citytech.cuny.edu"


def entry(path, name, kind="office", owner="bursar", status=200, error=""):
    return {
        "url": HOST + path, "kind": kind, "owner": owner, "status": status, "error": error,
        "final_url": HOST + path if status else None,
        "saved_as": f"raw/{name}.html" if name else None,
        "content_hash": "h" if status else None, "fetched_at": "2026-10-11T00:00:00+00:00",
    }  # fmt: skip


def test_slug_of():
    assert slug_of(HOST + "/bursar/refund-policy.aspx") == "refund-policy"
    assert slug_of(HOST + "/computer-systems/") == "index"


def test_build_pages_writes_one_json_per_page_and_uses_manifest_owner(tmp_path):
    raw = tmp_path / "raw_root"
    (raw / "raw").mkdir(parents=True)
    for name in ("bursar_refund_policy", "writing_intensive_empty"):
        shutil.copy(PAGES / f"{name}.html", raw / "raw" / f"{name}.html")
    manifest = [
        entry("/bursar/refund-policy.aspx", "bursar_refund_policy"),
        entry(
            "/advisement/writing-intensive-fall26.aspx",
            "writing_intensive_empty",
            owner="advisement",
        ),
        entry(
            "/computer-systems/",
            None,
            "department",
            "CST-NYT",
            status=None,
            error="FetchBlocked: x",
        ),
        entry("/dental/gone.aspx", None, "department", "DENT-NYT", status=404),
    ]
    records = build_pages(manifest, raw, tmp_path / "out")
    assert [r["status"] for r in records] == ["collected"] + ["not_collected"] * 3
    assert records[1]["reason"] == "main content empty in raw HTML"
    assert records[2]["reason"] == "not fetched: FetchBlocked: x"
    assert records[3]["reason"] == "http 404"
    written = sorted(p.relative_to(tmp_path / "out") for p in (tmp_path / "out").rglob("*.json"))
    assert [str(p) for p in written] == [
        "pages/CST-NYT/index.json", "pages/DENT-NYT/gone.json",
        "pages/advisement/writing-intensive-fall26.json", "pages/bursar/refund-policy.json",
    ]  # fmt: skip
    saved = json.loads((tmp_path / "out/pages/bursar/refund-policy.json").read_text())
    assert saved["owner"] == "bursar" and saved["sections"][0]["heading"] == "Refund Policy"
