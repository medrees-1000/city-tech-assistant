import type { ReactNode } from "react";

import type { Citation } from "../../lib/api";
import { parseBlocks } from "../../lib/markdown";
import type { Inline } from "../../lib/markdown";

function renderInlines(items: Inline[], onCite: (n: number) => void): ReactNode[] {
  return items.map((item, i) => {
    if (item.type === "text") return <span key={i}>{item.text}</span>;
    if (item.type === "bold") return <strong key={i}>{renderInlines(item.children, onCite)}</strong>;
    return (
      <button key={i} type="button" className="cite" aria-label={`Go to source ${item.n}`} onClick={() => onCite(item.n)}>
        {item.label}
      </button>
    );
  });
}

/** The answer as paragraphs and bullet lists with bold text; each [n] marker is a button that opens
 * and jumps to source n. Everything is rendered as React text nodes (never as HTML). */
export function AnswerText({
  text,
  citations,
  onCite,
}: {
  text: string;
  citations: Citation[];
  onCite: (n: number) => void;
}) {
  return (
    <div className="answer-text">
      {parseBlocks(text, citations).map((block, i) =>
        block.type === "p" ? (
          <p key={i}>{renderInlines(block.inlines, onCite)}</p>
        ) : (
          <ul key={i} className="answer-list">
            {block.items.map((item, j) => (
              <li key={j}>{renderInlines(item, onCite)}</li>
            ))}
          </ul>
        ),
      )}
    </div>
  );
}
