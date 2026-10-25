import { codeForStatus, isTimeout } from "./errors.ts";

// The API contract (docs/phase4-plan.md, section 1) and the one fetch call. No logic besides the call.

export type Citation = {
  n: number;
  id: string;
  title: string;
  url: string | null;
  file: string | null;
  doc_type: string | null;
  term: string | null;
  last_updated: string | null;
  excerpt: string;
  cited: boolean;
};

export type ContactEmail = { address: string; for: string | null };

export type Contact = {
  office: string;
  name: string;
  emails: ContactEmail[];
  phones: string[];
  note: string | null;
};

export type AnswerType = "answer" | "abstain" | "not_announced" | "clarify" | "guardrail";

export type RetrievedChunk = {
  id: string;
  title: string | null;
  first_stage_rank: number;
  similarity: number | null;
  rerank_score: number | null;
  final_rank: number | null;
  sent_to_answerer: boolean;
};

export type ChainInfo = {
  extraction?: string;
  code?: string | null;
  detail?: string[];
  course_count?: number;
  truncated?: boolean;
  unexpanded?: { code: string; level: number; names: string[]; reason: string }[];
  no_record?: boolean;
  no_record_codes?: string[];
};

export type CalendarInfo = {
  term_status?: string;
  term?: string | null;
  selected?: string[];
  pool_size?: number;
};

export type HowFound = {
  route_detail: string;
  intent: string | null;
  top_vector_similarity: number | null;
  abstain_threshold: number;
  retrieved: RetrievedChunk[];
  calendar: CalendarInfo | null;
  chain: ChainInfo | null;
  stages_ms: Record<string, number | null>;
  tokens: Record<string, number>;
  cost_usd: Record<string, number>;
  cache_hits: Record<string, boolean>;
  abstain_wording?: string | null;
  topic_in_scope?: boolean | null;
  language?: { code: string; english: string | null } | null;
  near_miss?: boolean;
};

export type AskResponse = {
  request_id: string;
  question: string;
  answer: string;
  answer_type: AnswerType;
  abstained: boolean;
  abstain_reason: string | null;
  route: "calendar" | "chain" | "retrieve" | "clarify" | "guardrail";
  citations: Citation[];
  contact: Contact | null;
  how_found: HowFound;
  meta: { today: string; version: string; model: string };
};

export type ApiError = { code: string; message: string; request_id: string | null };

export type AskResult = { ok: true; data: AskResponse } | { ok: false; error: ApiError };

export const MAX_QUESTION_CHARS = 500; // the API limit (config api.max_question_chars)

const UNREACHABLE: ApiError = {
  code: "unreachable",
  message: "I can't reach the assistant right now. Please try again in a moment.",
  request_id: null,
};
const TIMEOUT: ApiError = {
  code: "timeout",
  message: "This is taking longer than expected. Please try again in a moment.",
  request_id: null,
};

export type LoginCode = "sign_in_required" | "gmail_required";

/** The page proxy's login refusal, decided by the code in the body ({"error":"gmail_required"}), never by
 * the HTTP status: any other 401 or 403 (the API's own "forbidden", a host page) is a normal error. */
export function loginCode(body: unknown): LoginCode | null {
  const code = (body as { error?: unknown } | null)?.error;
  return code === "sign_in_required" || code === "gmail_required" ? code : null;
}

/** An error for a failed HTTP status whose body was not the API's own error object (a proxy page, an
 * empty body, a 429 or 503 from a layer in front of the API). The page shows its own plain sentence. */
export function errorForStatus(status: number): ApiError {
  const code = codeForStatus(status);
  return code ? { code, message: "", request_id: null } : UNREACHABLE;
}

export const CLIENT_TIMEOUT_MS = 60_000; // the API's own request timeout is 45 s

/** Ask one question. Only the API's own message and request id are ever passed on as an error. */
export async function ask(question: string, signal?: AbortSignal): Promise<AskResult> {
  let response: Response;
  const limit = AbortSignal.timeout(CLIENT_TIMEOUT_MS);
  try {
    response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal: signal ? AbortSignal.any([signal, limit]) : limit,
    });
  } catch (e) {
    return { ok: false, error: isTimeout(e) ? TIMEOUT : UNREACHABLE };
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return { ok: false, error: response.ok ? UNREACHABLE : errorForStatus(response.status) };
  }
  if (response.ok) return { ok: true, data: body as AskResponse };
  const login = loginCode(body);
  if (login) return { ok: false, error: { code: login, message: "", request_id: null } };
  const e = (body as { error?: { code?: unknown; message?: unknown }; request_id?: unknown }) ?? {};
  if (typeof e.error?.message === "string") {
    const code = typeof e.error.code === "string" ? e.error.code : "error";
    const id = typeof e.request_id === "string" ? e.request_id : null;
    return { ok: false, error: { code, message: e.error.message, request_id: id } };
  }
  return { ok: false, error: errorForStatus(response.status) };
}

export type FeedbackResult = { ok: true } | { ok: false; error: ApiError };

/** Save a thumbs vote for an answer. Only "up" or "down" is ever sent (no text). */
export async function sendFeedback(requestId: string, vote: "up" | "down"): Promise<FeedbackResult> {
  try {
    const response = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: requestId, vote }),
    });
    if (response.ok) return { ok: true };
    const body = (await response.json()) as { error?: { code?: unknown; message?: unknown }; request_id?: unknown };
    if (typeof body.error?.message === "string") {
      const code = typeof body.error.code === "string" ? body.error.code : "error";
      const id = typeof body.request_id === "string" ? body.request_id : null;
      return { ok: false, error: { code, message: body.error.message, request_id: id } };
    }
  } catch {
    // fall through to the fixed message
  }
  return { ok: false, error: UNREACHABLE };
}
