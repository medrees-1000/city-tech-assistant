// The "How this was found" panel: plain-language sentences built only from what the API sent.
// Pure functions (no React); the component just prints the sections.

import type { AskResponse, HowFound } from "./api.ts";

/** A best match this close above the confidence cutoff is called weak. */
export const WEAK_MARGIN = 0.05;
const COURSE_PREFIX = "City Tech course catalog: ";

export type Section = { title: string; lines: string[] };
export type View = { summary: string; sections: Section[] };

export function routeWords(data: AskResponse): string {
  if (data.route === "calendar") {
    return data.abstained ? "Checked the verified calendar" : "Looked up in the verified calendar";
  }
  if (data.route === "chain") {
    return data.abstained ? "Looked for the course in the prerequisite data" : "Walked the prerequisite chain";
  }
  return "Searched City Tech pages and documents";
}

const two = (n: number): string => n.toFixed(2);

/** Why there is no answer, or null when the assistant answered. */
export function abstainWhy(data: AskResponse): string | null {
  if (!data.abstained) return null;
  const hf = data.how_found;
  const top = hf.top_vector_similarity;
  const cutoff = hf.abstain_threshold;
  const scores = top === null ? "" : ` The best match scored ${two(top)} against a confidence cutoff of ${two(cutoff)}.`;
  switch (data.abstain_reason) {
    case "below_threshold":
      return `The best match was below the confidence cutoff, so no answer was written.${scores}`;
    case "model":
      return `The search found pages, but the assistant found nothing in them that answers the question.${scores}`;
    case "personal_account":
      return "This looks like a question about a personal account, which the assistant cannot see.";
    case "calendar_no_row":
      return "No row of the calendar for that term answers the question.";
    case "calendar_unsupported_term":
      return "There is no calendar for that term.";
    case "calendar_selector_failed":
      return "The calendar lookup did not return a usable result.";
    case "chain_no_record":
      return "There is no record of that course in the catalog data of the four departments.";
    default:
      return "The assistant did not answer this question.";
  }
}

export function ordinal(n: number): string {
  const rest = n % 100;
  if (rest >= 11 && rest <= 13) return `${n}th`;
  return `${n}${({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th"}`;
}

export function formatMs(ms: number): string {
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}

/** Dollars as cents in words: "0.05 cents", "1.2 cents", "12 cents". */
export function formatCents(usd: number): string {
  const cents = usd * 100;
  if (cents <= 0) return "0 cents";
  if (cents < 0.01) return "under 0.01 cents";
  if (cents < 1) return `${cents.toFixed(2)} cents`;
  if (cents < 10) return `${cents.toFixed(1)} cents`;
  return `${Math.round(cents)} cents`;
}

/** Is the best search match weak (under the cutoff plus the margin)? Only meaningful for answers. */
export function weakNote(hf: HowFound): string | null {
  const top = hf.top_vector_similarity;
  if (top === null || top >= hf.abstain_threshold + WEAK_MARGIN) return null;
  return `The best match was weak (similarity ${two(top)}, close to the cutoff of ${two(hf.abstain_threshold)}), so check the sources before relying on this answer.`;
}

/** The candidates in the order they were put in front of the model (the order of the [n] numbers). */
export function shownSources(hf: HowFound) {
  return hf.retrieved
    .filter((c) => c.sent_to_answerer && c.final_rank !== null)
    .sort((a, b) => (a.final_rank as number) - (b.final_rank as number));
}

export function consideredLines(data: AskResponse): string[] {
  const hf = data.how_found;
  const shown = shownSources(hf);
  if (shown.length === 0) return [];
  const lines = shown.map((c, i) => {
    const parts = [`search rank ${c.first_stage_rank}`];
    if (c.similarity !== null) parts.push(`similarity ${two(c.similarity)}`);
    if (c.rerank_score !== null) parts.push(`re-check score ${c.rerank_score} of 10`);
    return `[${i + 1}] ${c.title ?? c.id} (${parts.join(", ")})`;
  });
  const rest = hf.retrieved.length - shown.length;
  if (rest > 0) lines.push(`${rest} more candidates were considered but not used.`);
  if (shown.some((c) => c.final_rank !== c.first_stage_rank)) {
    lines.push("A second check of the best 20 matches reordered them; the list above is the reordered one.");
  }
  return lines;
}

const TERM_STATUS: Record<string, string> = {
  explicit: "named in your question",
  season: "worked out from the season you wrote",
  assumed: "assumed to be the current term, because the question named none",
  unsupported: "there is no calendar for the term you named",
};

export function calendarLines(data: AskResponse): string[] {
  const cal = data.how_found.calendar;
  if (data.route !== "calendar" || !cal) return [];
  const lines: string[] = [];
  if (cal.term) lines.push(`Term: ${cal.term}${cal.term_status && TERM_STATUS[cal.term_status] ? ` (${TERM_STATUS[cal.term_status]})` : ""}`);
  if (typeof cal.pool_size === "number") lines.push(`Chosen from ${cal.pool_size} calendar rows.`);
  for (const c of data.citations) lines.push(`Row used: ${c.title}`);
  return lines;
}

export function chainLines(data: AskResponse): string[] {
  const chain = data.how_found.chain;
  if (data.route !== "chain" || !chain) return [];
  const lines: string[] = [];
  if (chain.code) lines.push(`Course asked about: ${chain.code}`);
  if (chain.no_record && chain.code) lines.push(`No catalog record for ${chain.code}.`);
  if (data.citations.length > 0) {
    lines.push(`Courses followed (${data.citations.length}), in the order found:`);
    for (const c of data.citations) lines.push(`${c.n}. ${c.title.replace(COURSE_PREFIX, "")}`);
  }
  if (chain.no_record_codes && chain.no_record_codes.length > 0) {
    lines.push(`No catalog record for: ${chain.no_record_codes.join(", ")}.`);
  }
  if (chain.truncated) {
    lines.push("The walk stopped at its depth limit.");
    for (const u of chain.unexpanded ?? []) {
      lines.push(`Not followed: ${u.code} (level ${u.level}) names ${u.names.join(", ")}.`);
    }
  }
  return lines;
}

const STEPS: [string, string][] = [
  ["classify", "Understanding the question"],
  ["select", "Choosing calendar rows"],
  ["retrieval", "Searching"],
  ["rerank", "Re-checking the best matches"],
  ["walk", "Following the prerequisites"],
  ["answer", "Writing the answer"],
  ["topic", "Naming the topic"],
];

export function stepLines(hf: HowFound): string[] {
  const lines: string[] = [];
  for (const [key, label] of STEPS) {
    const ms = hf.stages_ms[key];
    if (typeof ms === "number") lines.push(`${label}: ${formatMs(ms)}`);
  }
  const total = hf.stages_ms["total"];
  if (typeof total === "number") lines.push(`Total: ${formatMs(total)}`);
  if (hf.cache_hits["rerank"]) lines.push("The re-check scores were reused from a saved copy.");
  return lines;
}

const COSTS: [string, string][] = [
  ["classify", "understanding the question"],
  ["select", "calendar rows"],
  ["embedding", "searching"],
  ["rerank", "re-checking"],
  ["answer", "writing"],
  ["topic", "naming the topic"],
];

export function usageLines(hf: HowFound): string[] {
  const t = hf.tokens;
  const lines = [`Tokens: ${t["prompt"] ?? 0} read by the model, ${t["completion"] ?? 0} written.`];
  const total = hf.cost_usd["total"] ?? 0;
  lines.push(`Cost: ${formatCents(total)}.`);
  const parts = COSTS.filter(([k]) => (hf.cost_usd[k] ?? 0) > 0).map(([k, label]) => `${label} ${formatCents(hf.cost_usd[k])}`);
  if (parts.length > 1) lines.push(`By step: ${parts.join(", ")}.`);
  return lines;
}

/** Everything the panel shows, as titled lists of plain sentences. Sections with no lines are left out. */
export function describe(data: AskResponse): View {
  const hf = data.how_found;
  const why = abstainWhy(data);
  const noModelSources = data.abstain_reason === "below_threshold";
  const sections: Section[] = [
    { title: "What the assistant did", lines: [routeWords(data)] },
    { title: "Why there is no answer", lines: why ? [why] : [] },
    {
      title: noModelSources
        ? "Closest matches (below the cutoff, so not sent to the model)"
        : "Sources shown to the model, in the order it saw them",
      lines: data.route === "retrieve" ? consideredLines(data) : [],
    },
    { title: "Confidence", lines: !data.abstained && data.route === "retrieve" ? [weakNote(hf)].filter((x): x is string => x !== null) : [] },
    { title: "Calendar", lines: calendarLines(data) },
    { title: "Prerequisite chain", lines: chainLines(data) },
    { title: "Time", lines: stepLines(hf) },
    { title: "Tokens and cost", lines: usageLines(hf) },
  ];
  return { summary: routeWords(data), sections: sections.filter((s) => s.lines.length > 0) };
}
