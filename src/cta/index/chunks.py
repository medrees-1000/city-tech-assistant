"""Build the chunks for the `chunks` table from data/processed. Pure: no network, no database.

    uv run python -m cta.index.chunks --stats    # counts, tokens, cost, gold-source check
    uv run python -m cta.index.chunks --write    # also save data/processed/chunks.jsonl

Three kinds (docs/archive/phase2-plan.md, section a): section, course, contact. Calendar events
are not chunked; the calendar table answers those questions.
"""

import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from statistics import median

import tiktoken

from cta.index.metadata import chunk_metadata
from cta.index.section_index import heading_path, is_indexable
from cta.parse.sections import merge_tables_into_parents
from cta.settings import ROOT, cost_usd, load_models

PROCESSED = ROOT / "data" / "processed"
METADATA_FIELDS = (
    "id", "kind", "source", "source_id", "doc_type", "department", "scope", "term", "terms",
    "fetched_at", "last_updated", "heading_path", "heading_url", "merged_section_ids",
)  # fmt: skip
SECTION_GROUPS = (
    ("page", "pages/*/*.json"),
    ("pdf", "pdfs/*.json"),
    ("dept", "departments/*/*.json"),
)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def finish(chunk: dict, model: str, dimensions: int) -> dict:
    """Add the two hashes. content_hash: the embedded text and the embedding settings. meta_hash:
    the metadata only, so a metadata edit never causes a re-embed."""
    meta = {f: chunk[f] for f in METADATA_FIELDS}
    chunk["content_hash"] = sha256(f"{chunk['text']}\n{model}\n{dimensions}")
    chunk["meta_hash"] = sha256(json.dumps(meta, sort_keys=True, ensure_ascii=False))
    return chunk


def section_chunks(record: dict, kind: str, stem: str) -> list[dict]:
    """One chunk per section after tables are merged into the text above them. A section's id is
    its position among all sections of the record (as in docs/section-index.md); a merged unit
    takes the id of its first section and lists the others in merged_section_ids."""
    sections = [
        {**s, "key": f"{kind}/{stem}#{n}"}
        for n, s in enumerate(record["sections"], 1)
        if s.get("embed") is not False
    ]
    chunks = []
    for unit in merge_tables_into_parents(sections):
        values, _ = chunk_metadata(record, unit)
        terms = list(unit.get("terms", []))
        for merged in unit.get("merged_keys", []):
            terms += [t for s in sections if s["key"] == merged for t in s.get("terms", [])]
        terms = list(dict.fromkeys(terms))
        path = heading_path(unit)
        chunks.append(
            {
                "id": unit["key"],
                "kind": "section",
                "source": values["source"],
                "source_id": unit["key"],
                "doc_type": values["doc_type"],
                "department": values["department"],
                "scope": values["scope"],
                "term": terms[0] if len(terms) == 1 else None,
                "terms": terms,
                "fetched_at": values["date"],
                "last_updated": values["last_updated"],
                "heading_path": path,
                "heading_url": unit.get("heading_url"),
                "merged_section_ids": unit.get("merged_keys", []),
                "text": f"{path}\n\n{unit['markdown'].strip()}",
            }
        )
    return chunks


def course_text(c: dict) -> str:
    style = c.get("prereq_style")
    if style == "text":
        prereq = c["prerequisite_text"].removeprefix("Prerequisites:").strip()
    elif style == "shorthand":
        # Not expanded: CLAUDE.md says never guess a shorthand rule.
        prereq = f"{c['prerequisite_text']} (shorthand as printed in the catalog, not expanded)"
    else:
        prereq = "none listed in the catalog"
    programs = "; ".join(f"{p['program']} ({', '.join(p['in'])})" for p in c.get("programs", []))
    lines = [
        f"{c['code']} - {c['title']}",
        f"Credits: {c['credits']}",
        f"Department: {c.get('department_name') or c['department']}",
        f"Description: {c.get('description') or 'none in the catalog'}",
        f"Prerequisites: {prereq}",
        f"Programs that list this course: {programs or 'none found'}",
    ]
    return "\n".join(lines)


def course_chunk(c: dict) -> dict:
    return {
        "id": f"catalog:{c['code']}",
        "kind": "course",
        "source": "catalog_course",
        "source_id": f"catalog:{c['code']}",
        "doc_type": "catalog_course",
        "department": c["department"],
        "scope": "city_tech",
        "term": None,
        "terms": [],
        "fetched_at": c["fetched_at"],
        "last_updated": None,
        "heading_path": f"{c['code']} - {c['title']}",
        "heading_url": None,
        "merged_section_ids": [],
        "text": course_text(c),
    }


def contact_chunk(rec: dict, names: dict[str, str]) -> dict:
    owner = rec["owner"]
    is_dept = rec["kind"] == "department"
    name = names.get(owner) or owner.replace("-", " ").title()
    title = f"Contact: {name}" + ("" if is_dept else " office")
    body = "\n\n".join(f"{p['heading']}\n{p['markdown']}" for p in rec["panels"])
    return {
        "id": f"contact:{owner}",
        "kind": "contact",
        "source": rec["source_pages"][0],
        "source_id": f"contact:{owner}",
        "doc_type": "contacts",
        "department": owner if is_dept else None,
        "scope": "department" if is_dept else "city_tech",
        "term": None,
        "terms": [],
        "fetched_at": rec["fetched_at"],
        "last_updated": None,
        "heading_path": title,
        "heading_url": None,
        "merged_section_ids": [],
        "text": f"{title}\n\n{body}",
    }


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def raw_chunks(processed: Path) -> list[dict]:
    chunks: list[dict] = []
    for kind, pattern in SECTION_GROUPS:
        for path in sorted(processed.glob(pattern)):
            record = load_json(path)
            if is_indexable(record):
                stem = path.stem if kind == "pdf" else f"{path.parent.name}/{path.stem}"
                chunks += section_chunks(record, kind, stem)
    courses = [load_json(p) for p in sorted(processed.glob("courses/*/*.json"))]
    chunks += [course_chunk(c) for c in courses]
    names = {c["department"]: c["department_name"] for c in courses if c.get("department_name")}
    chunks += [
        contact_chunk(load_json(p), names) for p in sorted(processed.glob("contacts/*.json"))
    ]
    return chunks


def get_encoding():
    """The tiktoken encoding text-embedding-3-small uses (cl100k_base). The first use downloads
    the encoding file from openaipublic.blob.core.windows.net into .cache/tiktoken."""
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(ROOT / ".cache" / "tiktoken"))
    return tiktoken.encoding_for_model("text-embedding-3-small")


def token_counter():
    """Counter for the same encoding."""
    encoding = get_encoding()
    return lambda text: len(encoding.encode(text))


def check_chunks(chunks: list[dict], count, max_tokens: int) -> list[int]:
    """Token count per chunk. Fails on a duplicate id or an oversize chunk."""
    dupes = [i for i, n in Counter(c["id"] for c in chunks).items() if n > 1]
    if dupes:
        raise ValueError(f"duplicate chunk ids: {dupes[:5]}")
    tokens = [count(c["text"]) for c in chunks]
    too_big = [(c["id"], t) for c, t in zip(chunks, tokens, strict=True) if t > max_tokens]
    if too_big:
        raise ValueError(f"chunks over max_chunk_tokens={max_tokens}: {too_big[:5]}")
    return tokens


def build_chunks(processed: Path = PROCESSED, cfg: dict | None = None, count=None) -> list[dict]:
    """All chunks, hashed and checked. Same data in, same chunks and hashes out."""
    cfg = cfg or load_models()
    count = count or token_counter()
    chunks = raw_chunks(processed)
    check_chunks(chunks, count, cfg["max_chunk_tokens"])
    return [finish(c, cfg["embedding_model"], cfg["embedding_dimensions"]) for c in chunks]


def gold_problems(chunks: list[dict], questions_path: Path = ROOT / "eval" / "questions.jsonl"):
    """Gold source ids (not calendar events) that no chunk id or merged_section_ids contains."""
    known = {c["id"] for c in chunks} | {m for c in chunks for m in c["merged_section_ids"]}
    problems = []
    for line in questions_path.read_text(encoding="utf-8").splitlines():
        q = json.loads(line)
        for g in q["gold_sources"]:
            if ("/" in g["id"] or g["id"].startswith("catalog:")) and g["id"] not in known:
                problems.append(f"{q['id']}: {g['id']}")
    return problems


NO_DATA = (
    "no chunks: data/processed has no records (it is not committed). Collect and parse the sources "
    "first (docs/running.md); nothing was written."
)


def stats(chunks: list[dict], count, cfg: dict) -> str:
    if not chunks:
        return NO_DATA
    tokens = [count(c["text"]) for c in chunks]
    total = sum(tokens)
    out = [f"chunks: {len(chunks)}"]
    out.append(
        "by kind: "
        + ", ".join(f"{k} {n}" for k, n in sorted(Counter(c["kind"] for c in chunks).items()))
    )
    out.append(
        "by doc_type: "
        + ", ".join(f"{k} {n}" for k, n in sorted(Counter(c["doc_type"] for c in chunks).items()))
    )
    merged = sum(len(c["merged_section_ids"]) for c in chunks)
    out.append(f"sections merged into a parent: {merged}")
    out.append(
        f"tokens: min {min(tokens)}, median {median(tokens)}, max {max(tokens)}, total {total}"
    )
    out.append("largest:")
    for c, t in sorted(zip(chunks, tokens, strict=True), key=lambda x: -x[1])[:5]:
        out.append(f"  {t:6} {c['id']}")
    price = cfg["embedding_model"]
    out.append(f"embedding cost, one time ({price}): ${cost_usd(cfg, price, total):.5f}")
    problems = gold_problems(chunks)
    out.append(
        f"gold sources without a chunk: {len(problems)}" + "".join(f"\n  {p}" for p in problems)
    )
    return "\n".join(out)


def main(argv: list[str]) -> int:
    flags = set(argv[1:])
    if not flags or not flags <= {"--stats", "--write"}:
        print("usage: python -m cta.index.chunks [--stats] [--write]")
        return 2
    cfg, count = load_models(), token_counter()
    try:
        chunks = build_chunks(cfg=cfg, count=count)
    except ValueError as e:
        print(f"chunk build failed: {e}")
        return 1
    if (
        not chunks
    ):  # an empty data folder: say so, write nothing (an empty chunks.jsonl would be wrong)
        print(NO_DATA)
        return 1
    if "--stats" in flags:
        print(stats(chunks, count, cfg))
    if "--write" in flags:
        path = PROCESSED / "chunks.jsonl"
        path.write_text(
            "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chunks), encoding="utf-8"
        )
        print(f"wrote {len(chunks)} chunks to {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
