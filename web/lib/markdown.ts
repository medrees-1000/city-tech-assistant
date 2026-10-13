// A small, safe markdown subset for answers: paragraphs, "- " bullet lists, **bold** and the [n]
// citation markers. Pure: it returns a tree that React renders as text nodes, so nothing the model
// writes is ever treated as HTML (an "<b>" in an answer is shown as the characters "<b>").

import type { Citation } from "./api.ts";
import { segments } from "./segments.ts";

export type Inline =
  | { type: "text"; text: string }
  | { type: "bold"; children: Inline[] }
  | { type: "cite"; n: number; label: string };

export type Block = { type: "p"; inlines: Inline[] } | { type: "ul"; items: Inline[][] };

type Known = Pick<Citation, "n">[];

/** Text and [n] markers only (no bold). */
function plain(text: string, citations: Known): Inline[] {
  return segments(text, citations);
}

/** Split at **bold** pairs. An unmatched "**", or an empty pair, stays as text. */
export function inlines(text: string, citations: Known): Inline[] {
  const out: Inline[] = [];
  const push = (items: Inline[]) => {
    for (const item of items) {
      const prev = out[out.length - 1];
      if (item.type === "text" && prev && prev.type === "text") prev.text += item.text;
      else out.push(item);
    }
  };
  let from = 0;
  let search = 0;
  for (;;) {
    const open = text.indexOf("**", search);
    if (open < 0) break;
    const close = text.indexOf("**", open + 2);
    if (close < 0) break;
    const inner = text.slice(open + 2, close);
    if (inner.trim() === "") {
      search = open + 2; // "****" or "** **": not bold, keep looking after the opening marks
      continue;
    }
    push(plain(text.slice(from, open), citations));
    out.push({ type: "bold", children: plain(inner, citations) });
    from = search = close + 2;
  }
  push(plain(text.slice(from), citations));
  return out;
}

const BULLET = /^\s*- (\S.*)$/;

/** Blocks: consecutive "- " lines are one list; other consecutive lines are one paragraph; a blank
 * line ends either. Line breaks inside a paragraph are kept (the page shows them as written). */
export function parseBlocks(text: string, citations: Known): Block[] {
  const blocks: Block[] = [];
  let para: string[] = [];
  let items: Inline[][] | null = null;
  const flushPara = () => {
    if (para.length) blocks.push({ type: "p", inlines: inlines(para.join("\n"), citations) });
    para = [];
  };
  const flushList = () => {
    if (items) blocks.push({ type: "ul", items });
    items = null;
  };
  for (const line of text.replace(/\r\n?/g, "\n").split("\n")) {
    const bullet = BULLET.exec(line);
    if (bullet) {
      flushPara();
      (items ??= []).push(inlines(bullet[1], citations));
    } else if (line.trim() === "") {
      flushPara();
      flushList();
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara();
  flushList();
  return blocks;
}
