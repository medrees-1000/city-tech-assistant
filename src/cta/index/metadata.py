"""The metadata every chunk carries (CLAUDE.md, "Data rules"), read from a record.

A record is a page, a PDF or a department record. A field is missing when the record has none of
the keys that can hold it, and null when the key is there with value None.
"""

SOURCE_KEYS = ("source_url", "source_file")
DATE_KEYS = ("fetched_at", "file_date", "file_modified", "file_created")  # fetch or file date
UPDATED_KEYS = ("last_updated", "pdf_last_updated")
FIELDS = ("source", "doc_type", "department", "scope", "term", "date", "last_updated")
NOT_NULL = ("source", "doc_type", "scope", "date")  # department, term, last_updated may be null


def first_present(record: dict, keys: tuple[str, ...]) -> tuple[bool, object]:
    """(some key exists, the first non-null value among the keys that exist)."""
    present = [k for k in keys if k in record]
    return bool(present), next((record[k] for k in present if record[k] is not None), None)


def chunk_metadata(record: dict) -> tuple[dict, list[str]]:
    """(the seven metadata values, the fields the record has no key for)."""
    values: dict = {}
    missing: list[str] = []
    candidates = {
        "source": SOURCE_KEYS,
        "doc_type": ("doc_type",),
        "department": ("department",),
        "scope": ("scope",),
        "term": ("term",),
        "date": DATE_KEYS,
        "last_updated": UPDATED_KEYS,
    }
    for field, keys in candidates.items():
        found, value = first_present(record, keys)
        values[field] = value
        if not found:
            missing.append(field)
    return values, missing


def null_problems(values: dict) -> list[str]:
    """Fields that are null where null is not allowed. A department is required when the scope is
    "department"; it may be null for central offices and CUNY-wide documents."""
    bad = [f for f in NOT_NULL if values[f] is None]
    if values["scope"] == "department" and values["department"] is None:
        bad.append("department")
    return bad
