"use client";

import { useState } from "react";

import { sendFeedback } from "../../lib/api";
import {
  feedbackMessage,
  finishVote,
  initialFeedback,
  isDisabled,
  isPressed,
  LABELS,
  startVote,
} from "../../lib/feedback";
import type { Vote } from "../../lib/feedback";

const PATHS: Record<Vote, string> = {
  // a thumb (outline), up and down: inline SVG, no icon library
  up: "M7 11v9H4a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1h3Zm0 0 4-8a2 2 0 0 1 2 2v4h5.2a2 2 0 0 1 2 2.3l-1.1 6.2a2 2 0 0 1-2 1.7H7",
  down: "M7 13V4H4a1 1 0 0 0-1 1v7a1 1 0 0 0 1 1h3Zm0 0 4 8a2 2 0 0 0 2-2v-4h5.2a2 2 0 0 0 2-2.3l-1.1-6.2a2 2 0 0 0-2-1.7H7",
};

/** Thumbs up and thumbs down under an answer. The vote lives in this component's state only. */
export function Feedback({ requestId }: { requestId: string }) {
  const [state, setState] = useState(initialFeedback);

  async function choose(vote: Vote) {
    const next = startVote(state, vote);
    if (next === state) return; // the same vote again, or one already in flight
    setState(next);
    const result = await sendFeedback(requestId, vote);
    setState((current) => finishVote(current, result.ok));
  }

  const message = feedbackMessage(state);
  return (
    <div className="feedback" role="group" aria-label="Rate this answer">
      {(["up", "down"] as Vote[]).map((vote) => (
        <button
          key={vote}
          type="button"
          className="thumb"
          aria-label={LABELS[vote]}
          title={LABELS[vote]}
          aria-pressed={isPressed(state, vote)}
          disabled={isDisabled(state)}
          onClick={() => void choose(vote)}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d={PATHS[vote]} />
          </svg>
        </button>
      ))}
      <span className="fb-msg" role="status" aria-live="polite">
        {message}
      </span>
    </div>
  );
}
