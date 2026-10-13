import type { Citation } from "../../lib/api";

function Meta({ c }: { c: Citation }) {
  const parts = [c.doc_type, c.term, c.last_updated ? `updated ${c.last_updated}` : null];
  return <span className="muted small">{parts.filter(Boolean).join(" · ")}</span>;
}

export function SourceList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <section aria-labelledby="sources-title" className="sources">
      <h3 id="sources-title" className="section-title">
        Sources
      </h3>
      <ol className="source-list">
        {citations.map((c) => (
          <li key={c.n} id={`source-${c.n}`} tabIndex={-1} className={c.cited ? "" : "uncited"}>
            <span className="source-n">[{c.n}]</span>
            <span className="source-body">
              {c.url ? (
                <a href={c.url} target="_blank" rel="noopener noreferrer">
                  {c.title}
                </a>
              ) : (
                <span>{c.title}</span>
              )}
              <br />
              <Meta c={c} />
              {c.cited ? null : <span className="muted small"> · shown to the assistant, not cited</span>}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
