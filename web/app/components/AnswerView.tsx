import type { AskResponse } from "../../lib/api";
import { AnswerText } from "./AnswerText";
import { ContactCard } from "./ContactCard";
import { SourceList } from "./SourceList";

const LABELS = {
  answer: null,
  abstain: "No answer found",
  not_announced: "Not announced yet",
  clarify: "Needs a clarification",
} as const;

export function AnswerView({ data }: { data: AskResponse }) {
  const label = LABELS[data.answer_type];
  return (
    <article className={`answer answer-${data.answer_type}`} aria-label="Answer">
      <p className="asked muted small">You asked: {data.question}</p>
      {label ? <p className="state-label">{label}</p> : null}
      {data.answer_type === "abstain" ? (
        <p className="answer-text">{data.answer}</p>
      ) : (
        <AnswerText text={data.answer} citations={data.citations} />
      )}
      {data.contact ? <ContactCard contact={data.contact} /> : null}
      <SourceList citations={data.citations} />
      {/* STEP 6: the collapsible "how this was found" panel goes here (data.how_found). Not built yet. */}
      <div id="how-found-slot" hidden />
    </article>
  );
}
