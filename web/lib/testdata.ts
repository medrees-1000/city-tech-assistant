// Builders for tests: a full AskResponse with sensible defaults.

import type { AskResponse, HowFound, RetrievedChunk } from "./api.ts";

export const howFound = (over: Partial<HowFound> = {}): HowFound => ({
  route_detail: "other",
  intent: "other",
  top_vector_similarity: 0.7,
  abstain_threshold: 0.59,
  retrieved: [],
  calendar: null,
  chain: null,
  stages_ms: { classify: 900, select: null, retrieval: 20, rerank: 1500, walk: null, answer: 1300, topic: null, total: 3800 },
  tokens: { prompt: 2400, completion: 60, embedding: 7, rerank_prompt: 4900, rerank_completion: 80, topic_prompt: 0, topic_completion: 0 },
  cost_usd: { classify: 0.00004, select: 0, embedding: 0, rerank: 0.0005, answer: 0.0002, topic: 0, total: 0.00074 },
  cache_hits: { embedding: false, rerank: false },
  ...over,
});

export const chunk = (over: Partial<RetrievedChunk> = {}): RetrievedChunk => ({
  id: "page/x#1",
  title: "FAQ > Question",
  first_stage_rank: 1,
  similarity: 0.7,
  rerank_score: 8,
  final_rank: 1,
  sent_to_answerer: true,
  ...over,
});

export const response = (over: Partial<AskResponse> = {}): AskResponse => ({
  request_id: "r1",
  question: "q",
  answer: "Because. [1]",
  answer_type: "answer",
  abstained: false,
  abstain_reason: null,
  route: "retrieve",
  citations: [],
  contact: null,
  how_found: howFound(),
  meta: { today: "2026-10-13", version: "x", model: "m" },
  ...over,
});
