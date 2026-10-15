// Pure helpers for the chat page (no React): the message list, the textarea height rule and the
// wording of each answer state. Kept here so they can be tested without a browser.

import type { ApiError, AskResponse, AskResult } from "./api.ts";

export type Turn =
  | { status: "loading" }
  | { status: "done"; data: AskResponse }
  | { status: "error"; error: ApiError };

export type Message =
  | { id: number; role: "user"; text: string }
  | { id: number; role: "assistant"; turn: Turn };

export const isEmpty = (messages: Message[]): boolean => messages.length === 0;

/** Add the user's question and an assistant placeholder. Ids: `id` for the question, `id + 1`
 * for the answer. Questions are independent: nothing about earlier messages is sent. */
export function startTurn(messages: Message[], id: number, text: string): Message[] {
  return [
    ...messages,
    { id, role: "user", text },
    { id: id + 1, role: "assistant", turn: { status: "loading" } },
  ];
}

/** Replace the placeholder with the result. Unknown ids leave the list unchanged. */
export function finishTurn(messages: Message[], assistantId: number, result: AskResult): Message[] {
  const turn: Turn = result.ok
    ? { status: "done", data: result.data }
    : { status: "error", error: result.error };
  return messages.map((m) => (m.role === "assistant" && m.id === assistantId ? { ...m, turn } : m));
}

export const isLoading = (messages: Message[]): boolean =>
  messages.some((m) => m.role === "assistant" && m.turn.status === "loading");

export function canSend(text: string, loading: boolean, max: number): boolean {
  const t = text.trim();
  return t.length > 0 && text.length <= max && !loading;
}

/** The DOM id of source n inside one answer (several answers can be on the page). */
export const sourceDomId = (assistantId: number, n: number): string => `source-${assistantId}-${n}`;

// ---- the auto-growing input: one line high, up to about 6 lines, then it scrolls ----

export const LINE_PX = 24; // line height of the textarea text
export const PAD_PX = 28; // vertical padding (14 + 14)
export const MAX_LINES = 6;
export const MIN_HEIGHT = LINE_PX + PAD_PX; // 52
export const MAX_HEIGHT = MAX_LINES * LINE_PX + PAD_PX; // 172

/** The height to give the textarea for its content height (`scrollHeight`), and whether it must
 * scroll because the content is taller than six lines. */
export function fitTextarea(scrollHeight: number): { height: number; scroll: boolean } {
  const height = Math.min(Math.max(scrollHeight, MIN_HEIGHT), MAX_HEIGHT);
  return { height, scroll: scrollHeight > MAX_HEIGHT };
}

// ---- how an answer is shown ----

export const PERSONAL_ACCOUNT_TEXT =
  "I can't see personal account information such as holds, balances or grades. Here is who can help:";

export const PERSONAL_ACCOUNT_TEXT_NO_CARD =
  "I can't see personal account information such as holds, balances or grades.";

/** The contact card is shown only when the API sent a contact; otherwise nothing is rendered for it
 * (no card, no empty box, so the answer box has no gap below it). */
export const showContact = (data: AskResponse): boolean => data.contact !== null;

export type AnswerKind = "answer" | "abstain" | "personal_account" | "not_announced" | "clarify" | "guardrail";

/** Which kind of answer this is and the text to show. Abstain and "not announced yet" answers are
 * plain assistant messages like any other (no box, no label); the kind is for logic and tests. A
 * personal-account abstention shows the fixed sentence, never the model's text; the contact card
 * follows it when there is one. */
export function answerView(data: AskResponse): { kind: AnswerKind; text: string } {
  if (data.abstained && data.abstain_reason === "personal_account") {
    // "Here is who can help:" only when a contact card follows it
    const text = showContact(data) ? PERSONAL_ACCOUNT_TEXT : PERSONAL_ACCOUNT_TEXT_NO_CARD;
    return { kind: "personal_account", text };
  }
  if (data.abstained) return { kind: "abstain", text: data.answer };
  if (data.answer_type === "not_announced") return { kind: "not_announced", text: data.answer };
  if (data.answer_type === "clarify") return { kind: "clarify", text: data.answer };
  if (data.answer_type === "guardrail") return { kind: "guardrail", text: data.answer };
  return { kind: "answer", text: data.answer };
}
