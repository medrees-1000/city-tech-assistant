import json

from cta.crawl.catalog import decode_entities
from cta.validate.entities import check_entities, entities_in


def test_entities_in_finds_named_and_numeric_forms_in_nested_values():
    data = {"a": "CAD&rsquo;s", "b": ["x &amp; y", {"c": "&#8217; and &#x27;"}], "n": 5}
    assert sorted(entities_in(data)) == ["&#8217;", "&#x27;", "&amp;", "&rsquo;"]
    assert entities_in({"a": "R&D and AT&T; plain text, a < b"}) == []


def test_check_fails_for_each_record_with_an_entity(tmp_path):
    (tmp_path / "courses").mkdir()
    (tmp_path / "courses" / "bad.json").write_text(json.dumps({"description": "design &amp; test"}))
    (tmp_path / "courses" / "good.json").write_text(json.dumps({"description": "design & test"}))
    count, findings = check_entities(tmp_path)
    assert count == 2 and len(findings) == 1
    assert findings[0].severity == "fail" and findings[0].course == "courses/bad.json"


def test_decode_entities():
    assert decode_entities("CAD&rsquo;s design &amp; test") == "CAD’s design & test"
    assert decode_entities(None) is None
