// A small, safe markdown subset for answers: paragraphs, "- " bullet lists, headings (#, ##, ###
// at the start of a line), **bold** and the [n] citation markers. Pure: it returns a tree that React renders as text nodes, so nothing the model
// writes is ever treated as HTML (an "<b>" in an answer is shown as the characters "<b>").

import type { Citation } from "./api.ts";
import { segments } from "./segments.ts";

export type Inline =
  | { type: "text"; text: string }
  | { type: "bold"; children: Inline[] }
  | { type: "cite"; n: number; label: string };

export type Block =
  | { type: "p"; inlines: Inline[] }
  | { type: "ul"; items: Inline[][] }
  | { type: "h"; level: 3 | 4; inlines: Inline[] }; // shown as small h3 or h4 elements, never page-title sizes

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
const HEADING = /^ {0,3}(#{1,3}) +(\S.*)$/; // "#", "##" or "###" at the start of a line, then a space

/** Blocks: a heading line is its own block ("#" and "##" become level 3, "###" level 4); consecutive
 * "- " lines are one list; other consecutive lines are one paragraph; a blank line ends a list or a
 * paragraph. Line breaks inside a paragraph are kept (the page shows them as written). */
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
    const heading = HEADING.exec(line);
    const bullet = heading ? null : BULLET.exec(line);
    if (heading) {
      flushPara();
      flushList();
      blocks.push({
        type: "h",
        level: heading[1].length === 3 ? 4 : 3,
        inlines: inlines(heading[2], citations),
      });
    } else if (bullet) {
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
