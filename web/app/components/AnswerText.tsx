import type { Citation } from "../../lib/api";
import { segments } from "../../lib/segments";

/** The answer text with each [n] marker turned into a link to source n in the list below. */
export function AnswerText({ text, citations }: { text: string; citations: Citation[] }) {
  return (
    <p className="answer-text">
      {segments(text, citations).map((s, i) =>
        s.type === "text" ? (
          <span key={i}>{s.text}</span>
        ) : (
          <a key={i} className="cite" href={`#source-${s.n}`} aria-label={`Source ${s.n}`}>
            {s.label}
          </a>
        ),
      )}
    </p>
  );
}
