import type { Citation } from "../../lib/api";
import { sourceDomId } from "../../lib/messages";

function Meta({ c }: { c: Citation }) {
  const parts = [c.doc_type, c.term, c.last_updated ? `updated ${c.last_updated}` : null];
  return <span className="muted small">{parts.filter(Boolean).join(" · ")}</span>;
}

/** The collapsed "Sources (n)" toggle under an answer. Open state is controlled so that a [n] link can open it. */
export function SourceList({
  assistantId,
  citations,
  open,
  onToggle,
}: {
  assistantId: number;
  citations: Citation[];
  open: boolean;
  onToggle: (open: boolean) => void;
}) {
  if (citations.length === 0) return null;
  return (
    <details className="sources" open={open} onToggle={(e) => onToggle(e.currentTarget.open)}>
      <summary>Sources ({citations.length})</summary>
      <ol className="source-list">
        {citations.map((c) => (
          <li key={c.n} id={sourceDomId(assistantId, c.n)} tabIndex={-1} className={c.cited ? "" : "uncited"}>
            <span className="source-n">[{c.n}]</span>
            <span className="source-body">
              {c.url ? (
                <a className="source-title" href={c.url} target="_blank" rel="noopener noreferrer">
                  {c.title}
                </a>
              ) : (
                <span className="source-title">{c.title}</span>
              )}
              <br />
              <Meta c={c} />
              {c.cited ? null : <span className="muted small"> · shown to the assistant, not cited</span>}
            </span>
          </li>
        ))}
      </ol>
    </details>
  );
}
