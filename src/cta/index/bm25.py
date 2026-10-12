"""BM25 keyword scoring over the chunks, standard library only (Phase 3, step 1b).

Postgres does only the tokenizing and stemming: `chunks.tsv` (the 'english' configuration) gives
each chunk's lexemes and how often each occurs. The scoring is done here:

    score(chunk, query) = sum over query lexemes t of
        idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(chunk) / avg_len))
    idf(t) = ln(1 + (N - df + 0.5) / (df + 0.5))

tf is the number of positions of the lexeme in the chunk, len(chunk) is the sum of tf over its
lexemes (stop words are not in the tsvector, so they are not counted), df is the number of chunks
that contain the lexeme, N the number of chunks. The constants are fixed in advance
(docs/experiments.md): k1 = 1.2, b = 0.75. They are not tuned.

A tsvector keeps at most 256 positions per lexeme and ignores positions beyond 16383. That would cap
tf for a very long chunk, but here the largest chunk is 6,868 characters, its most frequent lexeme
occurs 85 times and the longest document has 804 indexed positions, so neither cap is reached.
"""

import math
from dataclasses import dataclass, field

K1 = 1.2
B = 0.75


@dataclass
class Bm25Index:
    ids: list[str]
    lengths: list[int]
    postings: dict[str, list[tuple[int, int]]]  # lexeme -> [(chunk index, term frequency)]
    average_length: float = field(init=False)

    def __post_init__(self) -> None:
        self.average_length = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0

    def idf(self, lexeme: str) -> float:
        n, df = len(self.ids), len(self.postings.get(lexeme, ()))
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def search(self, lexemes: list[str], limit: int) -> list[tuple[str, float]]:
        """(chunk id, score) for the chunks matching any lexeme, best first, ties by id."""
        scores: dict[int, float] = {}
        for lexeme in dict.fromkeys(lexemes):  # duplicates in the query are ignored
            idf = self.idf(lexeme)
            for index, tf in self.postings.get(lexeme, ()):
                norm = tf + K1 * (1 - B + B * self.lengths[index] / self.average_length)
                scores[index] = scores.get(index, 0.0) + idf * tf * (K1 + 1) / norm
        ranked = sorted(((self.ids[i], s) for i, s in scores.items()), key=lambda x: (-x[1], x[0]))
        return ranked[:limit]


def build_index(rows: list[tuple[str, str, int]]) -> Bm25Index:
    """From (chunk id, lexeme, term frequency) rows."""
    ids: list[str] = []
    position: dict[str, int] = {}
    lengths: list[int] = []
    postings: dict[str, list[tuple[int, int]]] = {}
    for chunk_id, lexeme, tf in rows:
        if chunk_id not in position:
            position[chunk_id] = len(ids)
            ids.append(chunk_id)
            lengths.append(0)
        i = position[chunk_id]
        lengths[i] += tf
        postings.setdefault(lexeme, []).append((i, tf))
    return Bm25Index(ids, lengths, postings)


_CACHE: dict[str, tuple[tuple, Bm25Index]] = {}


def signature(conn) -> tuple:
    """Changes whenever the chunks change, so a reload rebuilds the index."""
    return conn.execute(
        "SELECT current_schema(), count(*), coalesce(max(updated_at)::text, ''), "
        "coalesce(sum(length(text)), 0) FROM chunks"
    ).fetchone()


def load_index(conn) -> Bm25Index:
    """The BM25 index, built once per process (and again if the chunks table changed)."""
    sig = signature(conn)
    cached = _CACHE.get(sig[0])
    if cached and cached[0] == sig:
        return cached[1]
    rows = conn.execute(
        "SELECT c.id, t.lexeme, coalesce(array_length(t.positions, 1), 0) "
        "FROM chunks c, unnest(c.tsv) AS t(lexeme, positions, weights) ORDER BY c.id, t.lexeme"
    ).fetchall()
    index = build_index([(r[0], r[1], r[2]) for r in rows])
    _CACHE[sig[0]] = (sig, index)
    return index


def query_lexemes(conn, question: str) -> list[str]:
    """The question's lexemes under the same 'english' configuration as the index (stop words
    dropped, ordinary words stemmed, codes such as EET 3672 or MAT 1275CO kept)."""
    rows = conn.execute(
        "SELECT lexeme FROM unnest(to_tsvector('english', %s)) ORDER BY lexeme", (question,)
    )
    return [r[0] for r in rows]


def bm25_ids(conn, lexemes: list[str], limit: int) -> list[str]:
    return [cid for cid, _ in load_index(conn).search(lexemes, limit)]
