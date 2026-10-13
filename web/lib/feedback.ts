// The state of the thumbs buttons under one answer. Pure functions; the votes live in the page
// state only (no cookies, no storage). A vote is "up" or "down", nothing else.

export type Vote = "up" | "down";
export type FeedbackState = {
  vote: Vote | null; // the vote the server has saved
  pending: Vote | null; // the vote being sent
  status: "idle" | "sending" | "saved" | "error";
};

export const initialFeedback: FeedbackState = { vote: null, pending: null, status: "idle" };

export const LABELS: Record<Vote, string> = { up: "Good answer", down: "Wrong or unhelpful" };

/** A vote can be sent when none is in flight and it differs from the saved one: choosing the same
 * button again does nothing (keep it simple: switching between up and down only). */
export const canVote = (s: FeedbackState, v: Vote): boolean => s.status !== "sending" && s.vote !== v;

/** Both buttons are disabled while a vote is in flight. */
export const isDisabled = (s: FeedbackState): boolean => s.status === "sending";

export function startVote(s: FeedbackState, v: Vote): FeedbackState {
  return canVote(s, v) ? { ...s, pending: v, status: "sending" } : s;
}

/** The answer of the server: the pending vote is now saved, or the old vote stays and there is an error. */
export function finishVote(s: FeedbackState, ok: boolean): FeedbackState {
  if (s.pending === null) return s;
  return ok
    ? { vote: s.pending, pending: null, status: "saved" }
    : { vote: s.vote, pending: null, status: "error" };
}

/** Which button looks chosen: the vote being sent shows at once, and goes back if it fails. */
export const isPressed = (s: FeedbackState, v: Vote): boolean => (s.pending ?? s.vote) === v;

export function feedbackMessage(s: FeedbackState): string | null {
  if (s.status === "sending") return "Saving…";
  if (s.status === "saved") return "Thanks, noted";
  if (s.status === "error") return "Your vote could not be saved. Please try again.";
  return null;
}
