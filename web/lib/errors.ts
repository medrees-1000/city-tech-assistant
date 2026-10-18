// What a visitor reads when a request fails. Plain sentences only: no status codes, no stack traces,
// no request ids (those are for the details view). The codes are the ones the API already returns
// (src/cta/api/app.py, src/cta/api/guard.py) plus two the page makes up: "unreachable" and "timeout".

import type { ApiError } from "./api.ts";

export const GENERIC = "Something went wrong. Please try again in a moment.";

const MESSAGES: Record<string, string> = {
  unreachable: "I can't reach the assistant right now. Please try again in a moment.",
  timeout: "This is taking longer than expected. Please try again in a moment.",
  unavailable: "The assistant is not available right now. Please try again in a moment.",
  provider_error: "I couldn't get an answer just now. Please try again in a moment.",
  internal_error: GENERIC,
  too_large: "That question is too long to send. Please shorten it and try again.",
  invalid_request: "That question could not be sent. Please check it and try again.",
  invalid_question: "Please type a question that is not empty and not too long.",
  rate_limited: "You're asking quickly. Please wait a moment and try again.",
  daily_cap: "The assistant has reached its limit for today. Please try again tomorrow.",
  kill_switch: "The assistant is switched off for now. Please check back later.",
  monthly_cap: "The assistant is paused for the rest of this month to stay within its budget. Please check back next month.",
  forbidden: "The assistant could not be reached from here. Please try again in a moment.",
};

/** The error code for an HTTP status whose body was not one of the API's own error objects (a proxy,
 * the host or the API answering 429, 502, 503 or 504 with its own text or a page). null: no rule. */
export function codeForStatus(status: number): string | null {
  if (status === 429) return "rate_limited";
  if (status === 503) return "unavailable";
  if (status === 408 || status === 504) return "timeout";
  if (status === 403) return "forbidden";
  if (status === 502 || status >= 500) return "unreachable";
  return null;
}

/** The visitor-facing sentence for an error. An unknown code gets the generic sentence. */
export function friendlyMessage(error: ApiError): string {
  return MESSAGES[error.code] ?? GENERIC;
}

/** True when the failure was a client-side timeout or abort of the fetch (not an API reply). */
export function isTimeout(e: unknown): boolean {
  return e instanceof Error && (e.name === "TimeoutError" || e.name === "AbortError");
}
