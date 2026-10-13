import type { Citation } from "../../lib/api";
import { segments } from "../../lib/segments";

/** The answer text with each [n] marker turned into a button that opens and jumps to source n. */
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
    <p className="answer-text">
      {segments(text, citations).map((s, i) =>
        s.type === "text" ? (
          <span key={i}>{s.text}</span>
        ) : (
          <button key={i} type="button" className="cite" aria-label={`Go to source ${s.n}`} onClick={() => onCite(s.n)}>
            {s.label}
          </button>
        ),
      )}
    </p>
  );
}
