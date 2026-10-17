"""Free replay of the quoted-sentence addenda over every stored answer (no model call, no network).

    uv run python scripts/quote_addenda_replay.py

For each stored answer that is not an abstention: the cited numbers come from its [n] markers, the
numbered chunks from the logged `retrieved` ids (text read from data/processed/chunks.jsonl), then
cta.answer.add_quoted_sentences runs with the rules of config/models.yaml. Prints every answer that
would change (log id, run, route, the added text) and checks that the added sentence is a
substring of the cited chunk.
"""

import json
import re
import sys

from cta.answer import add_quoted_sentences
from cta.index.db import connect
from cta.settings import ROOT, load_models

MARK = re.compile(r"\[(\d+)\]")


def main() -> int:
    rules = load_models()["answer"]["quote_addenda"]
    chunks = {}
    for line in (
        (ROOT / "data" / "processed" / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
    ):
        c = json.loads(line)
        chunks[c["id"]] = c
    with connect() as conn:
        rows = conn.execute(
            "SELECT l.id, e.label, l.route, l.question, l.answer, l.retrieved FROM request_logs l "
            "JOIN eval_runs e ON e.id = l.run_id ORDER BY l.id"
        ).fetchall()
    changed, citing = [], 0
    for log_id, label, route, question, answer, retrieved in rows:
        if not answer or answer.startswith("ABSTAIN") or not retrieved:
            continue
        sources = [chunks.get(r["id"], {"id": r["id"], "text": ""}) for r in retrieved]
        cites = sorted({int(n) for n in MARK.findall(answer)})
        citing += any(
            1 <= n <= len(sources) and sources[n - 1]["id"] in {r["chunk"] for r in rules}
            for n in cites
        )
        after = add_quoted_sentences(answer, sources, cites, rules)
        if after != answer:
            added = after[len(answer) :]
            quote = re.search(r"“(.*)”", added).group(1)
            n = int(MARK.search(added[-6:]).group(1))
            assert quote in " ".join(sources[n - 1]["text"].split()), "not a substring of the chunk"
            changed.append((log_id, label, route, question, answer, added))
    print(
        f"{len(rows)} stored answers; {citing} cite a configured chunk; {len(changed)} would change"
    )
    for log_id, label, route, question, answer, added in changed:
        print(f"- log id {log_id} | run {label} | route {route} | question: {question[:80]}")
        print(f"    appended: {added.strip()!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
