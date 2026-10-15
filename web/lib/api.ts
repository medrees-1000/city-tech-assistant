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
  message: "Something went wrong. Please try again in a moment.",
  request_id: null,
};

/** Ask one question. Only the API's own message and request id are ever passed on as an error. */
export async function ask(question: string, signal?: AbortSignal): Promise<AskResult> {
  let response: Response;
  try {
    response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal,
    });
  } catch {
    return { ok: false, error: UNREACHABLE };
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return { ok: false, error: UNREACHABLE };
  }
  if (response.ok) return { ok: true, data: body as AskResponse };
  const e = (body as { error?: { code?: unknown; message?: unknown }; request_id?: unknown }) ?? {};
  if (typeof e.error?.message === "string") {
    const code = typeof e.error.code === "string" ? e.error.code : "error";
    const id = typeof e.request_id === "string" ? e.request_id : null;
    return { ok: false, error: { code, message: e.error.message, request_id: id } };
  }
  return { ok: false, error: UNREACHABLE };
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
