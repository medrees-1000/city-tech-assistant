// Pure text helpers (no React): they turn answer text into pieces the page renders.

import type { Citation } from "./api.ts";

export type Segment =
  | { type: "text"; text: string }
  | { type: "cite"; n: number; label: string };

const MARKER = /\[(\d+)\]/g;

/** Split answer text at [n] markers. A marker becomes a "cite" segment only when a citation with
 * that number exists; any other bracketed number stays plain text. */
export function segments(text: string, citations: Pick<Citation, "n">[]): Segment[] {
  const known = new Set(citations.map((c) => c.n));
  const out: Segment[] = [];
  let last = 0;
  const push = (t: string) => {
    if (!t) return;
    const prev = out[out.length - 1];
    if (prev && prev.type === "text") prev.text += t;
    else out.push({ type: "text", text: t });
  };
  for (const m of text.matchAll(MARKER)) {
    const n = Number(m[1]);
    const at = m.index ?? 0;
    push(text.slice(last, at));
    if (known.has(n)) out.push({ type: "cite", n, label: m[0] });
    else push(m[0]);
    last = at + m[0].length;
  }
  push(text.slice(last));
  return out;
}

export type Piece = { type: "text"; text: string } | { type: "url"; url: string };

const URL = /https:\/\/[^\s<>"')]+[^\s<>"').,;:!?]/g;

/** Split text at https:// addresses (used for the Advisement note, whose URL comes from the data). */
export function withUrls(text: string): Piece[] {
  const out: Piece[] = [];
  let last = 0;
  for (const m of text.matchAll(URL)) {
    const at = m.index ?? 0;
    if (at > last) out.push({ type: "text", text: text.slice(last, at) });
    out.push({ type: "url", url: m[0] });
    last = at + m[0].length;
  }
  if (last < text.length) out.push({ type: "text", text: text.slice(last) });
  return out;
}

/** "718-260-5800" -> "tel:+17182605800" (digits only). */
export function telHref(phone: string): string {
  const digits = phone.replace(/\D/g, "");
  return `tel:+${digits.length === 10 ? "1" : ""}${digits}`;
}
