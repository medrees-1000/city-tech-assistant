import { useId, useState } from "react";
import type { ReactNode } from "react";

import type { Citation } from "../../lib/api";
import { bindCitations, parseBlocks } from "../../lib/markdown";
import type { Inline } from "../../lib/markdown";
import { shouldCollapse, toggleLabel, VISIBLE_ITEMS } from "../../lib/lists";

function renderInlines(items: Inline[], onCite: (n: number) => void, bound = false): ReactNode[] {
  return (bound ? items : bindCitations(items)).map((item, i) => {
    if (item.type === "text") return <span key={i}>{item.text}</span>;
    if (item.type === "nowrap") return <span key={i} className="nowrap">{renderInlines(item.children, onCite, true)}</span>;
    if (item.type === "bold") return <strong key={i}>{renderInlines(item.children, onCite, true)}</strong>;
    return (
      <button key={i} type="button" className="cite" aria-label={`Go to source ${item.n}`} onClick={() => onCite(item.n)}>
        {item.label}
      </button>
    );
  });
}

/** A bullet list. A long one (more than five items) shows the first five and keeps the rest behind a
 * "Show all N items" button; the hidden items stay in the page (hidden attribute), so no text changes. */
function AnswerList({ items, onCite }: { items: Inline[][]; onCite: (n: number) => void }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const collapsible = shouldCollapse(items.length);
  return (
    <>
      <ul id={id} className="answer-list">
        {items.map((item, j) => (
          <li key={j} dir="auto" hidden={collapsible && !open && j >= VISIBLE_ITEMS}>
            {renderInlines(item, onCite)}
          </li>
        ))}
      </ul>
      {collapsible ? (
        <button type="button" className="list-toggle" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>
          {toggleLabel(items.length, open)}
        </button>
      ) : null}
    </>
  );
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
          <p key={i} dir="auto">{renderInlines(block.inlines, onCite)}</p>
        ) : block.type === "h" ? (
          block.level === 3 ? (
            <h3 key={i} className="answer-heading" dir="auto">{renderInlines(block.inlines, onCite)}</h3>
          ) : (
            <h4 key={i} className="answer-heading" dir="auto">{renderInlines(block.inlines, onCite)}</h4>
          )
        ) : (
          <AnswerList key={i} items={block.items} onCite={onCite} />
        ),
      )}
    </div>
  );
}
